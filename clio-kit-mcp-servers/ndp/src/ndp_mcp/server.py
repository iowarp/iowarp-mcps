import asyncio
import os
from typing import Annotated, Any

import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from pydantic import BaseModel, Field

# Environment setup
load_dotenv()

# Initialize FastMCP server instance
mcp: FastMCP = FastMCP(
    "ndp",
    instructions=(
        "Discovers, explores, and registers data on the National Data Platform. "
        "Read tools: list_organizations, search_datasets, get_dataset_details, "
        "search_resources, get_jupyter_details, get_user_info. "
        "Write tools (need bearer auth via NDP_BEARER_TOKEN): register_dataset, "
        "register_kafka_topic, register_s3_resource, register_url_resource. "
        "Use the `ndp://catalogs` resource for available catalog scopes."
    ),
    list_page_size=10,
)


class Dataset(BaseModel):
    """Model for dataset information from NDP API."""

    id: str
    name: str
    title: str
    owner_org: str | None = None
    notes: str | None = None
    resources: list[dict[str, Any]] = Field(default_factory=list)
    extras: dict[str, Any] | None = None


class NDPClient:
    """Client for interacting with NDP API with retry logic and error handling."""

    def __init__(self, base_url: str | None = None, bearer: str | None = None):
        self.base_url = (base_url or os.getenv("NDP_BASE_URL", "http://155.101.6.191:8003")).rstrip("/")
        self.bearer = bearer or os.getenv("NDP_BEARER_TOKEN")
        self.timeout = httpx.Timeout(30.0)
        self.max_retries = 3
        self.retry_delay = 1.0

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {"Accept": "application/json"}
        if self.bearer:
            h["Authorization"] = f"Bearer {self.bearer}"
        return h

    async def _make_request(  # type: ignore[return]
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make HTTP request with retry logic."""
        url = f"{self.base_url}{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    headers = self._headers()
                    if method.upper() == "GET":
                        response = await client.get(url, params=params, headers=headers)
                    elif method.upper() == "POST":
                        response = await client.post(
                            url, params=params, json=json_data, headers=headers
                        )
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    response.raise_for_status()
                    if not response.content:
                        return {}
                    return response.json()  # type: ignore[no-any-return]

            except httpx.TimeoutException:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                raise Exception(f"Request timed out after {self.max_retries} attempts") from None
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500 and attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                raise Exception(f"HTTP {e.response.status_code}: {e.response.text}") from e
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2**attempt))
                    continue
                raise Exception(f"Request failed: {str(e)}") from e

    async def list_organizations(
        self, name_filter: str | None = None, server: str = "global"
    ) -> list[str]:
        """List organizations from NDP API."""
        params = {"server": server}
        if name_filter:
            params["name"] = name_filter

        result = await self._make_request("GET", "/organization", params=params)
        return result if isinstance(result, list) else []

    async def search_datasets_simple(
        self, terms: list[str], keys: list[str] | None = None, server: str = "global"
    ) -> list[Dataset]:
        """Search datasets using simple term-based search."""
        params = {"server": server}

        # Add terms as query parameters
        for term in terms:
            params.setdefault("terms", []).append(term)  # type: ignore[attr-defined, arg-type]

        # Add keys if provided
        if keys:
            for key in keys:
                params.setdefault("keys", []).append(key)  # type: ignore[attr-defined, arg-type]

        result = await self._make_request("GET", "/search", params=params)

        if isinstance(result, list):
            return [Dataset(**item) for item in result]
        return []

    async def search_datasets_advanced(
        self,
        dataset_name: str | None = None,
        dataset_title: str | None = None,
        owner_org: str | None = None,
        resource_url: str | None = None,
        resource_name: str | None = None,
        dataset_description: str | None = None,
        resource_description: str | None = None,
        resource_format: str | None = None,
        search_term: str | None = None,
        filter_list: list[str] | None = None,
        timestamp: str | None = None,
        server: str = "global",
    ) -> list[Dataset]:
        """Search datasets using advanced search with specific field filtering."""
        search_data = {"server": server}

        # Add all non-None parameters to the search
        if dataset_name:
            search_data["dataset_name"] = dataset_name
        if dataset_title:
            search_data["dataset_title"] = dataset_title
        if owner_org:
            search_data["owner_org"] = owner_org
        if resource_url:
            search_data["resource_url"] = resource_url
        if resource_name:
            search_data["resource_name"] = resource_name
        if dataset_description:
            search_data["dataset_description"] = dataset_description
        if resource_description:
            search_data["resource_description"] = resource_description
        if resource_format:
            search_data["resource_format"] = resource_format
        if search_term:
            search_data["search_term"] = search_term
        if filter_list:
            search_data["filter_list"] = filter_list  # type: ignore[assignment]
        if timestamp:
            search_data["timestamp"] = timestamp

        result = await self._make_request("POST", "/search", json_data=search_data)

        if isinstance(result, list):
            return [Dataset(**item) for item in result]
        return []


# Initialize NDP client
ndp_client = NDPClient()


@mcp.tool(
    name="list_organizations",
    description="List organizations available in the National Data Platform.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"organizations", "catalogs"},
)
async def list_organizations(
    name_filter: Annotated[
        str | None, Field(description="Filter organizations by name substring match")
    ] = None,
    server: Annotated[
        str, Field(description="Server to query: 'local', 'global', or 'pre_ckan'")
    ] = "global",
) -> dict[str, Any]:
    """List organizations from the National Data Platform."""
    try:
        organizations = await ndp_client.list_organizations(name_filter, server)

        return {
            "organizations": organizations,
            "count": len(organizations),
            "server": server,
            "name_filter": name_filter,
            "_meta": {"tool": "list_organizations", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_datasets",
    description="Search for datasets in the NDP using term-based or field-specific criteria.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"datasets", "search"},
)
async def search_datasets(
    search_terms: Annotated[
        list[str] | None, Field(description="Terms for simple search across all fields")
    ] = None,
    search_keys: Annotated[
        list[str] | None, Field(description="Corresponding keys for each search term")
    ] = None,
    dataset_name: Annotated[
        str | None, Field(description="Exact or partial dataset name to match")
    ] = None,
    dataset_title: Annotated[str | None, Field(description="Dataset title to search for")] = None,
    owner_org: Annotated[
        str | None, Field(description="Organization name that owns the dataset")
    ] = None,
    resource_url: Annotated[str | None, Field(description="URL of dataset resource")] = None,
    resource_name: Annotated[str | None, Field(description="Name of dataset resource")] = None,
    dataset_description: Annotated[
        str | None, Field(description="Text to search in dataset descriptions")
    ] = None,
    resource_description: Annotated[
        str | None, Field(description="Text to search in resource descriptions")
    ] = None,
    resource_format: Annotated[
        str | None, Field(description="Resource format (e.g., CSV, JSON, NetCDF)")
    ] = None,
    search_term: Annotated[
        str | None, Field(description="Comma-separated terms to search across all fields")
    ] = None,
    filter_list: Annotated[
        list[str] | None, Field(description="Field filters in format 'key:value'")
    ] = None,
    timestamp: Annotated[str | None, Field(description="Filter by timestamp field")] = None,
    server: Annotated[str, Field(description="Server to search: 'local' or 'global'")] = "global",
    limit: Annotated[
        str | int | None, Field(description="Maximum results to return (default: 20)")
    ] = None,
) -> dict[str, Any]:
    """Search for datasets in the National Data Platform."""
    try:
        # Determine which search method to use
        if search_terms:
            # Use simple search
            datasets = await ndp_client.search_datasets_simple(
                terms=search_terms, keys=search_keys, server=server
            )
        else:
            # Use advanced search
            datasets = await ndp_client.search_datasets_advanced(
                dataset_name=dataset_name,
                dataset_title=dataset_title,
                owner_org=owner_org,
                resource_url=resource_url,
                resource_name=resource_name,
                dataset_description=dataset_description,
                resource_description=resource_description,
                resource_format=resource_format,
                search_term=search_term,
                filter_list=filter_list,
                timestamp=timestamp,
                server=server,
            )

        # Store total count before limiting
        total_found = len(datasets)

        # Convert limit to integer if it's a string
        if isinstance(limit, str):
            try:
                limit = int(limit)
            except ValueError:
                limit = None

        # Apply limit if specified, or default limit of 20 to prevent huge responses
        effective_limit = limit if limit and limit > 0 else 20
        was_limited = len(datasets) > effective_limit

        if len(datasets) > effective_limit:
            datasets = datasets[:effective_limit]

        # Convert datasets to dict format
        dataset_dicts = [dataset.model_dump() for dataset in datasets]

        return {
            "datasets": dataset_dicts,
            "count": len(dataset_dicts),
            "total_found": total_found
            if not was_limited
            else f"{len(dataset_dicts)} of {total_found}",
            "server": server,
            "search_parameters": {
                "search_terms": search_terms,
                "search_keys": search_keys,
                "dataset_name": dataset_name,
                "dataset_title": dataset_title,
                "owner_org": owner_org,
                "resource_format": resource_format,
                "search_term": search_term,
                "filter_list": filter_list,
                "limit": limit,
            },
            "_meta": {"tool": "search_datasets", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_dataset_details",
    description="Retrieve detailed metadata for a specific dataset by ID or name.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"datasets", "metadata"},
)
async def get_dataset_details(
    dataset_identifier: Annotated[
        str, Field(description="The dataset ID or name to retrieve details for")
    ],
    identifier_type: Annotated[str, Field(description="Type of identifier: 'id' or 'name'")] = "id",
    server: Annotated[str, Field(description="Server to query: 'local' or 'global'")] = "global",
) -> dict[str, Any]:
    """Get detailed information about a specific dataset."""
    try:
        # Search for the specific dataset
        if identifier_type == "id":
            datasets = await ndp_client.search_datasets_advanced(server=server)
            matching_dataset = next((d for d in datasets if d.id == dataset_identifier), None)
        else:
            datasets = await ndp_client.search_datasets_advanced(
                dataset_name=dataset_identifier, server=server
            )
            matching_dataset = next((d for d in datasets if d.name == dataset_identifier), None)

        if not matching_dataset:
            raise ToolError(f"Dataset not found with {identifier_type}: {dataset_identifier}")

        # Return detailed dataset information
        dataset_dict = matching_dataset.model_dump()

        return {
            "dataset": dataset_dict,
            "identifier_used": {"type": identifier_type, "value": dataset_identifier},
            "server": server,
            "resource_count": len(dataset_dict.get("resources", [])),
            "_meta": {"tool": "get_dataset_details", "status": "success"},
        }
    except ToolError:
        raise
    except Exception as e:
        raise ToolError(str(e)) from e


# ── Registration tools (write — bearer required) ────────────────────────


@mcp.tool(
    name="register_dataset",
    description=(
        "Create a new general dataset in NDP. Requires bearer auth "
        "(NDP_BEARER_TOKEN env var). The dataset is created in the "
        "specified catalog scope and can then be populated with resources."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    tags={"datasets", "registration", "write"},
)
async def register_dataset(
    name: Annotated[
        str,
        Field(
            description="Unique dataset name — lowercase alphanumeric, hyphens, underscores"
        ),
    ],
    title: Annotated[str, Field(description="Human-readable dataset title")],
    owner_org: Annotated[str, Field(description="ID of the owning organization")],
    notes: Annotated[
        str | None, Field(description="Description / abstract")
    ] = None,
    tags: Annotated[
        list[str] | None, Field(description="Tag list for categorization")
    ] = None,
    license_id: Annotated[
        str | None, Field(description="License identifier (e.g. 'cc-by')")
    ] = None,
    private: Annotated[
        bool | None, Field(description="If True, the dataset is not publicly listed")
    ] = None,
    server: Annotated[
        str, Field(description="Catalog scope: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Register a new dataset on NDP."""
    body: dict[str, Any] = {"name": name, "title": title, "owner_org": owner_org}
    if notes is not None:
        body["notes"] = notes
    if tags is not None:
        body["tags"] = tags
    if license_id is not None:
        body["license_id"] = license_id
    if private is not None:
        body["private"] = private
    try:
        result = await ndp_client._make_request(
            "POST", "/dataset", params={"server": server}, json_data=body
        )
        return {
            "registration": result,
            "name": name,
            "server": server,
            "_meta": {"tool": "register_dataset", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="register_kafka_topic",
    description=(
        "Register a Kafka topic as an NDP streaming data source. Requires "
        "bearer auth. Creates a dataset entry that points at the topic."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    tags={"streaming", "kafka", "registration", "write"},
)
async def register_kafka_topic(
    dataset_name: Annotated[
        str, Field(description="Unique dataset name (lowercase alphanumeric)")
    ],
    dataset_title: Annotated[str, Field(description="Dataset title")],
    owner_org: Annotated[str, Field(description="Owning organization")],
    kafka_topic: Annotated[str, Field(description="Kafka topic name")],
    kafka_host: Annotated[str, Field(description="Kafka broker host")],
    kafka_port: Annotated[
        int, Field(description="Kafka broker port (1-65535)", ge=1, le=65535)
    ],
    dataset_description: Annotated[
        str | None, Field(description="Description of the dataset")
    ] = None,
    server: Annotated[
        str, Field(description="Catalog scope: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Register a Kafka topic with NDP."""
    body: dict[str, Any] = {
        "dataset_name": dataset_name,
        "dataset_title": dataset_title,
        "owner_org": owner_org,
        "kafka_topic": kafka_topic,
        "kafka_host": kafka_host,
        "kafka_port": kafka_port,
    }
    if dataset_description is not None:
        body["dataset_description"] = dataset_description
    try:
        result = await ndp_client._make_request(
            "POST", "/kafka", params={"server": server}, json_data=body
        )
        return {
            "registration": result,
            "dataset_name": dataset_name,
            "kafka_topic": kafka_topic,
            "server": server,
            "_meta": {"tool": "register_kafka_topic", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="register_s3_resource",
    description=(
        "Register an S3-hosted file as an NDP resource. Requires bearer auth. "
        "The S3 URL must be reachable from the NDP endpoint."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    tags={"resources", "s3", "registration", "write"},
)
async def register_s3_resource(
    resource_name: Annotated[
        str, Field(description="Unique resource name (lowercase alphanumeric)")
    ],
    resource_title: Annotated[str, Field(description="Resource title")],
    owner_org: Annotated[str, Field(description="Owning organization")],
    resource_s3: Annotated[
        str, Field(description="S3 URL (s3://bucket/key/path)")
    ],
    notes: Annotated[
        str | None, Field(description="Notes / description")
    ] = None,
    server: Annotated[
        str, Field(description="Catalog scope: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Register an S3 resource with NDP."""
    body: dict[str, Any] = {
        "resource_name": resource_name,
        "resource_title": resource_title,
        "owner_org": owner_org,
        "resource_s3": resource_s3,
    }
    if notes is not None:
        body["notes"] = notes
    try:
        result = await ndp_client._make_request(
            "POST", "/s3", params={"server": server}, json_data=body
        )
        return {
            "registration": result,
            "resource_name": resource_name,
            "s3_url": resource_s3,
            "server": server,
            "_meta": {"tool": "register_s3_resource", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="register_url_resource",
    description=(
        "Register a URL-addressable resource (CSV / JSON / NetCDF / stream / "
        "etc.). Requires bearer auth."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    tags={"resources", "url", "registration", "write"},
)
async def register_url_resource(
    resource_name: Annotated[
        str, Field(description="Unique resource name (lowercase alphanumeric)")
    ],
    resource_title: Annotated[str, Field(description="Resource title")],
    owner_org: Annotated[str, Field(description="Owning organization")],
    resource_url: Annotated[str, Field(description="URL of the resource")],
    file_type: Annotated[
        str | None,
        Field(description="Resource format: stream | CSV | TXT | JSON | NetCDF | ..."),
    ] = None,
    notes: Annotated[
        str | None, Field(description="Notes / description")
    ] = None,
    server: Annotated[
        str, Field(description="Catalog scope: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Register a URL-based resource with NDP."""
    body: dict[str, Any] = {
        "resource_name": resource_name,
        "resource_title": resource_title,
        "owner_org": owner_org,
        "resource_url": resource_url,
    }
    if file_type is not None:
        body["file_type"] = file_type
    if notes is not None:
        body["notes"] = notes
    try:
        result = await ndp_client._make_request(
            "POST", "/url", params={"server": server}, json_data=body
        )
        return {
            "registration": result,
            "resource_name": resource_name,
            "url": resource_url,
            "server": server,
            "_meta": {"tool": "register_url_resource", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


# ── Resource discovery (read) ───────────────────────────────────────────


@mcp.tool(
    name="search_resources",
    description=(
        "Search the NDP resource catalog (across all datasets) by name, URL, "
        "format, or free-text query. Returns matching resources with their "
        "parent dataset references."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"resources", "search"},
)
async def search_resources(
    q: Annotated[
        str | None, Field(description="Free-text query across all resource fields")
    ] = None,
    name: Annotated[str | None, Field(description="Resource name to match")] = None,
    url: Annotated[str | None, Field(description="Resource URL to match")] = None,
    format: Annotated[
        str | None, Field(description="Format (CSV, JSON, NetCDF, ...)")
    ] = None,
    description: Annotated[
        str | None, Field(description="Text to search in resource descriptions")
    ] = None,
    limit: Annotated[int | None, Field(description="Max results (default 20)")] = None,
    offset: Annotated[int | None, Field(description="Pagination offset")] = None,
    server: Annotated[
        str,
        Field(
            description=(
                "Catalog to search — 'local' or 'pre_ckan'. /resources/search "
                "does not support 'global' (federation-wide) — use "
                "search_datasets for that."
            )
        ),
    ] = "local",
) -> dict[str, Any]:
    """Search the NDP resource catalog."""
    params: dict[str, Any] = {"server": server}
    if q is not None:
        params["q"] = q
    if name is not None:
        params["name"] = name
    if url is not None:
        params["url"] = url
    if format is not None:
        params["format"] = format
    if description is not None:
        params["description"] = description
    if limit is not None:
        params["limit"] = limit
    if offset is not None:
        params["offset"] = offset
    try:
        result = await ndp_client._make_request(
            "GET", "/resources/search", params=params
        )
        resources = (
            result
            if isinstance(result, list)
            else (result.get("resources", []) if isinstance(result, dict) else [])
        )
        return {
            "resources": resources,
            "count": len(resources),
            "server": server,
            "_meta": {"tool": "search_resources", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


# ── Status / user (read — bearer required) ──────────────────────────────


@mcp.tool(
    name="get_jupyter_details",
    description=(
        "Fetch JupyterHub workspace connection details for the current user "
        "(URL, available kernels, token-handling guidance). Requires bearer "
        "auth."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"jupyter", "workspace", "status"},
)
async def get_jupyter_details() -> dict[str, Any]:
    """Return the user's JupyterHub workspace connection info."""
    try:
        result = await ndp_client._make_request("GET", "/status/jupyter")
        return {
            "jupyter": result,
            "_meta": {"tool": "get_jupyter_details", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_user_info",
    description=(
        "Return the calling user's identity and authorization claims "
        "(name, email, roles, org memberships). Requires bearer auth."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"user", "auth"},
)
async def get_user_info() -> dict[str, Any]:
    """Return the current authenticated user's identity."""
    try:
        result = await ndp_client._make_request("GET", "/user/info")
        return {
            "user": result,
            "_meta": {"tool": "get_user_info", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


# ── Live-stream / data-source tools (4 new) ─────────────────────────────
# Cover the workflow behind the EarthScope GNSS UI at
# https://vdc-192.chpc.utah.edu/gnss-ui/ — discover Kafka streams,
# inspect broker health, register a downstream-derived topic. The
# `/resources/search?format=kafka&server=local` endpoint returns Kafka
# resources WITHOUT auth, so the discovery tool below is usable by an
# unauthenticated model client.


@mcp.tool(
    name="list_kafka_streams",
    description=(
        "List Kafka streaming data sources in NDP — host/port/topic of each. "
        "Free to call without auth on `server='local'`. Optionally filter "
        "by free-text query or topic-name substring."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"streams", "kafka", "discovery"},
)
async def list_kafka_streams(
    q: Annotated[
        str | None, Field(description="Free-text query across resource fields")
    ] = None,
    name: Annotated[
        str | None, Field(description="Resource name substring to match (e.g. 'gnss')")
    ] = None,
    limit: Annotated[int | None, Field(description="Max rows (default 20)")] = None,
    server: Annotated[
        str, Field(description="Catalog: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Discover Kafka streams available on NDP."""
    params: dict[str, Any] = {"server": server, "format": "kafka"}
    if q is not None:
        params["q"] = q
    if name is not None:
        params["name"] = name
    if limit is not None:
        params["limit"] = limit
    try:
        result = await ndp_client._make_request("GET", "/resources/search", params=params)
        # The endpoint returns {"count": N, "results": [...]} OR a bare list.
        if isinstance(result, dict):
            rows = result.get("results") or result.get("resources") or []
        elif isinstance(result, list):
            rows = result
        else:
            rows = []
        # Pull out the kafka-specific fields each resource encodes in
        # its `description` JSON-blob — host / port / topic. Falls back
        # to the raw description if it isn't JSON.
        import json
        compact = []
        for r in rows:
            desc_raw = r.get("description", "") or ""
            try:
                desc = json.loads(desc_raw)
            except Exception:
                desc = {}
            compact.append({
                "name": r.get("name"),
                "topic": desc.get("topic"),
                "host": desc.get("host"),
                "port": desc.get("port"),
                "url": r.get("url"),
                "description": desc.get("description") or desc_raw[:200],
            })
        return {
            "streams": compact,
            "count": len(compact),
            "server": server,
            "_meta": {"tool": "list_kafka_streams", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_kafka_details",
    description=(
        "Get NDP-EP's Kafka broker connection details — broker list, "
        "consumer-group hints, auth requirements. Requires bearer auth."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"streams", "kafka", "status"},
)
async def get_kafka_details() -> dict[str, Any]:
    """Return NDP-EP Kafka broker connection info."""
    try:
        result = await ndp_client._make_request("GET", "/status/kafka-details")
        return {
            "kafka": result,
            "_meta": {"tool": "get_kafka_details", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_system_metrics",
    description=(
        "Get NDP-EP system health metrics (CPU, memory, message rate, "
        "lag). Requires bearer auth."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"status", "metrics"},
)
async def get_system_metrics() -> dict[str, Any]:
    """Return NDP-EP system metrics."""
    try:
        result = await ndp_client._make_request("GET", "/status/metrics")
        return {
            "metrics": result,
            "_meta": {"tool": "get_system_metrics", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="register_derived_stream",
    description=(
        "Register a NEW Kafka topic that filters / derives from an existing "
        "one — the pattern used by the EarthScope GNSS UI to publish per-"
        "station or per-SNCL filtered streams. Wraps NDP-EP's /kafka "
        "registration with a `mapping` field that records the filter. "
        "Requires bearer auth."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False},
    tags={"streams", "kafka", "registration", "write"},
)
async def register_derived_stream(
    dataset_name: Annotated[
        str, Field(description="Unique dataset name for the derived stream")
    ],
    dataset_title: Annotated[str, Field(description="Dataset title")],
    owner_org: Annotated[str, Field(description="Owning organization")],
    source_topic: Annotated[
        str, Field(description="Upstream Kafka topic this is derived from")
    ],
    dest_topic: Annotated[str, Field(description="New Kafka topic to publish to")],
    dest_host: Annotated[str, Field(description="New broker host")],
    dest_port: Annotated[
        int, Field(description="New broker port (1-65535)", ge=1, le=65535)
    ],
    sncl_filter: Annotated[
        str | None,
        Field(description="SNCL-style filter (e.g. 'AGMT.CI.LY.20') — recorded in `mapping`"),
    ] = None,
    extra_filter: Annotated[
        dict[str, Any] | None,
        Field(description="Additional structured filter info, recorded in `mapping`"),
    ] = None,
    server: Annotated[
        str, Field(description="Catalog: 'local' or 'pre_ckan'")
    ] = "local",
) -> dict[str, Any]:
    """Register a derived Kafka stream that filters another."""
    mapping: dict[str, Any] = {"source_topic": source_topic}
    if sncl_filter is not None:
        mapping["sncl_filter"] = sncl_filter
    if extra_filter:
        mapping.update(extra_filter)
    body: dict[str, Any] = {
        "dataset_name": dataset_name,
        "dataset_title": dataset_title,
        "owner_org": owner_org,
        "kafka_topic": dest_topic,
        "kafka_host": dest_host,
        "kafka_port": dest_port,
        "dataset_description": (
            f"Derived from {source_topic}"
            + (f" with SNCL filter {sncl_filter}" if sncl_filter else "")
        ),
        "mapping": mapping,
    }
    try:
        result = await ndp_client._make_request(
            "POST", "/kafka", params={"server": server}, json_data=body
        )
        return {
            "registration": result,
            "derived_topic": dest_topic,
            "source_topic": source_topic,
            "sncl_filter": sncl_filter,
            "server": server,
            "_meta": {"tool": "register_derived_stream", "status": "success"},
        }
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.resource("ndp://catalogs")
def available_catalogs() -> dict[str, Any]:
    """List of available NDP dataset catalogs."""
    return {
        "catalogs": ["global", "local", "pre_ckan"],
        "description": "Available NDP data catalogs",
    }


@mcp.prompt()
def explore_datasets(query: str) -> list[Message]:
    """Guided workflow for discovering and exploring scientific datasets."""
    return [
        Message(
            f"I want to find datasets related to '{query}'. "
            "Search available catalogs, show me the top results, "
            "and provide details on the most relevant one."
        ),
    ]


def main() -> None:
    """Main entry point for the NDP MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="NDP MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

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
        "Discovers and explores scientific datasets from NDP catalogs. "
        "Use search_datasets to find data, get_dataset_details for metadata, "
        "list_catalogs for available sources."
    ),
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

    def __init__(self, base_url: str = "http://155.101.6.191:8003"):
        self.base_url = base_url.rstrip("/")
        self.timeout = httpx.Timeout(30.0)
        self.max_retries = 3
        self.retry_delay = 1.0

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
                    if method.upper() == "GET":
                        response = await client.get(url, params=params)
                    elif method.upper() == "POST":
                        response = await client.post(url, params=params, json=json_data)
                    else:
                        raise ValueError(f"Unsupported HTTP method: {method}")

                    response.raise_for_status()
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
        mcp.run(transport=transport, host=args.host, port=args.port)

    else:
        mcp.run(transport=transport)


if __name__ == "__main__":
    main()

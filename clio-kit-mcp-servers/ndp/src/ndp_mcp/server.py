import asyncio
import csv
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
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
        "Discovers and explores scientific datasets from NDP catalogs and stages "
        "their data for analysis. Use search_datasets to find data, "
        "get_dataset_details for metadata, list_organizations for sources, "
        "stage_resource to download an HTTP(S)/OSDF dataset resource to a local "
        "file, query_arcgis_features to pull features from an ArcGIS FeatureServer "
        "into GeoJSON, and profile_csv_resource / plot_csv_timeseries to inspect "
        "and visualize a staged CSV."
    ),
    list_page_size=10,
)

# ---------------------------------------------------------------------------
# Generic data-retrieval configuration and helpers (standalone, domain-neutral)
# ---------------------------------------------------------------------------

# Default ceiling for direct resource staging to avoid runaway downloads.
_MAX_STAGE_BYTES = 50 * 1024 * 1024
# Network timeouts (seconds) for staging/HTTP feature queries.
_HTTP_CONNECT_TIMEOUT_S = 8.0
_HTTP_READ_TIMEOUT_S = 60.0
_PELICAN_TIMEOUT_S = 900
# Upper bounds that keep tool payloads small enough for agent traces.
_MAX_ARCGIS_FEATURES = 200
_MAX_CSV_PROFILE_ROWS = 250_000

_SIZE_UNITS = {
    "b": 1,
    "byte": 1,
    "bytes": 1,
    "kb": 1024,
    "kib": 1024,
    "mb": 1024 * 1024,
    "mib": 1024 * 1024,
    "gb": 1024 * 1024 * 1024,
    "gib": 1024 * 1024 * 1024,
    "tb": 1024 * 1024 * 1024 * 1024,
    "tib": 1024 * 1024 * 1024 * 1024,
}


def artifacts_root() -> Path:
    """Return the writable root for staged resources and generated artifacts.

    Configurable via the ``CLIO_KIT_ARTIFACTS`` environment variable; otherwise a
    stable per-user temp directory is used. No clio-agent paths are hardcoded.
    """
    configured = os.environ.get("CLIO_KIT_ARTIFACTS", "").strip()
    if configured:
        root = Path(configured).expanduser()
    else:
        root = Path(tempfile.gettempdir()) / "clio-kit-ndp-artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _validate_output_path(candidate: str | Path, *, default_name: str) -> Path:
    """Resolve an output path, confining writes to the configurable artifacts root.

    A relative path, bare filename, or any path outside the artifacts root is
    relocated under the artifacts root using only its filename. This is the
    standalone allowed-root check (no clio-agent file policy dependency).
    """
    root = artifacts_root()
    raw = Path(str(candidate)).expanduser() if candidate else Path(default_name)
    name = raw.name or default_name
    if raw.is_absolute():
        try:
            resolved = raw.resolve()
            resolved.relative_to(root)
            resolved.parent.mkdir(parents=True, exist_ok=True)
            return resolved
        except (ValueError, OSError):
            pass
    target = (root / name).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _safe_filename(value: str, *, default: str) -> str:
    """Return a conservative filesystem name for staged resources."""
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value.strip())
    cleaned = cleaned.strip("._-")
    return cleaned[:120] or default


def _clean_optional_text(value: str | None) -> str | None:
    """Normalize empty strings to absent optional values."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _clean_max_bytes(value: int | str | None) -> int:
    """Normalize an optional byte limit for resource staging."""
    if value is None or value == "":
        return _MAX_STAGE_BYTES
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _MAX_STAGE_BYTES
    return max(1, parsed)


def _parse_resource_size_bytes(value: Any) -> int | None:
    """Parse common resource size strings such as ``1.4 GB``."""
    if isinstance(value, int) and not isinstance(value, bool):
        return value if value >= 0 else None
    if not isinstance(value, str) or not value.strip():
        return None
    parts = value.strip().replace(",", "").split()
    if not parts:
        return None
    try:
        number = float(parts[0])
    except ValueError:
        return None
    unit = parts[1].lower() if len(parts) > 1 else "bytes"
    multiplier = _SIZE_UNITS.get(unit)
    if multiplier is None:
        return None
    return int(number * multiplier)


def _stage_pelican_resource(
    *,
    url: str,
    output_path: Path,
    max_bytes: int,
    resource_size_bytes: int | None,
) -> dict[str, Any]:
    """Stage an OSDF/Pelican resource using the local ``pelican`` CLI when present."""
    if resource_size_bytes is not None and resource_size_bytes > max_bytes:
        raise ToolError(
            f"Resource is advertised as {resource_size_bytes} bytes, exceeding the "
            f"staging limit of {max_bytes} bytes. Increase max_bytes intentionally "
            "or select a smaller object."
        )
    pelican = shutil.which("pelican")
    if pelican is None:
        raise ToolError(
            "The selected resource uses OSDF/Pelican transport, but the `pelican` "
            "CLI was not found on PATH. Install the Pelican client and retry."
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [pelican, "object", "get", url, str(output_path)]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=_PELICAN_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(
            f"Pelican staging timed out after {_PELICAN_TIMEOUT_S}s before the "
            "resource was downloaded."
        ) from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise ToolError(
            f"Pelican failed to stage the resource (exit {completed.returncode}): {stderr[-1200:]}"
        )
    if not output_path.exists():
        raise ToolError("Pelican exited successfully but the expected staged file was not found.")

    size = output_path.stat().st_size if output_path.is_file() else 0
    if size > max_bytes:
        raise ToolError(
            f"Staged file is {size} bytes, exceeding the staging limit of {max_bytes} bytes."
        )
    return {
        "ok": True,
        "local_path": str(output_path),
        "size_bytes": size,
        "content_type": None,
        "url": url,
        "method": "pelican",
        "transport": "osdf",
    }


def _arcgis_layer_query_url(feature_service_url: str, layer_id: int | str | None) -> str:
    """Return an ArcGIS FeatureServer query URL for a service or layer URL."""
    base = feature_service_url.strip().rstrip("/")
    if not base.lower().startswith(("http://", "https://")):
        raise ValueError("feature_service_url must be HTTP(S)")
    if base.lower().endswith("/query"):
        return base
    tail = base.rsplit("/", 1)[-1]
    if tail.isdigit():
        return f"{base}/query"
    selected_layer = str(layer_id if layer_id not in (None, "") else 0).strip()
    if not selected_layer.isdigit():
        raise ValueError("layer_id must be numeric when querying a FeatureServer root")
    return f"{base}/{selected_layer}/query"


def _arcgis_bbox_geometry(
    *,
    min_lon: float | str | None,
    min_lat: float | str | None,
    max_lon: float | str | None,
    max_lat: float | str | None,
) -> dict[str, Any]:
    """Build ArcGIS envelope query params from optional lon/lat bbox values."""
    values = [min_lon, min_lat, max_lon, max_lat]
    if any(value in (None, "") for value in values):
        return {}
    try:
        xmin, ymin, xmax, ymax = (float(str(value)) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError("bbox values must be numeric longitude/latitude values") from exc
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("bbox must satisfy min_lon < max_lon and min_lat < max_lat")
    return {
        "geometry": json.dumps(
            {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "spatialReference": {"wkid": 4326},
            }
        ),
        "geometryType": "esriGeometryEnvelope",
        "inSR": 4326,
        "spatialRel": "esriSpatialRelIntersects",
    }


def _compact_arcgis_geometry(geometry: Any) -> dict[str, Any]:
    """Summarize an ArcGIS geometry for compact agent-facing payloads."""
    if not isinstance(geometry, dict):
        return {}
    if "x" in geometry and "y" in geometry:
        return {"x": geometry.get("x"), "y": geometry.get("y")}
    rings = geometry.get("rings")
    if isinstance(rings, list):
        xs: list[float] = []
        ys: list[float] = []
        for ring in rings[:3]:
            if not isinstance(ring, list):
                continue
            for point in ring[:250]:
                if isinstance(point, list | tuple) and len(point) >= 2:
                    try:
                        xs.append(float(point[0]))
                        ys.append(float(point[1]))
                    except (TypeError, ValueError):
                        continue
        if xs and ys:
            return {"bbox": [min(xs), min(ys), max(xs), max(ys)], "point_count_sampled": len(xs)}
    return {"geometry_keys": sorted(str(key) for key in geometry)[:8]}


def _arcgis_epoch_to_iso(value: Any) -> str | None:
    """Return an ISO UTC timestamp for plausible ArcGIS epoch values."""
    if isinstance(value, bool):
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric <= 0:
        return None
    seconds = numeric / 1000 if numeric > 10_000_000_000 else numeric
    if not 946_684_800 <= seconds <= 4_102_444_800:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _is_arcgis_date_field(name: str) -> bool:
    lowered = name.lower()
    return any(token in lowered for token in ("date", "time", "start", "end", "updated", "expires"))


def _normalize_arcgis_attributes(attributes: Any) -> dict[str, Any]:
    """Add ISO companions for ArcGIS date/time fields while preserving raw values."""
    if not isinstance(attributes, dict):
        return {}
    normalized = dict(attributes)
    for key, value in attributes.items():
        key_text = str(key)
        if not _is_arcgis_date_field(key_text):
            continue
        iso_value = _arcgis_epoch_to_iso(value)
        if iso_value:
            normalized[f"{key_text}_iso"] = iso_value
    return normalized


def _arcgis_feature_collection(features: list[dict[str, Any]]) -> dict[str, Any]:
    """Convert ArcGIS feature rows into a compact GeoJSON-like feature collection."""
    rows: list[dict[str, Any]] = []
    for feature in features:
        if not isinstance(feature, dict):
            continue
        rows.append(
            {
                "type": "Feature",
                "properties": _normalize_arcgis_attributes(feature.get("attributes")),
                "geometry": _compact_arcgis_geometry(feature.get("geometry")),
            }
        )
    return {"type": "FeatureCollection", "features": rows}


def _read_csv_rows(path: Path, *, max_rows: int) -> tuple[list[str], list[dict[str, str]], int]:
    """Read up to ``max_rows`` CSV rows, returning columns, rows, and total scanned."""
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = []
        total = 0
        for row in reader:
            total += 1
            if len(rows) < max_rows:
                rows.append({str(key): str(value or "") for key, value in row.items()})
            if total >= _MAX_CSV_PROFILE_ROWS:
                break
    return columns, rows, total


def _to_float(value: Any) -> float | None:
    """Best-effort float coercion that tolerates blanks and non-numeric text."""
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _parse_datetime_text(value: Any) -> datetime | None:
    """Parse an ISO or common date string into a naive UTC datetime."""
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _infer_csv_plot_x_axis(values: list[str]) -> dict[str, Any]:
    """Infer plot-ready x values and trace metadata from a CSV x column."""
    if not values:
        return {"kind": "row_index", "values": [], "label": "row index", "parse_success_ratio": 0.0}

    numeric: list[float | None] = [_to_float(value) for value in values]
    numeric_values = [value for value in numeric if value is not None and math.isfinite(value)]
    numeric_ratio = len(numeric_values) / len(values)
    if numeric_ratio >= 0.8 and numeric_values:
        median_abs = sorted(abs(value) for value in numeric_values)[len(numeric_values) // 2]
        if median_abs >= 1_000_000_000_000:
            datetimes = [
                datetime.fromtimestamp(value / 1000, timezone.utc).replace(tzinfo=None)
                if value is not None and math.isfinite(value)
                else None
                for value in numeric
            ]
            return {
                "kind": "epoch_milliseconds",
                "values": datetimes,
                "label": "time (UTC)",
                "parse_success_ratio": numeric_ratio,
            }
        if median_abs >= 1_000_000_000:
            datetimes = [
                datetime.fromtimestamp(value, timezone.utc).replace(tzinfo=None)
                if value is not None and math.isfinite(value)
                else None
                for value in numeric
            ]
            return {
                "kind": "epoch_seconds",
                "values": datetimes,
                "label": "time (UTC)",
                "parse_success_ratio": numeric_ratio,
            }

    parsed_datetimes = [_parse_datetime_text(value) for value in values]
    parsed_count = sum(value is not None for value in parsed_datetimes)
    parsed_ratio = parsed_count / len(values)
    if parsed_ratio >= 0.8 and parsed_count:
        return {
            "kind": "datetime",
            "values": parsed_datetimes,
            "label": "time",
            "parse_success_ratio": parsed_ratio,
        }

    return {
        "kind": "categorical",
        "values": list(range(len(values))),
        "labels": values,
        "label": "row index",
        "parse_success_ratio": max(numeric_ratio, parsed_ratio),
    }


def _csv_numeric_summary(
    rows: list[dict[str, str]], columns: list[str]
) -> dict[str, dict[str, Any]]:
    """Return count/min/max/mean for each numeric CSV column."""
    summary: dict[str, dict[str, Any]] = {}
    for column in columns:
        values = [_to_float(row.get(column)) for row in rows]
        numeric = [value for value in values if value is not None]
        if not numeric:
            continue
        summary[column] = {
            "count": len(numeric),
            "min": min(numeric),
            "max": max(numeric),
            "mean": sum(numeric) / len(numeric),
        }
    return summary


def _csv_missing_summary(rows: list[dict[str, str]], columns: list[str]) -> dict[str, int]:
    """Return the count of blank values per column across the profiled rows."""
    return {
        column: sum(1 for row in rows if not str(row.get(column) or "").strip())
        for column in columns
    }


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


@mcp.tool(
    name="stage_resource",
    description=(
        "Download/stage an HTTP(S) or OSDF/Pelican dataset resource to a local "
        "file and return its local_path, size, and content-type."
    ),
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False},
    tags={"datasets", "staging", "download"},
)
async def stage_resource(
    url: Annotated[
        str,
        Field(description="HTTP(S) or osdf:// URL of the dataset resource to stage."),
    ],
    output_name: Annotated[
        str | None,
        Field(description="Optional filename for the staged file; derived from URL if omitted."),
    ] = None,
    max_bytes: Annotated[
        int | str | None,
        Field(description="Maximum download size in bytes (default 50 MiB)."),
    ] = None,
    resource_size_bytes: Annotated[
        int | str | None,
        Field(description="Advertised resource size (bytes or '1.4 GB') for OSDF size checks."),
    ] = None,
) -> dict[str, Any]:
    """Stage a dataset resource to the configurable artifacts root.

    HTTP(S) resources are streamed with a size cap. ``osdf://`` resources are
    staged via the local ``pelican`` CLI when available. Returns ``local_path``,
    ``size_bytes``, and ``content_type``.
    """
    target_url = (url or "").strip()
    if not target_url:
        raise ToolError("A non-empty resource URL is required.")
    scheme_ok = target_url.lower().startswith(("http://", "https://", "osdf://"))
    if not scheme_ok:
        raise ToolError(f"Unsupported resource URL scheme: {target_url}")

    max_stage_bytes = _clean_max_bytes(max_bytes)
    filename_source = output_name or Path(target_url.split("?", 1)[0]).name
    filename = _safe_filename(filename_source, default="ndp-resource")
    output_path = _validate_output_path(filename, default_name="ndp-resource")

    is_osdf = target_url.lower().startswith("osdf://")
    if is_osdf:
        return await asyncio.to_thread(
            _stage_pelican_resource,
            url=target_url,
            output_path=output_path,
            max_bytes=max_stage_bytes,
            resource_size_bytes=_parse_resource_size_bytes(resource_size_bytes),
        )

    timeout = httpx.Timeout(_HTTP_READ_TIMEOUT_S, connect=_HTTP_CONNECT_TIMEOUT_S)
    content_type: str | None = None
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            partial_path = output_path.with_name(f"{output_path.name}.part")
            partial_path.unlink(missing_ok=True)
            async with client.stream("GET", target_url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type")
                content_length = response.headers.get("content-length")
                if content_length:
                    try:
                        advertised = int(content_length)
                    except ValueError:
                        advertised = 0
                    if advertised > max_stage_bytes:
                        raise ToolError(
                            f"Resource is {advertised} bytes, exceeding the staging "
                            f"limit of {max_stage_bytes} bytes. Increase max_bytes "
                            "intentionally or select a smaller resource."
                        )
                total = 0
                with partial_path.open("wb") as handle:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_stage_bytes:
                            handle.close()
                            partial_path.unlink(missing_ok=True)
                            raise ToolError(
                                f"Resource exceeded the staging limit of "
                                f"{max_stage_bytes} bytes while downloading. Increase "
                                "max_bytes intentionally or select a smaller resource."
                            )
                        handle.write(chunk)
            partial_path.replace(output_path)
    except ToolError:
        raise
    except httpx.HTTPError as exc:
        raise ToolError(f"Could not download resource from {target_url}: {exc}") from exc

    size = output_path.stat().st_size
    return {
        "ok": True,
        "local_path": str(output_path),
        "size_bytes": size,
        "content_type": content_type,
        "url": target_url,
        "method": "http",
        "_meta": {"tool": "stage_resource", "status": "success"},
    }


@mcp.tool(
    name="query_arcgis_features",
    description=(
        "Query an ArcGIS FeatureServer layer (with optional lon/lat bbox and where "
        "clause) and write the returned features to a local GeoJSON file."
    ),
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"geospatial", "arcgis", "features"},
)
async def query_arcgis_features(
    feature_service_url: Annotated[
        str,
        Field(description="ArcGIS FeatureServer service, layer, or query URL (HTTP(S))."),
    ],
    layer_id: Annotated[
        int | str | None,
        Field(description="Numeric layer id when querying a FeatureServer root."),
    ] = None,
    where: Annotated[
        str,
        Field(description="ArcGIS SQL where clause (default '1=1')."),
    ] = "1=1",
    out_fields: Annotated[
        str,
        Field(description="Comma-separated output fields or '*' for all."),
    ] = "*",
    max_features: Annotated[
        int | str | None,
        Field(description="Maximum features to return (default 25, capped at 200)."),
    ] = 25,
    min_lon: Annotated[float | str | None, Field(description="Bbox minimum longitude.")] = None,
    min_lat: Annotated[float | str | None, Field(description="Bbox minimum latitude.")] = None,
    max_lon: Annotated[float | str | None, Field(description="Bbox maximum longitude.")] = None,
    max_lat: Annotated[float | str | None, Field(description="Bbox maximum latitude.")] = None,
    output_path: Annotated[
        str | None,
        Field(description="Output GeoJSON path; auto-named under the artifacts root if omitted."),
    ] = None,
) -> dict[str, Any]:
    """Query an ArcGIS FeatureServer layer and persist features as GeoJSON.

    Returns ``{ok, output_path, feature_count, ...}`` and writes a native GeoJSON
    FeatureCollection (ArcGIS ``f=geojson``) to ``output_path``.
    """
    if not output_path and feature_service_url:
        # Auto-name the saved FeatureCollection from the service segment so it can
        # always be resolved downstream without depending on the caller passing one.
        segments = [s for s in str(feature_service_url).split("/") if s]
        service_name = ""
        for index, segment in enumerate(segments):
            if segment.lower() == "featureserver" and index > 0:
                service_name = segments[index - 1]
                break
        if not service_name:
            service_name = next(
                (s for s in reversed(segments) if s and not s.isdigit() and "." not in s),
                "features",
            )
        safe = re.sub(r"[^a-zA-Z0-9]+", "_", service_name).strip("_").lower() or "features"
        output_path = f"{safe}.geojson"

    geojson_name = Path(str(output_path)).name or "features.geojson"
    if not geojson_name.lower().endswith((".geojson", ".json")):
        geojson_name += ".geojson"
    resolved_output = _validate_output_path(geojson_name, default_name="features.geojson")

    try:
        limit = max(1, min(int(max_features or 25), _MAX_ARCGIS_FEATURES))
        params: dict[str, Any] = {
            "f": "json",
            "where": _clean_optional_text(where) or "1=1",
            "outFields": _clean_optional_text(out_fields) or "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultRecordCount": limit,
        }
        params.update(
            _arcgis_bbox_geometry(
                min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat
            )
        )
        query_url = _arcgis_layer_query_url(feature_service_url, layer_id)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc

    timeout = httpx.Timeout(30.0, connect=_HTTP_CONNECT_TIMEOUT_S)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(query_url, params=params)
            response.raise_for_status()
            decoded = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ToolError(f"Could not query ArcGIS FeatureServer resource: {exc}") from exc

    if isinstance(decoded, dict) and decoded.get("error"):
        raise ToolError(
            f"ArcGIS returned an error for the requested feature query: {decoded.get('error')}"
        )
    features = decoded.get("features") if isinstance(decoded, dict) else None
    if not isinstance(features, list):
        raise ToolError("ArcGIS returned no feature list for the requested resource.")

    collection = _arcgis_feature_collection(features)
    # The compact collection above summarizes geometry for agent traces. For the
    # saved file fetch native GeoJSON so downstream renderers get real geometry.
    geo_collection: dict[str, Any] = collection
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            geo_resp = await client.get(query_url, params={**params, "f": "geojson"})
            geo_resp.raise_for_status()
            candidate = geo_resp.json()
            if isinstance(candidate, dict) and candidate.get("type") == "FeatureCollection":
                geo_collection = candidate
    except (httpx.HTTPError, ValueError):
        geo_collection = collection

    resolved_output.write_text(
        json.dumps(geo_collection, sort_keys=True, indent=2, default=str), encoding="utf-8"
    )

    raw_fields = decoded.get("fields") if isinstance(decoded, dict) else []
    fields = raw_fields if isinstance(raw_fields, list) else []
    return {
        "ok": True,
        "source_url": feature_service_url,
        "query_url": str(response.url),
        "output_path": str(resolved_output),
        "output_size_bytes": resolved_output.stat().st_size,
        "feature_count": len(collection["features"]),
        "geometry_type": decoded.get("geometryType") if isinstance(decoded, dict) else None,
        "fields": [
            str(field.get("name"))
            for field in fields
            if isinstance(field, dict) and field.get("name")
        ][:24],
        "features": collection["features"][: min(10, len(collection["features"]))],
        "features_truncated": len(collection["features"]) > 10,
        "_meta": {"tool": "query_arcgis_features", "status": "success"},
    }


@mcp.tool(
    name="profile_csv_resource",
    description="Profile a local CSV: columns, sample rows, numeric stats, and missing values.",
    annotations={"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True},
    tags={"csv", "profiling", "analysis"},
)
async def profile_csv_resource(
    filepath: Annotated[str, Field(description="Path to a local CSV file to profile.")],
    max_rows: Annotated[
        int | str | None,
        Field(description="Maximum rows to retain for stats (default 5000)."),
    ] = 5000,
) -> dict[str, Any]:
    """Profile an arbitrary CSV file with columns, samples, and numeric stats."""
    path = Path(filepath).expanduser()
    if not path.exists() or not path.is_file():
        raise ToolError(f"The CSV file path does not exist or is not a file: {filepath}")
    try:
        limit = max(1, min(int(max_rows or 5000), _MAX_CSV_PROFILE_ROWS))
        columns, rows, row_count = _read_csv_rows(path, max_rows=limit)
    except (OSError, csv.Error, UnicodeDecodeError, ValueError) as exc:
        raise ToolError(f"Could not profile the CSV file: {exc}") from exc

    numeric = _csv_numeric_summary(rows, columns)
    missing = _csv_missing_summary(rows, columns)
    rows_profiled = len(rows)
    return {
        "ok": True,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "columns": columns,
        "column_count": len(columns),
        "rows_examined": row_count,
        "rows_profiled": rows_profiled,
        "rows_scanned": row_count,
        "numeric_summary_rows": rows_profiled,
        "row_scan_cap": _MAX_CSV_PROFILE_ROWS,
        "scan_limited": row_count >= _MAX_CSV_PROFILE_ROWS,
        "profile_limited": row_count > rows_profiled,
        "numeric_summary": numeric,
        "missing_values": missing,
        "missing_values_rows": rows_profiled,
        "missing_values_scope": "profiled_rows",
        "sample_rows": rows[:3],
        "_meta": {"tool": "profile_csv_resource", "status": "success"},
    }


@mcp.tool(
    name="plot_csv_timeseries",
    description="Create a PNG line plot from columns of a local CSV file.",
    annotations={"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    tags={"csv", "plot", "visualization"},
)
async def plot_csv_timeseries(
    filepath: Annotated[str, Field(description="Path to a local CSV file to plot.")],
    x_column: Annotated[str, Field(description="Column to use for the x axis.")],
    y_columns: Annotated[
        list[str] | str,
        Field(description="One or more numeric y columns (list or comma-separated string)."),
    ],
    output_path: Annotated[
        str | None,
        Field(description="Output PNG path; auto-named under the artifacts root if omitted."),
    ] = None,
    max_rows: Annotated[
        int | str | None,
        Field(description="Maximum rows to read for plotting (default 2000)."),
    ] = 2000,
    title: Annotated[str | None, Field(description="Optional plot title.")] = None,
) -> dict[str, Any]:
    """Create a PNG line plot from arbitrary CSV columns."""
    path = Path(filepath).expanduser()
    if not path.exists() or not path.is_file():
        raise ToolError(f"The CSV file path does not exist or is not a file: {filepath}")

    if isinstance(y_columns, str):
        selected_y = [part.strip() for part in y_columns.split(",") if part.strip()]
    else:
        selected_y = [str(part).strip() for part in y_columns if str(part).strip()]
    if not selected_y:
        raise ToolError("At least one y column is required for a CSV plot.")

    default_name = f"{path.stem}_plot.png"
    candidate = output_path or default_name
    output_name = Path(str(candidate)).name or default_name
    if not output_name.lower().endswith(".png"):
        output_name += ".png"
    output = _validate_output_path(output_name, default_name=default_name)

    try:
        row_limit = max(1, min(int(max_rows or 2000), _MAX_CSV_PROFILE_ROWS))
        columns, rows, _ = _read_csv_rows(path, max_rows=row_limit)
    except (OSError, csv.Error, UnicodeDecodeError, ValueError) as exc:
        raise ToolError(f"Could not read the CSV file for plotting: {exc}") from exc

    missing = [column for column in [x_column, *selected_y] if column not in columns]
    if missing:
        raise ToolError(
            f"Requested plot columns are not present in the CSV: {missing}. "
            f"Available columns: {columns}"
        )

    x_values = [row.get(x_column, "") for row in rows]
    x_axis = _infer_csv_plot_x_axis(x_values)
    series: dict[str, list[float | None]] = {
        column: [_to_float(row.get(column)) for row in rows] for column in selected_y
    }
    plotted = {
        column: values for column, values in series.items() if any(v is not None for v in values)
    }
    if not plotted:
        raise ToolError(
            "None of the requested y columns contained numeric values in the scanned rows."
        )

    try:
        import matplotlib as mpl

        mpl.use("Agg")
        import matplotlib.dates as mdates
        import matplotlib.pyplot as plt

        output.parent.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(10, 4.8))
        x_plot_values = x_axis["values"]
        valid_x = [value is not None for value in x_plot_values]
        for column, values in plotted.items():
            xy = [
                (x_value, value)
                for x_value, value, ok in zip(x_plot_values, values, valid_x, strict=False)
                if ok
            ]
            x_series = [item[0] for item in xy]
            y_series = [float("nan") if item[1] is None else item[1] for item in xy]
            ax.plot(x_series, y_series, linewidth=1.2, label=column)
        if x_axis["kind"] in {"epoch_milliseconds", "epoch_seconds", "datetime"}:
            locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
            ax.xaxis.set_major_locator(locator)
            ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
            fig.autofmt_xdate(rotation=30, ha="right")
        else:
            tick_count = min(8, len(x_values))
            if tick_count:
                step = max(1, len(x_values) // tick_count)
                tick_positions = list(range(0, len(x_values), step))[:tick_count]
                tick_labels = x_axis.get("labels", x_values)
                ax.set_xticks(tick_positions)
                ax.set_xticklabels(
                    [tick_labels[index] for index in tick_positions], rotation=35, ha="right"
                )
        ax.set_xlabel(f"{x_column} ({x_axis['label']})")
        ax.set_ylabel(", ".join(plotted))
        ax.set_title(title or path.name)
        ax.grid(alpha=0.25)
        ax.legend(loc="best")
        fig.tight_layout()
        fig.savefig(output, dpi=140)
        plt.close(fig)
    except ToolError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface any plotting/runtime failure uniformly
        raise ToolError(f"Could not create CSV plot artifact: {exc}") from exc

    return {
        "ok": True,
        "path": str(path),
        "output_path": str(output),
        "output_size_bytes": output.stat().st_size,
        "x_column": x_column,
        "x_axis": {
            "kind": x_axis["kind"],
            "label": x_axis["label"],
            "parse_success_ratio": x_axis["parse_success_ratio"],
        },
        "y_columns": sorted(plotted),
        "rows_plotted": len(x_values),
        "_meta": {"tool": "plot_csv_timeseries", "status": "success"},
    }


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

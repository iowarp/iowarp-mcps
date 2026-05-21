# Ndp MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/pypi/v/ndp-mcp.svg)](https://pypi.org/project/ndp-mcp/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

**Part of [CLIO Kit](https://docs.iowarp.ai/) - Gnosis Research Center**

The National Data Platform (NDP) MCP server provides comprehensive access to search and discover datasets across multiple CKAN instances within the National Data Platform ecosystem. This server enables seamless interaction with the NDP API to find scientific datasets, explore organizations, and r...

## Quick Start

```bash
uvx clio-kit mcp-server ndp
```

## Documentation

- **Full Documentation**: [CLIO Kit Website](https://docs.iowarp.ai/)
- **Installation Guide**: See [INSTALLATION.md](../../../CLAUDE.md#setup--installation)
- **Contributing**: See [Contribution Guide](https://github.com/iowarp/clio-kit/wiki/Contribution)

---

## 🛠️ Installation

### Requirements
- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)
- Linux/macOS environment (Windows supported)

<details>
<summary><b>Install in Cursor</b></summary>

Go to: `Settings` -> `Cursor Settings` -> `MCP` -> `Add new global MCP server`

Pasting the following configuration into your Cursor `~/.cursor/mcp.json` file:

```json
{
  "mcpServers": {
    "ndp-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "ndp"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in VS Code</b></summary>

Add the following to your VS Code MCP configuration:

```json
{
  "mcpServers": {
    "ndp-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "ndp"]
    }
  }
}
```

</details>

<details>
<summary><b>Install in Claude Code</b></summary>

Run the following command in your terminal:

```bash
uvx clio-kit mcp-server ndp
```

</details>

<details>
<summary><b>Install in Claude Desktop</b></summary>

Add the following to your `claude_desktop_config.json` file:

```json
{
  "mcpServers": {
    "ndp-mcp": {
      "command": "uvx",
      "args": ["clio-kit", "mcp-server", "ndp"]
    }
  }
}
```

</details>

<details>
<summary><b>Manual Setup</b></summary>

1. Clone the repository:
```bash
git clone https://github.com/iowarp/clio-kit.git
cd clio-kit/clio-kit-mcp-servers/ndp
```

2. Install dependencies using uv:
```bash
uv sync --all-extras --dev
```

3. Run the server:
```bash
uv run python src/server.py
```

</details>

## Capabilities

### `list_organizations`
**Description**: List organizations available in the National Data Platform.
**Hints**: read-only, idempotent
**Tags**: catalogs, organizations

### `search_datasets`
**Description**: Search for datasets in the NDP using term-based or field-specific criteria.
**Hints**: read-only, idempotent
**Tags**: datasets, search

### `get_dataset_details`
**Description**: Retrieve detailed metadata for a specific dataset by ID or name.
**Hints**: read-only, idempotent
**Tags**: datasets, metadata

### `register_dataset`
**Description**: Create a new general dataset in NDP. Requires bearer auth (NDP_BEARER_TOKEN env var). The dataset is created in the specified catalog scope and can then be populated with resources.
**Hints**: destructive
**Tags**: datasets, registration, write

### `register_kafka_topic`
**Description**: Register a Kafka topic as an NDP streaming data source. Requires bearer auth. Creates a dataset entry that points at the topic.
**Hints**: destructive
**Tags**: kafka, registration, streaming, write

### `register_s3_resource`
**Description**: Register an S3-hosted file as an NDP resource. Requires bearer auth. The S3 URL must be reachable from the NDP endpoint.
**Hints**: destructive
**Tags**: registration, resources, s3, write

### `register_url_resource`
**Description**: Register a URL-addressable resource (CSV / JSON / NetCDF / stream / etc.). Requires bearer auth.
**Hints**: destructive
**Tags**: registration, resources, url, write

### `search_resources`
**Description**: Search the NDP resource catalog (across all datasets) by name, URL, format, or free-text query. Returns matching resources with their parent dataset references.
**Hints**: read-only, idempotent
**Tags**: resources, search

### `get_jupyter_details`
**Description**: Fetch JupyterHub workspace connection details for the current user (URL, available kernels, token-handling guidance). Requires bearer auth.
**Hints**: read-only, idempotent
**Tags**: jupyter, status, workspace

### `get_user_info`
**Description**: Return the calling user's identity and authorization claims (name, email, roles, org memberships). Requires bearer auth.
**Hints**: read-only, idempotent
**Tags**: auth, user

### `list_kafka_streams`
**Description**: List Kafka streaming data sources in NDP — host/port/topic of each. Free to call without auth on `server='local'`. Optionally filter by free-text query or topic-name substring.
**Hints**: read-only, idempotent
**Tags**: discovery, kafka, streams

### `get_kafka_details`
**Description**: Get NDP-EP's Kafka broker connection details — broker list, consumer-group hints, auth requirements. Requires bearer auth.
**Hints**: read-only, idempotent
**Tags**: kafka, status, streams

### `get_system_metrics`
**Description**: Get NDP-EP system health metrics (CPU, memory, message rate, lag). Requires bearer auth.
**Hints**: read-only, idempotent
**Tags**: metrics, status

### `register_derived_stream`
**Description**: Register a NEW Kafka topic that filters / derives from an existing one — the pattern used by the EarthScope GNSS UI to publish per-station or per-SNCL filtered streams. Wraps NDP-EP's /kafka registration with a `mapping` field that records the filter. Requires bearer auth.
**Hints**: destructive
**Tags**: kafka, registration, streams, write

### Resources

- `ndp://catalogs` - List of available NDP dataset catalogs.

### Prompts

- **explore_datasets**: Guided workflow for discovering and exploring scientific datasets.
## Claude Code

```bash
claude mcp add clio-ndp -- uvx clio-kit ndp
```

Or install via the CLIO Kit plugin marketplace:

```
/plugin marketplace add iowarp/clio-kit
/plugin install clio-ndp@iowarp-clio-kit
```
## Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "clio-ndp": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "ndp"
      ]
    }
  }
}
```
## Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "clio-ndp": {
      "command": "uvx",
      "args": [
        "clio-kit",
        "ndp"
      ]
    }
  }
}
```

Or install the CLIO Kit extension:

```bash
gemini extensions install https://github.com/iowarp/clio-kit
```
## Examples

### 1. Discover Available Organizations
```
List all organizations in the National Data Platform to see what data is available
```

**Tools called:**
- `list_organizations` - Retrieves all available organizations from the global server

This prompt will:
- Return a comprehensive list of organizations contributing data to NDP
- Show the total count of organizations available
- Provide foundation for targeted dataset searches

### 2. Search for Climate Data from NOAA
```
I want to find climate datasets from NOAA. First show me organizations that contain "noaa" and then search for climate-related datasets from that organization.
```

**Tools called:**
- `list_organizations` - Filters organizations containing "noaa" to verify correct name formatting
- `search_datasets` - Searches for datasets with climate terms from the verified NOAA organization

This prompt will:
- Verify the correct NOAA organization name format
- Find all climate-related datasets published by NOAA
- Return dataset metadata including titles, descriptions, and resource information

### 3. Find CSV Datasets about Temperature Monitoring
```
Find datasets that contain temperature sensor data in CSV format, limit to 10 results
```

**Tools called:**
- `search_datasets` - Searches with advanced parameters for temperature data in CSV format

This prompt will:
- Search across all fields for temperature-related terms
- Filter results to only CSV format resources
- Limit results to 10 datasets to manage response size
- Return detailed metadata for each matching dataset

### 4. Get Complete Information About a Specific Dataset
```
I found a dataset with ID "dataset-12345-climate-temp" in my search. Give me all the details about this dataset including all its resources and metadata.
```

**Tools called:**
- `get_dataset_details` - Retrieves comprehensive information for the specified dataset ID

This prompt will:
- Fetch complete dataset metadata using the provided ID
- Return all associated resources with download URLs and formats
- Provide additional metadata fields and processing information
- Show resource count and detailed descriptions

### 5. Multi-Server Search Workflow
```
Search for oceanographic datasets on both global and local servers, focusing on those from research institutions
```

**Tools called:**
- `list_organizations` - First on global server, then on local server to compare available organizations
- `search_datasets` - Search global server for oceanographic data
- `search_datasets` - Search local server for oceanographic data

This prompt will:
- Compare organization availability across different NDP servers
- Search multiple server instances for comprehensive coverage
- Filter results by research institution organizations
- Provide comparative analysis of dataset availability

### 6. Advanced Filtering for Specific Research Needs
```
Find datasets that have "satellite imagery" in their description, are in NetCDF format, and were published after 2020. Also show me organizations that might have earth observation data.
```

**Tools called:**
- `list_organizations` - Filter organizations that might contain earth observation data
- `search_datasets` - Advanced search with description, format, and timestamp filtering

This prompt will:
- Identify organizations likely to have earth observation datasets
- Use advanced field-specific search parameters
- Filter by resource format and temporal constraints
- Return highly targeted results matching specific research criteria
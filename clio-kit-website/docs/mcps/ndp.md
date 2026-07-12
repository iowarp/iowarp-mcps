---
title: Ndp MCP
description: "NDP MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 3 tools for dataset discovery: list organizations, search datasets, get details. Enables AI agents to discover and access datasets across CKAN instances."
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="Ndp"
  icon="🔧"
  category="Data Processing"
  description="NDP MCP v1.0.0 - Part of CLIO Kit (IoWarp Platform). 3 tools for dataset discovery: list organizations, search datasets, get details. Enables AI agents to discover and access datasets across CKAN instances."
  version="2.2.3"
  actions={["list_organizations", "search_datasets", "get_dataset_details"]}
  platforms={["claude", "cursor", "vscode"]}
  keywords={["ndp", "dataset-search", "ckan", "mcp", "llm-integration", "scientific-data"]}
  license="BSD-3-Clause"
  tools={[{"name": "list_organizations", "description": "List organizations available in the National Data Platform.", "function_name": "list_organizations"}, {"name": "search_datasets", "description": "Search for datasets in the NDP using term-based or field-specific criteria.", "function_name": "search_datasets"}, {"name": "get_dataset_details", "description": "Retrieve detailed metadata for a specific dataset by ID or name.", "function_name": "get_dataset_details"}]}
>

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

</MCPDetail>


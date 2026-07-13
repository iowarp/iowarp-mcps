#!/usr/bin/env python3
"""
Script to automatically generate Docusaurus markdown files for MCP documentation website.
Creates 4 simple sections: General Info, Installation, Available Tools, Examples
"""

import sys
import subprocess
import re
import json
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python
    except ImportError:
        print(
            "Error: tomllib/tomli not available. Please install tomli: pip install tomli"
        )
        sys.exit(1)


# Agentic Search is a first-class CLIO showcase surface, but it is an HTTP/CLI
# service rather than an embedded MCP server. Keep its tile in the same
# generated data without pretending it belongs to the MCP Registry inventory.
NON_MCP_SHOWCASE_ENTRIES = {
    "agentic_search": {
        "name": "Agentic Search",
        "category": "Search & Retrieval",
        "description": (
            "Hybrid retrieval engine. Lexical, vector, graph, and scientific "
            "search over namespaced document corpora. DuckDB storage. FastAPI "
            "service with async job queue."
        ),
        "icon": "🔍",
        "actions": [
            "query",
            "index",
            "list_documents",
            "submit_index_job",
            "get_job_status",
            "cancel_job",
            "health",
            "metrics",
        ],
        "stats": {"version": "1.0.0", "updated": "2026-02-23"},
        "platforms": ["claude", "cursor", "vscode"],
        "slug": "agentic_search",
        "docPath": "/docs/agentic-search",
    }
}


def read_documentation_updated(inventory: dict[str, object]) -> str:
    """Return the explicit deterministic date for generated website metadata."""
    raw_documentation = inventory.get("documentation")
    if not isinstance(raw_documentation, dict):
        raise ValueError("mcp-server-versions.toml must define [documentation]")
    raw_updated = raw_documentation.get("updated")
    if not isinstance(raw_updated, str):
        raise ValueError("documentation.updated must be an ISO date")
    try:
        parsed = date.fromisoformat(raw_updated)
    except ValueError as exc:
        raise ValueError("documentation.updated must be an ISO date") from exc
    if parsed.isoformat() != raw_updated:
        raise ValueError("documentation.updated must use YYYY-MM-DD")
    return raw_updated


class MCPDataExtractor:
    """Extract MCP data from project files."""

    def __init__(self, server_versions: Dict[str, str], updated_date: str):
        self.server_versions = server_versions
        self.updated_date = updated_date
        self.icon_mapping = {
            "adios": "📊",
            "arxiv": "📄",
            "hdf5": "🗂️",
            "pandas": "🐼",
            "parquet": "📋",
            "plot": "📈",
            "darshan": "⚡",
            "slurm": "🖥️",
            "lmod": "📦",
            "node_hardware": "💻",
            "compression": "🗜️",
            "parallel_sort": "🔄",
            "jarvis": "🤖",
            "chronolog": "⏰",
        }

    def extract_mcp_data(self, mcps_dir: Path) -> Dict:
        """Extract data for all MCPs in the directory."""
        mcps_data = {}

        for mcp_dir in sorted(mcps_dir.iterdir(), key=lambda path: path.name):
            if mcp_dir.is_dir() and not mcp_dir.name.startswith("."):
                print(f"Processing MCP: {mcp_dir.name}")
                try:
                    mcp_data = self._extract_single_mcp_data(mcp_dir)
                    if mcp_data:
                        mcps_data[mcp_data["slug"]] = mcp_data
                except Exception as e:
                    print(f"Error processing {mcp_dir.name}: {e}")

        return mcps_data

    def _extract_single_mcp_data(self, mcp_dir: Path) -> Optional[Dict]:
        """Extract data for a single MCP."""
        # Read pyproject.toml
        pyproject_file = mcp_dir / "pyproject.toml"
        if not pyproject_file.exists():
            print(f"Warning: No pyproject.toml found in {mcp_dir.name}")
            return None

        try:
            with open(pyproject_file, "rb") as f:
                pyproject_data = tomllib.load(f)
        except Exception as e:
            print(f"Error reading pyproject.toml in {mcp_dir.name}: {e}")
            return None

        # Extract basic info from pyproject.toml
        project_info = pyproject_data.get("project", {})
        name = (
            project_info.get("name", mcp_dir.name)
            .replace("-mcp", "")
            .replace("_", " ")
            .title()
        )
        description = project_info.get("description", f"{name} MCP server")
        version = self.server_versions[mcp_dir.name]
        keywords = project_info.get("keywords", [])
        license_info = project_info.get("license", "MIT")

        # Determine slug and category
        slug = mcp_dir.name.lower().replace("_", "_").replace("-", "_")
        category = self._determine_category(name, description, keywords)
        icon = self.icon_mapping.get(slug, "🔧")

        # Extract tools from server.py
        tools = self._extract_tools_from_server(mcp_dir)
        actions = [tool["name"] for tool in tools] if tools else []

        return {
            "name": name,
            "slug": slug,
            "category": category,
            "description": description,
            "icon": icon,
            "version": version,
            "actions": actions,
            "tools": tools,
            "platforms": ["claude", "cursor", "vscode"],
            "updated": self.updated_date,
            "path": str(mcp_dir),
            "keywords": keywords,
            "license": license_info,
        }

    def _determine_category(
        self, name: str, description: str, keywords: List[str]
    ) -> str:
        """Determine MCP category based on name, description, and keywords."""
        text = f"{name} {description} {' '.join(keywords)}".lower()

        if any(
            word in text
            for word in ["data", "processing", "pandas", "hdf5", "parquet", "adios"]
        ):
            return "Data Processing"
        elif any(
            word in text
            for word in ["analysis", "visualization", "plot", "chart", "graph"]
        ):
            return "Analysis & Visualization"
        elif any(
            word in text
            for word in ["system", "management", "slurm", "hardware", "node", "jarvis"]
        ):
            return "System Management"
        else:
            return "Utilities"

    def _extract_description_from_readme(self, readme_content: str) -> Optional[str]:
        """Extract a better description from README content."""
        lines = readme_content.split("\n")

        # Look for description after the title
        in_description = False
        description_lines = []

        for line in lines:
            line = line.strip()

            # Skip title and badges
            if line.startswith("#") or line.startswith("[!["):
                continue

            # Start collecting description after badges/title
            if not in_description and line and not line.startswith("#"):
                in_description = True

            if in_description:
                if line.startswith("##") or line.startswith(
                    "# "
                ):  # Stop at next section
                    break
                if line:
                    description_lines.append(line)
                elif description_lines:  # Stop at first empty line after content
                    break

        if description_lines:
            description = " ".join(description_lines)
            # Clean up common patterns
            description = re.sub(r"\*\*([^*]+)\*\*", r"\1", description)  # Remove bold
            description = re.sub(r"`([^`]+)`", r"\1", description)  # Remove code quotes
            description = re.sub(r"\s+", " ", description)  # Normalize whitespace
            return description.strip()

        return None

    def _extract_tools_from_server(self, mcp_dir: Path) -> List[Dict]:
        """Extract tool information by importing the server via FastMCP 3.0 API."""
        script_dir = Path(__file__).parent
        extract_script = script_dir / "extract_mcp_metadata.py"

        try:
            result = subprocess.run(
                ["uv", "run", "python", str(extract_script)],
                cwd=str(mcp_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                print(
                    f"Warning: metadata extraction failed for {mcp_dir.name}: {result.stderr.strip()}"
                )
                return []

            metadata = json.loads(result.stdout)
            return [
                {
                    "name": tool["name"],
                    "description": tool.get("description", f"Tool: {tool['name']}"),
                    "function_name": tool["name"],
                }
                for tool in metadata.get("tools", [])
            ]
        except (
            subprocess.TimeoutExpired,
            json.JSONDecodeError,
            FileNotFoundError,
        ) as e:
            print(f"Warning: could not extract metadata for {mcp_dir.name}: {e}")
            return []


class DocusaurusGenerator:
    """Generate Docusaurus markdown files from MCP data."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.mcps_output_dir = output_dir / "docs" / "mcps"
        self.data_output_dir = output_dir / "src" / "data"

    def generate_all_docs(self, mcps_data: Dict):
        """Generate all documentation files."""
        # Ensure output directories exist
        self.mcps_output_dir.mkdir(parents=True, exist_ok=True)
        self.data_output_dir.mkdir(parents=True, exist_ok=True)

        # Generate individual MCP markdown files
        for slug in sorted(mcps_data):
            mcp_data = mcps_data[slug]
            self._generate_mcp_markdown(mcp_data)

        # Generate mcpData.js file
        self._generate_mcp_data_js(mcps_data)

        print(f"Generated {len(mcps_data)} MCP documentation files")

    def _generate_mcp_markdown(self, mcp_data: Dict):
        """Generate markdown file for a single MCP with 4 sections."""
        output_file = self.mcps_output_dir / f"{mcp_data['slug']}.md"
        base_description = mcp_data["description"]

        # Escape YAML special characters in description
        description = base_description.replace('"', '\\"').replace("\n", " ")
        if len(description) > 300:
            description = description[:297] + "..."

        # Escape quotes in the full description for JSX
        jsx_description = base_description.replace('"', "&quot;").replace("\n", " ")

        # Format JSX props
        actions_jsx = json.dumps(mcp_data["actions"])
        platforms_jsx = json.dumps(mcp_data["platforms"])
        keywords_jsx = json.dumps(mcp_data.get("keywords", []))
        tools_jsx = json.dumps(mcp_data.get("tools", []))

        content = f"""---
title: {mcp_data["name"]} MCP
description: "{description}"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail
  name="{mcp_data["name"]}"
  icon="{mcp_data["icon"]}"
  category="{mcp_data["category"]}"
  description="{jsx_description}"
  version="{mcp_data["version"]}"
  actions={{{actions_jsx}}}
  platforms={{{platforms_jsx}}}
  keywords={{{keywords_jsx}}}
  license="{mcp_data.get("license", "MIT")}"
  tools={{{tools_jsx}}}
>

{self._extract_examples_from_readme(mcp_data)}

</MCPDetail>
"""

        output_file = self.mcps_output_dir / f"{mcp_data['slug']}.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Generated {output_file}")

    def _generate_tools_section(self, mcp_data: Dict) -> str:
        """Generate tools section from extracted data."""
        if not mcp_data["tools"]:
            # Fallback to action list if no detailed tools found
            tools_list = "\n".join(
                [
                    f"- **`{action}`**: {action.replace('_', ' ').title()} functionality"
                    for action in mcp_data["actions"]
                ]
            )
            return f"""
The following tools are available:

{tools_list}

Refer to the MCP server documentation for detailed parameter information.
"""

        tools_content = []
        for tool in mcp_data["tools"]:
            # Clean up description
            description = tool["description"]
            if len(description) > 150:
                description = description[:147] + "..."

            tools_content.append(f"""
### `{tool["name"]}`

{description}

**Usage Example:**
```python
# Use {tool["name"]} function
result = {tool["name"]}()
print(result)
```
""")

        return "\n".join(tools_content)

    def _extract_installation_from_readme(self, mcp_data: Dict) -> str:
        """Extract installation section from README."""
        readme_file = Path(mcp_data["path"]) / "README.md"

        if readme_file.exists():
            try:
                with open(readme_file, "r", encoding="utf-8") as f:
                    readme_content = f.read()

                # Extract installation section from README
                installation = self._extract_section_from_readme(
                    readme_content, "installation"
                )
                if installation:
                    return installation
            except Exception as e:
                print(f"Error reading installation from README: {e}")

        # Return default installation message if not found
        return f"""
### Requirements

- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

### Quick Install

Add this to your MCP client configuration:

```json
{{
  "mcpServers": {{
    "{mcp_data["name"].lower()}-mcp": {{
      "command": "clio-kit",
      "args": ["mcp-server", "{mcp_data["slug"].replace("_", "-")}"]
    }}
  }}
}}
```

Refer to your MCP client documentation for specific setup instructions.
"""

    def _extract_section_from_readme(
        self, readme_content: str, section_name: str
    ) -> str:
        """Extract a specific section from README content."""
        lines = readme_content.split("\n")
        in_section = False
        section_lines = []
        section_level = 0

        for line in lines:
            # Look for section header (with various markdown styles, including emojis)
            header_match = re.match(r"^(#+)\s*", line)
            if header_match and section_name.lower() in line.lower():
                in_section = True
                section_level = len(
                    header_match.group(1)
                )  # Count number of # characters
                continue
            elif in_section and header_match:
                # Stop at next section header of same level or higher (fewer #'s)
                current_level = len(header_match.group(1))
                if current_level <= section_level:
                    break

            if in_section:
                section_lines.append(line)

        if section_lines:
            content = "\n".join(section_lines).strip()
            # Clean up the content - remove trailing problematic content
            content = self._clean_extracted_content(content)
            return content

        return ""

    def _clean_extracted_content(self, content: str) -> str:
        """Clean extracted content to avoid MDX issues."""
        lines = content.split("\n")
        cleaned_lines = []
        in_code_block = False
        code_block_count = 0

        for line in lines:
            # Track code blocks
            if line.strip().startswith("```"):
                if in_code_block:
                    cleaned_lines.append(line)
                    in_code_block = False
                    code_block_count += 1
                else:
                    cleaned_lines.append(line)
                    in_code_block = True
                continue

            # Skip lines that might cause MDX issues
            if line.strip() == "---" and len(cleaned_lines) > 10:
                break
            if "Screenshot" in line or "alt text" in line:
                continue
            if line.strip().startswith("![") and line.strip().endswith(">)"):
                continue

            cleaned_lines.append(line)

        # Ensure any open code blocks are closed
        if in_code_block:
            cleaned_lines.append("```")

        return "\n".join(cleaned_lines).strip()

    def _extract_examples_from_readme(self, mcp_data: Dict) -> str:
        """Extract examples section from README or generate basic examples."""
        readme_file = Path(mcp_data["path"]) / "README.md"

        if readme_file.exists():
            try:
                with open(readme_file, "r", encoding="utf-8") as f:
                    readme_content = f.read()

                # Extract examples section from README
                examples = self._extract_section_from_readme(readme_content, "examples")
                if examples:
                    return examples
            except Exception as e:
                print(f"Error reading examples from README: {e}")

        # Fallback to generated examples
        return self._generate_basic_examples(mcp_data)

    def _generate_basic_examples(self, mcp_data: Dict) -> str:
        """Generate basic examples based on category."""
        name = mcp_data["name"]
        category = mcp_data["category"]

        if "Data Processing" in category:
            return f"""
### Basic Usage
```python
# Load and process data with {name}
data = load_data("input_file")
processed_data = process_data(data)
save_data(processed_data, "output_file")
```

### Integration Example
```python
# Use {name} in a data pipeline
for file in data_files:
    data = load_data(file)
    result = analyze_data(data)
    export_results(result, f"analysis_{{file}}")
```
"""
        elif "System Management" in category:
            return f"""
### System Monitoring
```python
# Monitor system status with {name}
status = get_system_status()
if status.needs_attention:
    send_alert("System requires attention")
```

### Resource Management
```python
# Manage system resources
resources = get_available_resources()
allocate_resources(resources, job_requirements)
```
"""
        else:
            return f"""
### Basic Usage
```python
# Use {name} MCP
result = perform_operation("input_data")
print(f"Result: {{result}}")
```

### Advanced Usage
```python
# Chain multiple operations
data = load_input("source")
processed = process_data(data)
final_result = finalize_output(processed)
```
"""

    def _generate_mcp_data_js(self, mcps_data: Dict):
        """Generate the mcpData.js file for the frontend."""
        # Build only from committed source data. Reading a previous generated
        # file made clean and incremental checkouts produce different output.
        js_mcps = dict(NON_MCP_SHOWCASE_ENTRIES)
        for slug in sorted(mcps_data):
            mcp_data = mcps_data[slug]
            js_mcps[slug] = {
                "name": mcp_data["name"],
                "category": mcp_data["category"],
                "description": mcp_data["description"],
                "icon": mcp_data["icon"],
                "actions": mcp_data["actions"],
                "stats": {
                    "version": mcp_data["version"],
                    "updated": mcp_data["updated"],
                },
                "platforms": mcp_data["platforms"],
                "slug": mcp_data["slug"],
            }

        category_counts = {}
        for showcase_data in js_mcps.values():
            category = showcase_data["category"]
            category_counts[category] = category_counts.get(category, 0) + 1

        # Generate categories object
        categories = {"All": {"count": len(js_mcps), "color": "#6b7280", "icon": "🔍"}}

        category_colors = {
            "Data Processing": "#3b82f6",
            "Analysis & Visualization": "#10b981",
            "System Management": "#f59e0b",
            "Search & Retrieval": "#6366f1",
            "Utilities": "#ef4444",
        }

        category_icons = {
            "Data Processing": "📊",
            "Analysis & Visualization": "📈",
            "System Management": "🖥️",
            "Search & Retrieval": "🔍",
            "Utilities": "🔧",
        }

        for category in sorted(category_counts):
            count = category_counts[category]
            categories[category] = {
                "count": count,
                "color": category_colors.get(category, "#6b7280"),
                "icon": category_icons.get(category, "🔧"),
            }

        # Popular MCPs (those with most actions)
        popular_mcps = sorted(
            js_mcps,
            key=lambda slug: (-len(js_mcps[slug]["actions"]), slug),
        )[:6]

        # Category types for TypeScript/JSDoc
        category_types = {
            "Data Processing": "data",
            "Analysis & Visualization": "analysis",
            "Search & Retrieval": "search",
            "System Management": "system",
            "Utilities": "util",
        }

        # GitHub stats placeholder
        github_stats = {
            "stars": 0,
            "forks": 0,
            "watchers": 0,
            "url": "https://github.com/iowarp/clio-kit",
        }

        # MCP endorsements/badges
        mcp_endorsement = {
            "hdf5": ["flagship", "v1.0"],
            "slurm": ["hpc"],
            "arxiv": ["research"],
            "pandas": ["data"],
        }

        content = f"""// MCP data structure for tile-based showcase
export const mcpData = {json.dumps(js_mcps, indent=2)};

// Categories with counts and colors
export const categories = {json.dumps(categories, indent=2)};

// Popular MCPs for featured section
export const popularMcps = {json.dumps(popular_mcps, indent=2)};

// Category type mappings
export const categoryTypes = {json.dumps(category_types, indent=2)};

// GitHub repository statistics
export const githubStats = {json.dumps(github_stats, indent=2)};

// MCP endorsements and badges
export const mcpEndorsement = {json.dumps(mcp_endorsement, indent=2)};
"""

        output_file = self.data_output_dir / "mcpData.js"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"Generated {output_file}")


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python generate_docs.py <mcps_directory> <docs_output_directory>")
        sys.exit(1)

    mcps_dir = Path(sys.argv[1])
    docs_output_dir = Path(sys.argv[2])

    if not mcps_dir.exists():
        print(f"Error: MCPs directory {mcps_dir} does not exist")
        sys.exit(1)

    try:
        versions_path = mcps_dir.parent / "mcp-server-versions.toml"
        with open(versions_path, "rb") as stream:
            inventory = tomllib.load(stream)
        server_versions = inventory["servers"]
        updated_date = read_documentation_updated(inventory)
        discovered_servers = {
            path.name
            for path in mcps_dir.iterdir()
            if (path / "pyproject.toml").is_file()
        }
        if set(server_versions) != discovered_servers:
            raise ValueError(
                "MCP documentation inventory differs from mcp-server-versions.toml"
            )

        # Extract MCP data using each public agent-contract version.
        extractor = MCPDataExtractor(server_versions, updated_date)
        mcps_data = extractor.extract_mcp_data(mcps_dir)

        if not mcps_data:
            print("Error: No MCPs found or processed")
            sys.exit(1)

        # Generate documentation
        generator = DocusaurusGenerator(docs_output_dir)
        generator.generate_all_docs(mcps_data)

        print(f"Successfully generated documentation for {len(mcps_data)} MCPs!")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

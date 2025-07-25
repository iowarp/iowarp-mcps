#!/usr/bin/env python3
"""
Script to automatically generate Docusaurus markdown files for MCP documentation website.
Creates 4 simple sections: General Info, Installation, Available Tools, Examples
"""

import os
import sys
import ast
import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # Fallback for older Python
    except ImportError:
        print("Error: tomllib/tomli not available. Please install tomli: pip install tomli")
        sys.exit(1)


class MCPDataExtractor:
    """Extract MCP data from project files."""
    
    def __init__(self):
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
            "chronolog": "⏰"
        }

    def extract_mcp_data(self, mcps_dir: Path) -> Dict:
        """Extract data for all MCPs in the directory."""
        mcps_data = {}
        
        for mcp_dir in mcps_dir.iterdir():
            if mcp_dir.is_dir() and not mcp_dir.name.startswith('.'):
                print(f"Processing MCP: {mcp_dir.name}")
                try:
                    mcp_data = self._extract_single_mcp_data(mcp_dir)
                    if mcp_data:
                        mcps_data[mcp_data['slug']] = mcp_data
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
            with open(pyproject_file, 'rb') as f:
                pyproject_data = tomllib.load(f)
        except Exception as e:
            print(f"Error reading pyproject.toml in {mcp_dir.name}: {e}")
            return None
        
        # Extract basic info from pyproject.toml
        project_info = pyproject_data.get('project', {})
        name = project_info.get('name', mcp_dir.name).replace('-mcp', '').replace('_', ' ').title()
        description = project_info.get('description', f'{name} MCP server')
        version = project_info.get('version', '1.0.0')
        keywords = project_info.get('keywords', [])
        license_info = project_info.get('license', 'MIT')
        
        # Determine slug and category
        slug = mcp_dir.name.lower().replace('_', '_').replace('-', '_')
        category = self._determine_category(name, description, keywords)
        icon = self.icon_mapping.get(slug, "🔧")
        
        # Read README.md for enhanced description
        readme_file = mcp_dir / "README.md"
        enhanced_description = description
        
        if readme_file.exists():
            try:
                with open(readme_file, 'r', encoding='utf-8') as f:
                    readme_content = f.read()
                enhanced_description = self._extract_description_from_readme(readme_content) or description
            except Exception as e:
                print(f"Error reading README.md in {mcp_dir.name}: {e}")
        
        # Extract tools from server.py
        tools = self._extract_tools_from_server(mcp_dir)
        actions = [tool['name'] for tool in tools] if tools else []
        
        return {
            'name': name,
            'slug': slug,
            'category': category,
            'description': enhanced_description,
            'icon': icon,
            'version': version,
            'actions': actions,
            'tools': tools,
            'platforms': ["claude", "cursor", "vscode"],
            'updated': datetime.now().strftime("%Y-%m-%d"),
            'path': str(mcp_dir),
            'keywords': keywords,
            'license': license_info
        }
    
    def _determine_category(self, name: str, description: str, keywords: List[str]) -> str:
        """Determine MCP category based on name, description, and keywords."""
        text = f"{name} {description} {' '.join(keywords)}".lower()
        
        if any(word in text for word in ['data', 'processing', 'pandas', 'hdf5', 'parquet', 'adios']):
            return "Data Processing"
        elif any(word in text for word in ['analysis', 'visualization', 'plot', 'chart', 'graph']):
            return "Analysis & Visualization"
        elif any(word in text for word in ['system', 'management', 'slurm', 'hardware', 'node', 'jarvis']):
            return "System Management"
        else:
            return "Utilities"
    
    def _extract_description_from_readme(self, readme_content: str) -> Optional[str]:
        """Extract a better description from README content."""
        lines = readme_content.split('\n')
        
        # Look for description after the title
        in_description = False
        description_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip title and badges
            if line.startswith('#') or line.startswith('[!['):
                continue
            
            # Start collecting description after badges/title
            if not in_description and line and not line.startswith('#'):
                in_description = True
            
            if in_description:
                if line.startswith('##') or line.startswith('# '):  # Stop at next section
                    break
                if line:
                    description_lines.append(line)
                elif description_lines:  # Stop at first empty line after content
                    break
        
        if description_lines:
            description = ' '.join(description_lines)
            # Clean up common patterns
            description = re.sub(r'\*\*([^*]+)\*\*', r'\1', description)  # Remove bold
            description = re.sub(r'`([^`]+)`', r'\1', description)  # Remove code quotes
            description = re.sub(r'\s+', ' ', description)  # Normalize whitespace
            return description.strip()
        
        return None
    
    def _extract_tools_from_server(self, mcp_dir: Path) -> List[Dict]:
        """Extract tool information from server.py files."""
        server_files = list(mcp_dir.glob("src/**/server.py"))
        
        tools = []
        for server_file in server_files:
            try:
                with open(server_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        tool_info = self._extract_tool_from_function(node)
                        if tool_info:
                            tools.append(tool_info)
            
            except Exception as e:
                print(f"Error parsing {server_file}: {e}")
        
        return tools
    
    def _extract_tool_from_function(self, node) -> Optional[Dict]:
        """Extract tool information from a function node."""
        # Check for @mcp.tool decorator
        for decorator in node.decorator_list:
            if self._is_mcp_tool_decorator(decorator):
                name = self._extract_decorator_name(decorator) or node.name
                description = self._extract_decorator_description(decorator)
                
                # Get enhanced description from docstring
                docstring = ast.get_docstring(node)
                if docstring and not description:
                    description = docstring.split('\n')[0].strip()
                
                return {
                    'name': name,
                    'description': description or f"Tool: {name}",
                    'function_name': node.name
                }
        
        return None
    
    def _is_mcp_tool_decorator(self, decorator) -> bool:
        """Check if decorator is @mcp.tool."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return (decorator.func.attr == 'tool' and 
                       isinstance(decorator.func.value, ast.Name) and 
                       decorator.func.value.id == 'mcp')
        elif isinstance(decorator, ast.Attribute):
            return (decorator.attr == 'tool' and 
                   isinstance(decorator.value, ast.Name) and 
                   decorator.value.id == 'mcp')
        return False
    
    def _extract_decorator_name(self, decorator) -> Optional[str]:
        """Extract name from decorator arguments."""
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == 'name' and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
        return None
    
    def _extract_decorator_description(self, decorator) -> Optional[str]:
        """Extract description from decorator arguments."""
        if isinstance(decorator, ast.Call):
            for keyword in decorator.keywords:
                if keyword.arg == 'description' and isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
        return None


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
        for slug, mcp_data in mcps_data.items():
            self._generate_mcp_markdown(mcp_data)
        
        # Generate mcpData.js file
        self._generate_mcp_data_js(mcps_data)
        
        print(f"Generated {len(mcps_data)} MCP documentation files")
    
    def _generate_mcp_markdown(self, mcp_data: Dict):
        """Generate markdown file for a single MCP with 4 sections."""
        # Escape YAML special characters in description
        description = mcp_data['description'].replace('"', '\\"').replace('\n', ' ')
        if len(description) > 300:
            description = description[:297] + "..."
        
        # Escape quotes in the full description for JSX
        jsx_description = mcp_data['description'].replace('"', '&quot;').replace('\n', ' ')
        
        # Format JSX props
        actions_jsx = json.dumps(mcp_data['actions'])
        platforms_jsx = json.dumps(mcp_data['platforms'])
        keywords_jsx = json.dumps(mcp_data.get('keywords', []))
        tools_jsx = json.dumps(mcp_data.get('tools', []))
        
        content = f"""---
title: {mcp_data['name']} MCP
description: "{description}"
---

import MCPDetail from '@site/src/components/MCPDetail';

<MCPDetail 
  name="{mcp_data['name']}"
  icon="{mcp_data['icon']}"
  category="{mcp_data['category']}"
  description="{jsx_description}"
  version="{mcp_data['version']}"
  actions={{{actions_jsx}}}
  platforms={{{platforms_jsx}}}
  keywords={{{keywords_jsx}}}
  license="{mcp_data.get('license', 'MIT')}"
  tools={{{tools_jsx}}}
>

{self._extract_examples_from_readme(mcp_data)}

</MCPDetail>

"""
        
        output_file = self.mcps_output_dir / f"{mcp_data['slug']}.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Generated {output_file}")
    
    def _generate_tools_section(self, mcp_data: Dict) -> str:
        """Generate tools section from extracted data."""
        if not mcp_data['tools']:
            # Fallback to action list if no detailed tools found
            tools_list = '\n'.join([f"- **`{action}`**: {action.replace('_', ' ').title()} functionality" 
                                  for action in mcp_data['actions']])
            return f"""
The following tools are available:

{tools_list}

Refer to the MCP server documentation for detailed parameter information.
"""
        
        tools_content = []
        for tool in mcp_data['tools']:
            # Clean up description
            description = tool['description']
            if len(description) > 150:
                description = description[:147] + "..."
            
            tools_content.append(f"""
### `{tool['name']}`

{description}

**Usage Example:**
```python
# Use {tool['name']} function
result = {tool['name']}()
print(result)
```
""")
        
        return '\n'.join(tools_content)
    
    def _extract_installation_from_readme(self, mcp_data: Dict) -> str:
        """Extract installation section from README."""
        readme_file = Path(mcp_data['path']) / "README.md"
        
        if readme_file.exists():
            try:
                with open(readme_file, 'r', encoding='utf-8') as f:
                    readme_content = f.read()
                
                # Extract installation section from README
                installation = self._extract_section_from_readme(readme_content, "installation")
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
    "{mcp_data['name'].lower()}-mcp": {{
      "command": "uvx",
      "args": ["iowarp-mcps", "{mcp_data['slug'].replace('_', '-')}"]
    }}
  }}
}}
```

Refer to your MCP client documentation for specific setup instructions.
"""
    
    def _extract_section_from_readme(self, readme_content: str, section_name: str) -> str:
        """Extract a specific section from README content."""
        lines = readme_content.split('\n')
        in_section = False
        section_lines = []
        section_level = 0
        
        for line in lines:
            # Look for section header (with various markdown styles, including emojis)
            header_match = re.match(r'^(#+)\s*', line)
            if header_match and section_name.lower() in line.lower():
                in_section = True
                section_level = len(header_match.group(1))  # Count number of # characters
                continue
            elif in_section and header_match:
                # Stop at next section header of same level or higher (fewer #'s)
                current_level = len(header_match.group(1))
                if current_level <= section_level:
                    break
            
            if in_section:
                section_lines.append(line)
        
        if section_lines:
            content = '\n'.join(section_lines).strip()
            # Clean up the content - remove trailing problematic content
            content = self._clean_extracted_content(content)
            return content
        
        return ""
    
    def _clean_extracted_content(self, content: str) -> str:
        """Clean extracted content to avoid MDX issues."""
        lines = content.split('\n')
        cleaned_lines = []
        in_code_block = False
        code_block_count = 0
        
        for line in lines:
            # Track code blocks
            if line.strip().startswith('```'):
                if in_code_block:
                    cleaned_lines.append(line)
                    in_code_block = False
                    code_block_count += 1
                else:
                    cleaned_lines.append(line)
                    in_code_block = True
                continue
            
            # Skip lines that might cause MDX issues
            if line.strip() == '---' and len(cleaned_lines) > 10:
                break
            if 'Screenshot' in line or 'alt text' in line:
                continue
            if line.strip().startswith('![') and line.strip().endswith('>)'):
                continue
            
            cleaned_lines.append(line)
        
        # Ensure any open code blocks are closed
        if in_code_block:
            cleaned_lines.append('```')
        
        return '\n'.join(cleaned_lines).strip()
    
    def _extract_examples_from_readme(self, mcp_data: Dict) -> str:
        """Extract examples section from README or generate basic examples."""
        readme_file = Path(mcp_data['path']) / "README.md"
        
        if readme_file.exists():
            try:
                with open(readme_file, 'r', encoding='utf-8') as f:
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
        name = mcp_data['name']
        category = mcp_data['category']
        
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
        # Count categories
        category_counts = {}
        for mcp_data in mcps_data.values():
            category = mcp_data['category']
            category_counts[category] = category_counts.get(category, 0) + 1
        
        # Generate JavaScript object
        js_mcps = {}
        for slug, mcp_data in mcps_data.items():
            js_mcps[slug] = {
                'name': mcp_data['name'],
                'category': mcp_data['category'],
                'description': mcp_data['description'],
                'icon': mcp_data['icon'],
                'actions': mcp_data['actions'],
                'stats': {
                    'version': mcp_data['version'],
                    'updated': mcp_data['updated']
                },
                'platforms': mcp_data['platforms'],
                'slug': mcp_data['slug']
            }
        
        # Generate categories object
        categories = {
            "All": {
                "count": len(mcps_data),
                "color": "#6b7280",
                "icon": "🔍"
            }
        }
        
        category_colors = {
            "Data Processing": "#3b82f6",
            "Analysis & Visualization": "#10b981", 
            "System Management": "#f59e0b",
            "Utilities": "#ef4444"
        }
        
        category_icons = {
            "Data Processing": "📊",
            "Analysis & Visualization": "📈",
            "System Management": "🖥️", 
            "Utilities": "🔧"
        }
        
        for category, count in category_counts.items():
            categories[category] = {
                "count": count,
                "color": category_colors.get(category, "#6b7280"),
                "icon": category_icons.get(category, "🔧")
            }
        
        # Popular MCPs (those with most actions)
        popular_mcps = sorted(mcps_data.keys(), 
                            key=lambda k: len(mcps_data[k]['actions']), 
                            reverse=True)[:6]
        
        content = f"""// MCP data structure for tile-based showcase
export const mcpData = {json.dumps(js_mcps, indent=2)};

// Categories with counts and colors
export const categories = {json.dumps(categories, indent=2)};

// Popular MCPs for featured section
export const popularMcps = {json.dumps(popular_mcps, indent=2)};
"""
        
        output_file = self.data_output_dir / "mcpData.js"
        with open(output_file, 'w', encoding='utf-8') as f:
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
        # Extract MCP data
        extractor = MCPDataExtractor()
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
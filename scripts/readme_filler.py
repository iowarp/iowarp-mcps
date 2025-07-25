#!/usr/bin/env python3
"""
Script to automatically update README files for all MCP servers in the mcps/ directory.
Parses docstrings from server.py files and updates the Capabilities section in README.md files.
"""

import os
import sys
import ast
import re
import glob
from typing import Dict, List, Tuple, Optional
from pathlib import Path


class DocstringParser:
    """Parse docstrings from Python AST to extract function information."""
    
    def __init__(self):
        self.tools = []
        self.resources = []
        self.prompts = []
    
    def parse_server_file(self, file_path: str) -> Dict[str, List[Dict]]:
        """Parse a server.py file and extract tool, resource, and prompt information."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            tools = []
            resources = []
            prompts = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Check for @mcp.tool decorator
                    tool_info = self._extract_tool_info(node)
                    if tool_info:
                        tools.append(tool_info)
                    
                    # Check for @mcp.resource decorator
                    resource_info = self._extract_resource_info(node)
                    if resource_info:
                        resources.append(resource_info)
                    
                    # Check for @mcp.prompt decorator
                    prompt_info = self._extract_prompt_info(node)
                    if prompt_info:
                        prompts.append(prompt_info)
            
            return {
                'tools': tools,
                'resources': resources,
                'prompts': prompts
            }
        
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            return {'tools': [], 'resources': [], 'prompts': []}
    
    def _extract_tool_info(self, node) -> Optional[Dict]:
        """Extract tool information from a function with @mcp.tool decorator."""
        for decorator in node.decorator_list:
            if self._is_mcp_decorator(decorator, 'tool'):
                return self._parse_function_details(node, decorator)
        return None
    
    def _extract_resource_info(self, node) -> Optional[Dict]:
        """Extract resource information from a function with @mcp.resource decorator."""
        for decorator in node.decorator_list:
            if self._is_mcp_decorator(decorator, 'resource'):
                return self._parse_function_details(node, decorator)
        return None
    
    def _extract_prompt_info(self, node) -> Optional[Dict]:
        """Extract prompt information from a function with @mcp.prompt decorator."""
        for decorator in node.decorator_list:
            if self._is_mcp_decorator(decorator, 'prompt'):
                return self._parse_function_details(node, decorator)
        return None
    
    def _is_mcp_decorator(self, decorator, decorator_type: str) -> bool:
        """Check if decorator is an MCP decorator of the specified type."""
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                return (decorator.func.attr == decorator_type and 
                       isinstance(decorator.func.value, ast.Name) and 
                       decorator.func.value.id == 'mcp')
        elif isinstance(decorator, ast.Attribute):
            # Handle case like @mcp.tool without parentheses
            return (decorator.attr == decorator_type and 
                   isinstance(decorator.value, ast.Name) and 
                   decorator.value.id == 'mcp')
        return False
    
    def _parse_function_details(self, node, decorator) -> Dict:
        """Parse function details including name, description, parameters, and returns."""
        # Extract name from decorator
        name = self._extract_decorator_name(decorator)
        if not name:
            name = node.name.replace('_tool', '').replace('_handler', '')
        
        # Extract description from decorator
        description = self._extract_decorator_description(decorator)
        
        # Extract enhanced description from docstring
        enhanced_description = self._extract_enhanced_description_from_docstring(node)
        
        # Use enhanced description if available, otherwise use decorator description
        final_description = enhanced_description or description or "No description available"
        
        # Extract parameters and returns from docstring and function signature
        params, returns = self._parse_docstring_params_and_returns(node)
        
        # If no parameters from docstring, extract from function signature
        if not params:
            params = self._extract_function_signature_params(node)
        
        # If no returns from docstring, extract from function signature
        if not returns:
            returns = self._extract_function_return_type(node)
        
        return {
            'name': name,
            'description': final_description,
            'parameters': params,
            'returns': returns
        }
    
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
    
    def _extract_enhanced_description_from_docstring(self, node) -> Optional[str]:
        """Extract enhanced description from function docstring (first line or summary)."""
        if not node.args or not ast.get_docstring(node):
            return None
        
        docstring = ast.get_docstring(node)
        if not docstring:
            return None
        
        # Look for a description in the docstring - usually the first paragraph
        lines = docstring.strip().split('\n')
        description_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                break  # Stop at first empty line
            if line.startswith('Args:') or line.startswith('Parameters:') or line.startswith('Returns:'):
                break  # Stop at parameters section
            description_lines.append(line)
        
        if description_lines:
            return ' '.join(description_lines)
        
        return None
    
    def _parse_docstring_params_and_returns(self, node) -> Tuple[List[Dict], str]:
        """Parse parameters and returns from function docstring."""
        docstring = ast.get_docstring(node)
        if not docstring:
            return [], ""
        
        params = []
        returns = ""
        
        lines = docstring.split('\n')
        current_section = None
        current_param = None
        
        for line in lines:
            line = line.strip()
            
            # Detect sections
            if line.startswith('Args:') or line.startswith('Parameters:'):
                current_section = 'params'
                continue
            elif line.startswith('Returns:'):
                current_section = 'returns'
                continue
            elif line.startswith('Raises:') or line.startswith('Note:') or line.startswith('Example:'):
                current_section = None
                continue
            
            if current_section == 'params' and line:
                # Parse parameter line like "param_name (type): description"
                param_match = re.match(r'(\w+)\s*\(([^)]+)\):\s*(.+)', line)
                if param_match:
                    param_name, param_type, param_desc = param_match.groups()
                    
                    # Check if optional
                    optional = 'optional' in param_desc.lower() or 'none' in param_type.lower()
                    
                    params.append({
                        'name': param_name,
                        'type': param_type,
                        'description': param_desc,
                        'optional': optional
                    })
                    current_param = params[-1]
                elif current_param and line.startswith('-') or line.startswith(' '):
                    # Continuation of previous parameter description
                    current_param['description'] += ' ' + line.lstrip('- ')
            
            elif current_section == 'returns' and line:
                returns += line + ' '
        
        return params, returns.strip()
    
    def _extract_function_signature_params(self, node) -> List[Dict]:
        """Extract parameters from function signature."""
        params = []
        
        # Skip 'self' parameter if present
        args = node.args.args
        if args and args[0].arg in ['self', 'cls']:
            args = args[1:]
        
        # Get default values
        defaults = node.args.defaults
        num_defaults = len(defaults)
        num_args = len(args)
        
        for i, arg in enumerate(args):
            param_name = arg.arg
            
            # Determine if parameter has a default (is optional)
            has_default = i >= (num_args - num_defaults)
            
            # Extract type annotation if available
            param_type = "Any"
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    param_type = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    param_type = str(arg.annotation.value)
                elif hasattr(arg.annotation, 'id'):
                    param_type = arg.annotation.id
                else:
                    param_type = "Any"
            
            # Get default value if available
            default_value = None
            if has_default:
                default_idx = i - (num_args - num_defaults)
                default_node = defaults[default_idx]
                if isinstance(default_node, ast.Constant):
                    default_value = default_node.value
                elif isinstance(default_node, ast.Name) and default_node.id == 'None':
                    default_value = None
                else:
                    default_value = "..."
            
            # Create parameter description
            description = f"Parameter for {param_name}"
            if default_value is not None:
                description += f" (default: {default_value})"
            
            params.append({
                'name': param_name,
                'type': param_type,
                'description': description,
                'optional': has_default
            })
        
        return params
    
    def _extract_function_return_type(self, node) -> str:
        """Extract return type from function signature."""
        if node.returns:
            if isinstance(node.returns, ast.Name):
                return f"Returns {node.returns.id}"
            elif isinstance(node.returns, ast.Constant):
                return f"Returns {node.returns.value}"
            else:
                return "Returns data"
        return "Returns data"


class ReadmeUpdater:
    """Update README files with capabilities extracted from server.py files."""
    
    def __init__(self):
        self.parser = DocstringParser()
    
    def update_all_mcps(self, mcps_dir: str):
        """Update README files for all MCP servers in the directory."""
        mcps_path = Path(mcps_dir)
        
        if not mcps_path.exists():
            raise FileNotFoundError(f"Directory {mcps_dir} does not exist")
        
        for mcp_dir in mcps_path.iterdir():
            if mcp_dir.is_dir():
                print(f"Processing MCP server: {mcp_dir.name}")
                try:
                    self.update_mcp_readme(mcp_dir)
                except Exception as e:
                    print(f"Error processing {mcp_dir.name}: {e}")
    
    def update_mcp_readme(self, mcp_dir: Path):
        """Update README file for a single MCP server."""
        # Find server.py file
        server_file = self._find_server_file(mcp_dir)
        if not server_file:
            raise FileNotFoundError(f"No server.py file found in src/ folder for {mcp_dir.name}. Server file must be located in src/ directory.")
        
        # Parse capabilities
        capabilities = self.parser.parse_server_file(str(server_file))
        
        # Find README file
        readme_file = mcp_dir / "README.md"
        if not readme_file.exists():
            print(f"Warning: README.md not found in {mcp_dir}, skipping")
            return
        
        # Update README
        self._update_readme_content(readme_file, capabilities)
        print(f"Updated README for {mcp_dir.name}")
    
    def _find_server_file(self, mcp_dir: Path) -> Optional[Path]:
        """Find the server.py file in the MCP directory. Must be inside src/ folder."""
        # Only look for server.py files inside src/ directory
        patterns = [
            "src/server.py",
            "src/*/server.py"
        ]
        
        for pattern in patterns:
            matches = list(mcp_dir.glob(pattern))
            if matches:
                # Verify that the found file is actually in a src/ directory
                server_file = matches[0]
                if "src" in server_file.parts:
                    return server_file
        
        return None
    
    def _update_readme_content(self, readme_file: Path, capabilities: Dict):
        """Update the README file content with new capabilities."""
        with open(readme_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Generate new capabilities section
        new_capabilities_section = self._generate_capabilities_section(capabilities)
        
        # Find and replace the capabilities section
        updated_content = self._replace_capabilities_section(content, new_capabilities_section)
        
        # Write back to file
        with open(readme_file, 'w', encoding='utf-8') as f:
            f.write(updated_content)
    
    def _generate_capabilities_section(self, capabilities: Dict) -> str:
        """Generate the capabilities section content."""
        sections = []
        
        # Add tools section
        if capabilities['tools']:
            sections.append("## Capabilities\n")
            for tool in capabilities['tools']:
                sections.append(self._format_capability_entry(tool))
        
        # Add resources section
        if capabilities['resources']:
            if not sections:
                sections.append("## Capabilities\n")
            sections.append("### Resources\n")
            for resource in capabilities['resources']:
                sections.append(self._format_capability_entry(resource))
        
        # Add prompts section
        if capabilities['prompts']:
            if not sections:
                sections.append("## Capabilities\n")
            sections.append("### Prompts\n")
            for prompt in capabilities['prompts']:
                sections.append(self._format_capability_entry(prompt))
        
        return '\n'.join(sections)
    
    def _format_capability_entry(self, capability: Dict) -> str:
        """Format a single capability entry following the Arxiv example."""
        lines = []
        
        # Function name header
        lines.append(f"### `{capability['name']}`")
        
        # Description
        lines.append(f"**Description**: {capability['description']}")
        lines.append("")
        
        # Parameters
        if capability['parameters']:
            lines.append("**Parameters**:")
            for param in capability['parameters']:
                optional_text = ", optional" if param.get('optional') else ""
                lines.append(f"- `{param['name']}` ({param['type']}{optional_text}): {param['description']}")
            lines.append("")
        
        # Returns
        if capability['returns']:
            lines.append(f"**Returns**: {capability['returns']}")
            lines.append("")
        
        return '\n'.join(lines)
    
    def _replace_capabilities_section(self, content: str, new_section: str) -> str:
        """Replace the capabilities section in the README content while preserving everything else."""
        # Pattern to match from ## Capabilities to the next ## section or end of file
        pattern = r'## Capabilities.*?(?=\n## |\Z)'
        
        if re.search(pattern, content, re.DOTALL):
            # Replace existing capabilities section, preserving the rest
            return re.sub(pattern, new_section.rstrip(), content, flags=re.DOTALL)
        else:
            # If no capabilities section exists, try to insert before ## Examples
            examples_match = re.search(r'\n(## Examples)', content)
            if examples_match:
                # Insert before Examples section
                before_examples = content[:examples_match.start(1)]
                examples_and_after = content[examples_match.start(1):]
                return f"{before_examples}\n{new_section}\n\n{examples_and_after}"
            else:
                # Look for any other ## section to insert before
                section_match = re.search(r'\n(## [^C])', content)  # Any section not starting with 'C' to avoid Capabilities
                if section_match:
                    before_section = content[:section_match.start(1)]
                    section_and_after = content[section_match.start(1):]
                    return f"{before_section}\n{new_section}\n\n{section_and_after}"
                else:
                    # If no other sections, append at the end
                    return content.rstrip() + f"\n\n{new_section}"


def main():
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python update_readme_capabilities.py <mcps_directory>")
        sys.exit(1)
    
    mcps_dir = sys.argv[1]
    
    try:
        updater = ReadmeUpdater()
        updater.update_all_mcps(mcps_dir)
        print("Successfully updated all README files!")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
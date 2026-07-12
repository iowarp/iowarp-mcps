#!/usr/bin/env python3
"""Update README files for all MCP servers using live FastMCP metadata.

Imports each server via extract_mcp_metadata.py and updates the Capabilities,
Claude Code, Claude Desktop, and Gemini CLI sections in each server's README.md.

Usage:
    python scripts/readme_filler.py clio-kit-mcp-servers
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def extract_metadata(mcp_dir: Path) -> dict[str, Any] | None:
    """Extract metadata from an MCP server by running it in its own venv."""
    script_path = Path(__file__).parent / "extract_mcp_metadata.py"
    try:
        result = subprocess.run(
            ["uv", "run", "python", str(script_path)],
            cwd=str(mcp_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            print(f"  Warning: extraction failed: {result.stderr.strip()[:200]}")
            return None
        return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        print(f"  Warning: could not extract metadata: {e}")
        return None


def format_capabilities_section(metadata: dict[str, Any]) -> str:
    """Generate the ## Capabilities markdown section from metadata."""
    lines: list[str] = ["## Capabilities\n"]

    # Tools
    tools = metadata.get("tools", [])
    if tools:
        for tool in tools:
            lines.append(f"### `{tool['name']}`")
            lines.append(f"**Description**: {tool['description']}")
            annotations = tool.get("annotations", {})
            hints = []
            if annotations.get("readOnlyHint"):
                hints.append("read-only")
            if annotations.get("destructiveHint"):
                hints.append("destructive")
            if annotations.get("idempotentHint"):
                hints.append("idempotent")
            if hints:
                lines.append(f"**Hints**: {', '.join(hints)}")
            tags = tool.get("tags", [])
            if tags:
                lines.append(f"**Tags**: {', '.join(tags)}")
            lines.append("")

    # Resources
    resources = metadata.get("resources", [])
    templates = metadata.get("resource_templates", [])
    if resources or templates:
        lines.append("### Resources\n")
        for r in resources:
            lines.append(f"- `{r['uri']}` - {r['description']}")
        for t in templates:
            lines.append(f"- `{t['uri_template']}` - {t['description']}")
        lines.append("")

    # Prompts
    prompts = metadata.get("prompts", [])
    if prompts:
        lines.append("### Prompts\n")
        for p in prompts:
            lines.append(f"- **{p['name']}**: {p['description']}")
        lines.append("")

    return "\n".join(lines)


def format_claude_desktop_section(server_name: str) -> str:
    """Generate the ## Claude Desktop markdown section for a server."""
    config = json.dumps(
        {
            "mcpServers": {
                f"clio-{server_name}": {
                    "command": "clio-kit",
                    "args": ["mcp-server", server_name],
                }
            }
        },
        indent=2,
    )
    lines = [
        "## Claude Desktop\n",
        "Add to your Claude Desktop config (`claude_desktop_config.json`):\n",
        "```json",
        config,
        "```",
        "",
    ]
    return "\n".join(lines)


def format_claude_code_section(server_name: str) -> str:
    """Generate the ## Claude Code markdown section for a server."""
    lines = [
        "## Claude Code\n",
        "```bash",
        f"claude mcp add clio-{server_name} -- clio-kit mcp-server {server_name}",
        "```\n",
        "Or install via the CLIO Kit plugin marketplace:\n",
        "```",
        "/plugin marketplace add iowarp/clio-kit",
        f"/plugin install clio-{server_name}@iowarp-clio-kit",
        "```",
        "",
    ]
    return "\n".join(lines)


def format_gemini_section(server_name: str) -> str:
    """Generate the ## Gemini CLI markdown section for a server."""
    config = json.dumps(
        {
            "mcpServers": {
                f"clio-{server_name}": {
                    "command": "clio-kit",
                    "args": ["mcp-server", server_name],
                }
            }
        },
        indent=2,
    )
    lines = [
        "## Gemini CLI\n",
        "Add to `~/.gemini/settings.json`:\n",
        "```json",
        config,
        "```\n",
        "Or install the CLIO Kit extension:\n",
        "```bash",
        "gemini extensions install https://github.com/iowarp/clio-kit",
        "```",
        "",
    ]
    return "\n".join(lines)


def update_section(content: str, heading: str, new_section: str) -> str:
    """Replace a ## heading section in content, or append before ## Examples / EOF."""
    pattern = rf"## {re.escape(heading)}.*?(?=\n## |\Z)"
    if re.search(pattern, content, re.DOTALL):
        return re.sub(pattern, new_section.rstrip(), content, flags=re.DOTALL)
    # No existing section — append before ## Examples or at end
    examples_match = re.search(r"\n(## Examples)", content)
    if examples_match:
        pos = examples_match.start(1)
        return content[:pos] + "\n" + new_section + "\n\n" + content[pos:]
    return content.rstrip() + "\n\n" + new_section


def update_readme(
    readme_file: Path,
    capabilities_section: str,
    claude_code_section: str,
    claude_desktop_section: str,
    gemini_section: str,
) -> None:
    """Replace Capabilities, Claude Code, Claude Desktop, and Gemini sections."""
    content = readme_file.read_text(encoding="utf-8")
    content = update_section(content, "Capabilities", capabilities_section)
    content = update_section(content, "Claude Code", claude_code_section)
    content = update_section(content, "Claude Desktop", claude_desktop_section)
    content = update_section(content, "Gemini CLI", gemini_section)
    readme_file.write_text(content, encoding="utf-8")


def update_all_mcps(mcps_dir: str) -> None:
    """Update README files for all MCP servers."""
    mcps_path = Path(mcps_dir)
    if not mcps_path.exists():
        print(f"Error: {mcps_dir} does not exist")
        sys.exit(1)

    for mcp_dir in sorted(mcps_path.iterdir()):
        if not mcp_dir.is_dir() or mcp_dir.name.startswith("."):
            continue

        pyproject = mcp_dir / "pyproject.toml"
        readme = mcp_dir / "README.md"
        if not pyproject.exists():
            continue
        if not readme.exists():
            print(f"  Skipping {mcp_dir.name}: no README.md")
            continue

        server_name = mcp_dir.name
        print(f"Processing {server_name}...")
        metadata = extract_metadata(mcp_dir)
        if metadata is None:
            continue

        capabilities = format_capabilities_section(metadata)
        claude_code = format_claude_code_section(server_name)
        claude_desktop = format_claude_desktop_section(server_name)
        gemini = format_gemini_section(server_name)
        update_readme(readme, capabilities, claude_code, claude_desktop, gemini)
        tool_count = len(metadata.get("tools", []))
        print(
            f"  Updated README ({tool_count} tools, "
            f"{len(metadata.get('resources', [])) + len(metadata.get('resource_templates', []))} resources, "
            f"{len(metadata.get('prompts', []))} prompts)"
        )


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python readme_filler.py <mcps_directory>")
        sys.exit(1)
    update_all_mcps(sys.argv[1])
    print("Done.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Update README files for all MCP servers using FastMCP 3.0 metadata.

Imports each server via extract_mcp_metadata.py and updates the Capabilities
section in each server's README.md with real tool/resource/prompt data.

Usage:
    python scripts/readme_filler.py clio-kit-mcp-servers
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


def extract_metadata(mcp_dir: Path) -> Optional[Dict]:
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


def format_capabilities_section(metadata: Dict) -> str:
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


def update_readme(readme_file: Path, new_section: str) -> None:
    """Replace the ## Capabilities section in a README file."""
    content = readme_file.read_text(encoding="utf-8")

    # Replace existing Capabilities section (up to next ## heading or EOF)
    pattern = r"## Capabilities.*?(?=\n## |\Z)"
    if re.search(pattern, content, re.DOTALL):
        updated = re.sub(pattern, new_section.rstrip(), content, flags=re.DOTALL)
    else:
        # No existing section — append before ## Examples or at end
        examples_match = re.search(r"\n(## Examples)", content)
        if examples_match:
            pos = examples_match.start(1)
            updated = content[:pos] + "\n" + new_section + "\n\n" + content[pos:]
        else:
            updated = content.rstrip() + "\n\n" + new_section
    readme_file.write_text(updated, encoding="utf-8")


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

        print(f"Processing {mcp_dir.name}...")
        metadata = extract_metadata(mcp_dir)
        if metadata is None:
            continue

        section = format_capabilities_section(metadata)
        update_readme(readme, section)
        tool_count = len(metadata.get("tools", []))
        print(f"  Updated README ({tool_count} tools, "
              f"{len(metadata.get('resources', [])) + len(metadata.get('resource_templates', []))} resources, "
              f"{len(metadata.get('prompts', []))} prompts)")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python readme_filler.py <mcps_directory>")
        sys.exit(1)
    update_all_mcps(sys.argv[1])
    print("Done.")


if __name__ == "__main__":
    main()

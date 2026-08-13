"""Shared helpers for the web MCP server tests."""

from __future__ import annotations

import json
from typing import Any


def parse_result(result: Any) -> dict[str, Any]:
    """Normalize a FastMCP in-memory tool result into a plain dict."""
    data = result.data
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        parsed = json.loads(data)
        if isinstance(parsed, dict):
            return parsed
    return {"raw": str(data)}

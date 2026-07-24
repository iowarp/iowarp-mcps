"""Test configuration and fixtures for the web MCP server tests.

Every test runs against a freshly constructed ``Settings`` confined to the
pytest temp dir, so behavior is driven by config -- never ambient environment.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from web_mcp import server
from web_mcp.server import Settings


@pytest.fixture(autouse=True)
def clean_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Reset ``server.settings`` to a HERMETIC temp-confined default for each test.

    Ambient ``WEB_*`` env vars are cleared and ``.env`` reading is disabled so behavior is
    driven purely by config, never the runner's environment.
    """
    for key in [k for k in os.environ if k.startswith("WEB_")]:
        monkeypatch.delenv(key, raising=False)
    cfg = Settings(_env_file=None, artifacts_root=str(tmp_path / "artifacts"))
    monkeypatch.setattr(server, "settings", cfg)
    return cfg

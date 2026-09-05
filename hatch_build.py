"""Generate immutable wheel launch metadata from the source being packaged."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class RuntimeCatalogHook(BuildHookInterface):
    """Build the runtime catalog once, rather than hashing source on every launch."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        root = Path(self.root)
        spec = importlib.util.spec_from_file_location(
            "runtime_catalog", root / "src/clio_kit/runtime_catalog.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.write_catalog(
            root / "clio-kit-mcp-servers", root / "src/clio_kit/runtime-catalog.json"
        )

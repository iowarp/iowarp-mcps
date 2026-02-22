"""Local filesystem namespace stub."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LocalFilesystemNamespace:
    root: Path

    def describe(self) -> str:
        return f"local filesystem namespace at {self.root}"

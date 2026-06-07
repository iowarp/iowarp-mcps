"""Error types for the terrain implementation layer."""

from __future__ import annotations


class TerrainError(Exception):
    """Base error for terrain analysis failures (bad input, invalid grid, etc.)."""


class DependencyMissingError(TerrainError):
    """An optional dependency required for a specific file format is not installed.

    Carries the package name and a human-readable next action so the server
    layer can surface an actionable message.
    """

    def __init__(self, package: str, next_action: str) -> None:
        self.package = package
        self.next_action = next_action
        super().__init__(
            f"Optional dependency {package!r} is required for this file type. {next_action}"
        )

"""Task aliases exposed through project scripts."""

from __future__ import annotations

import subprocess


def _run(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def lint() -> None:
    raise SystemExit(_run(["ruff", "check", "."]))


def format_check() -> None:
    raise SystemExit(_run(["ruff", "format", "--check", "."]))


def typecheck() -> None:
    raise SystemExit(_run(["mypy", "src"]))


def test() -> None:
    raise SystemExit(_run(["pytest"]))


def build() -> None:
    raise SystemExit(_run(["python", "-m", "build"]))


def serve() -> None:
    raise SystemExit(_run(["uvicorn", "clio_agentic_search.api.app:app", "--reload"]))


def sync() -> None:
    raise SystemExit(_run(["uv", "sync", "--all-groups"]))

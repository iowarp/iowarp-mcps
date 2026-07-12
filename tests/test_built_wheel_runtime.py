"""Exact built-wheel regressions for root launcher data and child profiles."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from clio_kit.mcp_contracts import exchange_mcp_tools_list

JSON = dict[str, Any]
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def built_root_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build one exact root wheel for installed-artifact regressions."""
    uv = shutil.which("uv")
    assert uv is not None, "uv is required for built-wheel tests"
    output = tmp_path_factory.mktemp("clio-kit-wheel")
    completed = subprocess.run(
        [uv, "build", "--out-dir", str(output)],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stderr
    wheels = list(output.glob("clio_kit-*.whl"))
    assert len(wheels) == 1
    return wheels[0].resolve(strict=True)


def test_installed_wheel_ignores_fake_home_legacy_server_shadow(
    built_root_wheel: Path,
    tmp_path: Path,
) -> None:
    """Wheel-owned server data wins over a mutable legacy user-home tree."""
    uvx = shutil.which("uvx")
    assert uvx is not None, "uvx is required for built-wheel tests"
    fake_home = tmp_path / "home"
    shadow = (
        fake_home / ".local" / "share" / "clio-kit" / "clio-kit-mcp-servers" / "shadow"
    )
    shadow.mkdir(parents=True)
    (shadow / "pyproject.toml").write_text(
        "[project]\nname='shadow-mcp'\nversion='1.0.0'\n"
        "[project.scripts]\nshadow-mcp='shadow:main'\n",
        encoding="utf-8",
    )
    environment = _wheel_environment(tmp_path, fake_home=fake_home)

    completed = subprocess.run(
        [
            uvx,
            "--isolated",
            "--refresh",
            "--from",
            str(built_root_wheel),
            "clio-kit",
            "mcp-servers",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
        timeout=120,
    )

    assert completed.returncode == 0, completed.stderr
    assert "  - spack" in completed.stdout
    assert "shadow" not in completed.stdout


def test_built_wheel_default_spack_entry_exposes_exact_admin_profile(
    built_root_wheel: Path,
    tmp_path: Path,
) -> None:
    """The shared spack-mcp entry honors --profile admin in the built wheel."""
    uvx = shutil.which("uvx")
    assert uvx is not None, "uvx is required for built-wheel tests"
    _, tools_list = exchange_mcp_tools_list(
        [
            uvx,
            "--isolated",
            "--refresh",
            "--from",
            str(built_root_wheel),
            "clio-kit",
            "mcp-server",
            "spack",
            "--",
            "--profile",
            "admin",
        ],
        environment=_wheel_environment(tmp_path),
        contract_id="built-wheel-spack-admin",
        timeout_seconds=180,
    )
    result = tools_list.get("result")
    assert isinstance(result, dict)
    tools = cast(list[JSON], result["tools"])

    assert {tool["name"] for tool in tools} == {"spack_environment"}


def _wheel_environment(
    tmp_path: Path, *, fake_home: Path | None = None
) -> dict[str, str]:
    environment = os.environ.copy()
    environment["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    environment["CLIO_KIT_CACHE_DIR"] = str(tmp_path / "clio-cache")
    environment["UV_PYTHON"] = sys.executable
    if fake_home is not None:
        environment["HOME"] = str(fake_home)
        environment["USERPROFILE"] = str(fake_home)
    return environment

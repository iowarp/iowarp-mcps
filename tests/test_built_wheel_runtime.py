"""Exact built-wheel regressions for root launcher data and child profiles."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
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
            f"{built_root_wheel}[spack]",
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


@pytest.fixture(scope="module")
def shared_wheel_install(
    built_root_wheel: Path, tmp_path_factory: pytest.TempPathFactory
) -> tuple[Path, dict[str, str]]:
    """Install the science/HPC union once, outside the source checkout."""
    root = tmp_path_factory.mktemp("shared-wheel-runtime")
    environment = root / "runtime"
    uv = shutil.which("uv")
    assert uv is not None
    subprocess.run(
        [uv, "venv", "--python", sys.executable, str(environment)],
        check=True,
        timeout=60,
    )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--python",
            str(python),
            f"{built_root_wheel}[science,hpc]",
        ],
        check=True,
        timeout=300,
    )
    env = os.environ.copy()
    env["CLIO_KIT_CACHE_DIR"] = str(root / "unused-cache")
    env["UV_OFFLINE"] = "1"
    env.pop("PYTHONPATH", None)
    return python, env


@pytest.mark.parametrize("server", ["ndp", "geo", "pandas", "plot"])
def test_four_servers_share_one_installed_wheel_environment(
    shared_wheel_install: tuple[Path, dict[str, str]],
    server: str,
) -> None:
    """Real offline MCP handshakes work twice without allocating private envs."""
    python, env = shared_wheel_install
    command = [
        str(python),
        "-c",
        "from clio_kit import cli; cli()",
        "mcp-server",
        server,
    ]
    timings = []
    for _ in range(2):
        start = time.perf_counter()
        initialize, response = exchange_mcp_tools_list(
            command,
            environment=env,
            contract_id=f"shared-{server}",
            timeout_seconds=60,
        )
        timings.append(round(time.perf_counter() - start, 3))
        assert "result" in initialize
        assert response["result"]["tools"]
        assert not Path(env["CLIO_KIT_CACHE_DIR"]).exists()
    print(f"{server}: first/repeat MCP handshake seconds={timings}")


def test_wheel_runtime_info_reports_one_installed_prefix(
    shared_wheel_install: tuple[Path, dict[str, str]],
) -> None:
    python, env = shared_wheel_install
    result = subprocess.run(
        [
            str(python),
            "-c",
            "from clio_kit import cli; cli()",
            "runtime-info",
            "ndp",
            "geo",
            "pandas",
            "plot",
        ],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    info = json.loads(result.stdout)
    assert Path(info["prefix"]) == python.parent.parent
    assert Path(info["python"]) == python
    assert all(not spec["problems"] for spec in info["servers"].values())
    assert len({spec["source_sha256"] for spec in info["servers"].values()}) == 4
    assert not Path(env["CLIO_KIT_CACHE_DIR"]).exists()


def test_shared_wheel_profiles_and_plots_a_real_csv(
    shared_wheel_install: tuple[Path, dict[str, str]],
    tmp_path: Path,
) -> None:
    """Exercise two servers' scientific libraries and workspace outputs over MCP."""
    python, env = shared_wheel_install
    csv = tmp_path / "data.csv"
    csv.write_text("x,y\n1,2\n2,4\n3,6\n", encoding="utf-8")
    output = tmp_path / "plot.png"
    script = """
import asyncio, json, sys
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

async def main():
    for server, tool, args in [
        ("pandas", "profile_csv", {"data_path": sys.argv[1]}),
        ("plot", "line_plot", {"file_path": sys.argv[1], "x_column": "x", "y_column": "y", "output_path": sys.argv[2]}),
    ]:
        transport = StdioTransport(command=sys.executable, args=["-c", "from clio_kit import cli; cli()", "mcp-server", server])
        async with Client(transport) as client:
            result = await client.call_tool(tool, args)
            assert not result.is_error
            print(json.dumps({"server": server, "data": result.structured_content}))
asyncio.run(main())
"""
    result = subprocess.run(
        [str(python), "-c", script, str(csv), str(output)],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = [json.loads(line) for line in result.stdout.splitlines()]
    assert [item["server"] for item in data] == ["pandas", "plot"]
    assert data[0]["data"]["success"] is True
    assert data[1]["data"]["data_points"] == 3
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert not Path(env["CLIO_KIT_CACHE_DIR"]).exists()


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

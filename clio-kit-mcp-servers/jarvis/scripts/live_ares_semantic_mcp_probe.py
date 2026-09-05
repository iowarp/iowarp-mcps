"""Probe the JARVIS MCP semantic user contract through a real stdio MCP server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlsplit

Json = dict[str, Any]
EXPECTED_JARVIS_VERSION = "1.8.0"
EXPECTED_JARVIS_URL = (
    "https://github.com/grc-iit/jarvis-cd/releases/download/v1.8.0/"
    "jarvis_cd-1.8.0-py3-none-any.whl"
)
EXPECTED_JARVIS_SHA256 = (
    "2c2e2042d0256bd3d9c117d75aaf00d26d9e814fcbcca9a904abf06399fc1067"
)


class McpClient:
    """Small JSON-RPC stdio client for live MCP smoke and acceptance probes."""

    def __init__(self, command: list[str], env: dict[str, str] | None = None) -> None:
        self._next_id = 1
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )

    def close(self) -> None:
        """Terminate the MCP process."""
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def request(self, method: str, params: Json | None = None) -> Json:
        """Send a JSON-RPC request and return the response."""
        request_id = self._next_id
        self._next_id += 1
        payload: Json = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)
        deadline = time.time() + 120
        while time.time() < deadline:
            line = self._readline()
            if not line:
                continue
            try:
                response = json.loads(line)
            except json.JSONDecodeError:
                print(f"non_json_stdout: {line.rstrip()}", file=sys.stderr)
                continue
            if response.get("id") == request_id:
                if "error" in response:
                    raise RuntimeError(json.dumps(response["error"], indent=2))
                return response
        raise TimeoutError(f"timed out waiting for {method}")

    def notify(self, method: str, params: Json | None = None) -> None:
        """Send a JSON-RPC notification."""
        payload: Json = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        self._send(payload)

    def initialize(self) -> None:
        """Complete the MCP initialize handshake."""
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "clio-kit-live-probe", "version": "0"},
            },
        )
        self.notify("notifications/initialized")

    def call_tool(self, name: str, arguments: Json | None = None) -> Json:
        """Call an MCP tool."""
        return self.request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )["result"]

    def tools(self) -> list[str]:
        """List available tool names."""
        names: list[str] = []
        cursor: str | None = None
        while True:
            params = {"cursor": cursor} if cursor else None
            response = self.request("tools/list", params)
            result = response["result"]
            names.extend(tool["name"] for tool in result["tools"])
            cursor = result.get("nextCursor")
            if not cursor:
                return names

    def _send(self, payload: Json) -> None:
        if self.process.stdin is None:
            raise RuntimeError("MCP stdin is closed")
        self.process.stdin.write(json.dumps(payload) + "\n")
        self.process.stdin.flush()

    def _readline(self) -> str:
        if self.process.stdout is None:
            raise RuntimeError("MCP stdout is closed")
        return self.process.stdout.readline()


def _tool_payload(result: Json) -> Json:
    """Return one successful tool's structured payload."""
    if result.get("isError") is True:
        raise RuntimeError(f"MCP tool returned an error: {json.dumps(result)}")
    structured = result.get("structuredContent")
    if isinstance(structured, dict):
        return structured
    content = result.get("content")
    if isinstance(content, list):
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "text":
                continue
            text = item.get("text")
            if not isinstance(text, str):
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
    raise RuntimeError(f"MCP tool omitted structured output: {json.dumps(result)}")


def _assert_valid_artifact_location(artifact: Json) -> None:
    """Assert that a live artifact carries a safe transport-neutral location."""
    location = artifact.get("location")
    assert isinstance(location, dict), artifact
    assert set(location) == {"kind", "value"}, location
    kind = location.get("kind")
    value = location.get("value")
    assert kind in {"execution_path", "cluster_path", "external_uri"}, location
    assert (
        isinstance(value, str)
        and value
        and not any(ord(character) < 32 for character in value)
    ), location
    if kind == "execution_path":
        path = PurePosixPath(value)
        assert (
            "\\" not in value
            and not path.is_absolute()
            and not value.startswith("/")
            and not value.endswith("/")
            and "//" not in value
            and path.as_posix() == value
            and (not path.parts or ":" not in path.parts[0])
        ), location
        assert all(part not in {"", ".", ".."} for part in path.parts), location
    elif kind == "cluster_path":
        path = PurePosixPath(value)
        assert (
            "\\" not in value
            and path.is_absolute()
            and value.startswith("/")
            and value != "/"
            and not value.endswith("/")
            and "//" not in value
            and path.as_posix() == value
        ), location
        assert all(part not in {"", ".", ".."} for part in path.parts[1:]), location
    else:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        assert re.fullmatch(r"[a-z][a-z0-9+.-]*", scheme), location
        assert len(scheme) > 1 and scheme not in {
            "data",
            "file",
            "javascript",
        }, location
        assert parsed.username is None and parsed.password is None, location
        if scheme in {"gs", "http", "https", "s3"}:
            assert parsed.netloc, location


def _pipeline_step_ids(snapshot: Json) -> set[str]:
    """Return package IDs from one jarvis_describe pipeline snapshot."""
    pipeline = snapshot.get("pipeline")
    if not isinstance(pipeline, dict):
        raise RuntimeError("jarvis_describe omitted its pipeline document")
    packages = pipeline.get("packages")
    if not isinstance(packages, list):
        raise RuntimeError("jarvis_describe omitted its package list")
    return {
        str(package.get("pkg_id") or package.get("id"))
        for package in packages
        if isinstance(package, dict) and (package.get("pkg_id") or package.get("id"))
    }


def _install_clio_kit_tool(wheel: str, root: Path) -> tuple[Path, dict[str, str]]:
    """Install the candidate wheel as an isolated persistent uv tool."""
    uv = shutil.which("uv")
    if uv is None:
        candidate = Path.home() / ".local" / "bin" / "uv"
        if not candidate.is_file():
            raise RuntimeError("uv is required to install the clio-kit acceptance tool")
        uv = str(candidate)

    tool_dir = root / "uv-tools"
    bin_dir = root / "uv-tool-bin"
    cache_dir = root / "uv-cache"
    child_cache_dir = root / "clio-kit-cache"
    env = os.environ.copy()
    for inherited_name in (
        "PYTHONHOME",
        "PYTHONPATH",
        "UV_PROJECT",
        "UV_PROJECT_ENVIRONMENT",
        "VIRTUAL_ENV",
    ):
        env.pop(inherited_name, None)
    env.update(
        {
            "CLIO_KIT_CACHE_DIR": str(child_cache_dir),
            "PYTHONNOUSERSITE": "1",
            "UV_TOOL_DIR": str(tool_dir),
            "UV_TOOL_BIN_DIR": str(bin_dir),
            "UV_CACHE_DIR": str(cache_dir),
        }
    )
    subprocess.run(
        [
            uv,
            "tool",
            "install",
            "--force",
            "--no-cache",
            "--with",
            f"jarvis-cd @ {EXPECTED_JARVIS_URL}#sha256={EXPECTED_JARVIS_SHA256}",
            f"{wheel}[jarvis]",
        ],
        check=True,
        env=env,
        stdout=sys.stderr,
        stderr=sys.stderr,
    )
    executable = bin_dir / ("clio-kit.exe" if os.name == "nt" else "clio-kit")
    if not executable.is_file():
        raise RuntimeError(
            f"uv tool install omitted the clio-kit executable: {executable}"
        )
    return executable, env


def _checked_command(
    command: list[str],
    *,
    env: dict[str, str],
    label: str,
    timeout: int = 300,
) -> subprocess.CompletedProcess[str]:
    """Run one bounded acceptance subprocess and retain its diagnostics."""
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label} timed out after {timeout} seconds") from exc
    if result.returncode != 0:
        diagnostic = (result.stderr or result.stdout)[-8192:]
        raise RuntimeError(
            f"{label} failed with exit code {result.returncode}: {diagnostic}"
        )
    return result


def _json_command(
    command: list[str],
    *,
    env: dict[str, str],
    label: str,
) -> Json:
    """Run a checked command and decode its final JSON object."""
    result = _checked_command(command, env=env, label=label)
    for line in reversed(result.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError(f"{label} did not return a JSON object")


def _environment_python(environment: Path) -> Path:
    """Return the Python executable inside one uv-managed environment."""
    executable = environment / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if not executable.is_file():
        raise RuntimeError(f"locked environment omitted Python: {executable}")
    return executable


def _verify_locked_jarvis_child(env: dict[str, str]) -> Json:
    """Prove that the installed launcher resolved the exact released JARVIS wheel."""
    tool_python = _environment_python(Path(env["UV_TOOL_DIR"]) / "clio-kit")
    resolved = _json_command(
        [
            str(tool_python),
            "-c",
            """
import json
import tomllib
import sys
from clio_kit import get_servers_path
from clio_kit.shared_runtime import runtime_info

server = get_servers_path() / "jarvis"
project = tomllib.loads((server / "pyproject.toml").read_text(encoding="utf-8"))
requirement = next(
    item for item in project["project"]["dependencies"]
    if item.startswith("jarvis-cd @ ")
)
lock = tomllib.loads((server / "uv.lock").read_text(encoding="utf-8"))
package = next(item for item in lock["package"] if item["name"] == "jarvis-cd")
print(json.dumps({
    "server_path": str(server),
    "child_environment": sys.prefix,
    "runtime": runtime_info(("jarvis",)),
    "requirement": requirement,
    "locked_version": package["version"],
    "locked_url": package["source"]["url"],
    "locked_wheels": package["wheels"],
}))
""",
        ],
        env=env,
        label="locked JARVIS project inspection",
    )
    expected_requirement = (
        f"jarvis-cd @ {EXPECTED_JARVIS_URL}#sha256={EXPECTED_JARVIS_SHA256}"
    )
    expected_wheels = [
        {
            "url": EXPECTED_JARVIS_URL,
            "hash": f"sha256:{EXPECTED_JARVIS_SHA256}",
        }
    ]
    if (
        resolved.get("requirement") != expected_requirement
        or resolved.get("locked_version") != EXPECTED_JARVIS_VERSION
        or resolved.get("locked_url") != EXPECTED_JARVIS_URL
        or resolved.get("locked_wheels") != expected_wheels
    ):
        raise RuntimeError(
            f"installed clio-kit carried an unexpected JARVIS lock: {resolved}"
        )

    runtime = resolved["runtime"]
    assert runtime["prefix"] == resolved["child_environment"]
    assert not runtime["servers"]["jarvis"]["problems"]
    assert not (Path(env["CLIO_KIT_CACHE_DIR"]) / "mcp-environments").exists()
    child_environment = Path(str(resolved["child_environment"]))
    installed = _json_command(
        [
            str(_environment_python(child_environment)),
            "-c",
            """
import inspect
import json
import sys
from importlib.metadata import distribution
from pathlib import Path
from jarvis_cd.core.pipeline import Pipeline

installed = distribution("jarvis-cd")
direct_url_text = installed.read_text("direct_url.json")
if direct_url_text is None:
    raise RuntimeError("jarvis-cd omitted direct_url.json")
source = Path(inspect.getfile(Pipeline)).resolve()
print(json.dumps({
    "installed_version": installed.version,
    "direct_url": json.loads(direct_url_text),
    "pipeline_source": str(source),
    "python_prefix": str(Path(sys.prefix).resolve()),
    "pipeline_source_is_child_owned": source.is_relative_to(Path(sys.prefix).resolve()),
    "has_artifact_api": callable(getattr(Pipeline, "get_execution_artifacts", None)),
}))
""",
        ],
        env=env,
        label="installed JARVIS child inspection",
    )
    direct_url = installed.get("direct_url")
    if (
        installed.get("installed_version") != EXPECTED_JARVIS_VERSION
        or not isinstance(direct_url, dict)
        or direct_url.get("url") != EXPECTED_JARVIS_URL
        or installed.get("pipeline_source_is_child_owned") is not True
        or installed.get("has_artifact_api") is not True
    ):
        raise RuntimeError(
            f"locked child did not load the exact released JARVIS runtime: {installed}"
        )
    return {
        **resolved,
        **installed,
        "expected_sha256": EXPECTED_JARVIS_SHA256,
    }


def _spack_command_path(value: str) -> Path:
    """Resolve one operator-supplied executable for the isolated MCP server."""
    candidate = Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise argparse.ArgumentTypeError(
            f"Spack command does not exist: {candidate}"
        ) from exc
    if not resolved.is_file():
        raise argparse.ArgumentTypeError(f"Spack command is not a file: {resolved}")
    if os.name != "nt" and not os.access(resolved, os.X_OK):
        raise argparse.ArgumentTypeError(f"Spack command is not executable: {resolved}")
    return resolved


def main() -> int:
    """Run the live semantic JARVIS MCP probe."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument(
        "--spack-spec",
        required=True,
        help="One already-installed, non-sensitive Spack spec to materialize.",
    )
    parser.add_argument(
        "--spack-command",
        type=_spack_command_path,
        required=True,
        help="Audited Spack executable used by the isolated JARVIS MCP server.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    spack_command = args.spack_command
    config_dir = root / "config"
    private_dir = root / "private"
    shared_dir = root / "shared"
    jarvis_root = root / "jarvis-root"
    for path in (config_dir, private_dir, shared_dir, jarvis_root):
        path.mkdir(parents=True, exist_ok=True)

    clio_kit, tool_env = _install_clio_kit_tool(args.wheel, root)
    base_cmd = [str(clio_kit), "mcp-server", "jarvis"]
    server_args = ["--spack-command", str(spack_command)]
    env = tool_env.copy()
    env["JARVIS_ROOT"] = str(jarvis_root)
    env["JARVIS_MCP_SCHEDULER"] = "slurm"
    help_result = _checked_command(
        base_cmd + ["--", *server_args, "--help"],
        env=env,
        label="installed JARVIS MCP help smoke",
    )
    if "Jarvis MCP Server" not in (help_result.stdout + help_result.stderr):
        raise RuntimeError("installed JARVIS MCP help omitted its server identity")
    locked_jarvis = _verify_locked_jarvis_child(env)

    admin = McpClient(base_cmd + ["--", *server_args, "--profile", "admin"], env=env)
    try:
        admin.initialize()
        admin_tools = admin.tools()
        assert "jm_create_config" in admin_tools, admin_tools
        admin.call_tool(
            "jm_create_config",
            {
                "config_dir": str(config_dir),
                "private_dir": str(private_dir),
                "shared_dir": str(shared_dir),
            },
        )
    finally:
        admin.close()

    user = McpClient(base_cmd + ["--", *server_args], env=env)
    try:
        user.initialize()
        tools = user.tools()
        expected = [
            "jarvis_create_pipeline",
            "jarvis_describe",
            "jarvis_add_step",
            "jarvis_edit_step",
            "jarvis_run",
            "jarvis_get_execution",
        ]
        assert tools == expected, tools
        paraview_description = _tool_payload(
            user.call_tool(
                "jarvis_describe",
                {"target": "package", "package_name": "paraview"},
            )
        )
        paraview_package = paraview_description.get("package")
        assert isinstance(paraview_package, dict), paraview_description
        assert paraview_package.get("name") == "builtin.paraview", paraview_package
        paraview_menu = paraview_package.get("settings")
        assert isinstance(paraview_menu, list), paraview_package
        paraview_settings = {
            setting["name"]: setting
            for setting in paraview_menu
            if isinstance(setting, dict) and isinstance(setting.get("name"), str)
        }
        assert paraview_settings["mode"].get("default") == "server"
        assert "service for a live dataset view" in str(
            paraview_settings["mode"].get("description")
        )
        assert paraview_settings["dataset_descriptor"].get("default") == ""
        assert "requires mode=service" in str(
            paraview_settings["dataset_descriptor"].get("description")
        )
        assert paraview_settings["force_offscreen_rendering"].get("default") is False
        assert "service mode is always headless" in str(
            paraview_settings["force_offscreen_rendering"].get("description")
        )
        assert {
            "pvpython_bin",
            "pvpython_options",
            "pvbatch_bin",
            "pvbatch_options",
        }.isdisjoint(paraview_settings)
        pipeline_id = f"clio_semantic_{int(time.time())}"
        create_result = user.call_tool(
            "jarvis_create_pipeline",
            {
                "pipeline_id": pipeline_id,
                "execution": {
                    "mode": "cluster",
                    "job_name": pipeline_id,
                    "nodes": 1,
                    "tasks_per_node": 1,
                    "walltime": "00:05:00",
                    "output": str(shared_dir / f"{pipeline_id}-%j.out"),
                    "error": str(shared_dir / f"{pipeline_id}-%j.err"),
                },
            },
        )
        add_result = user.call_tool(
            "jarvis_add_step",
            {
                "pipeline_id": pipeline_id,
                "package_name": "builtin.echo",
                "step_id": "echo_keep",
            },
        )
        removable_add_result = user.call_tool(
            "jarvis_add_step",
            {
                "pipeline_id": pipeline_id,
                "package_name": "builtin.ior",
                "step_id": "ior_edit_remove",
            },
        )
        edit_result = user.call_tool(
            "jarvis_edit_step",
            {
                "pipeline_id": pipeline_id,
                "step_id": "ior_edit_remove",
                "operation": "edit",
                "config": {"block": "64m"},
            },
        )
        edited_step = _tool_payload(
            user.call_tool(
                "jarvis_describe",
                {
                    "target": "step",
                    "pipeline_id": pipeline_id,
                    "step_id": "ior_edit_remove",
                    "include_yaml": False,
                },
            )
        )
        edited_config = edited_step.get("config")
        assert isinstance(edited_config, dict), edited_step
        assert edited_config.get("config", {}).get("block") == "64m"

        remove_result = user.call_tool(
            "jarvis_edit_step",
            {
                "pipeline_id": pipeline_id,
                "step_id": "ior_edit_remove",
                "operation": "remove",
            },
        )
        pipeline_after_remove = _tool_payload(
            user.call_tool(
                "jarvis_describe",
                {
                    "target": "pipeline",
                    "pipeline_id": pipeline_id,
                    "include_yaml": False,
                },
            )
        )
        step_ids = _pipeline_step_ids(pipeline_after_remove)
        assert "echo_keep" in step_ids, step_ids
        assert "ior_edit_remove" not in step_ids, step_ids

        scripted_result = user.call_tool(
            "jarvis_run",
            {
                "pipeline_id": pipeline_id,
                "execution": {"mode": "cluster"},
                "submit": False,
                "spack_specs": [args.spack_spec],
            },
        )
        scripted_payload = _tool_payload(scripted_result)
        assert scripted_payload.get("schema_version") == "clio-kit.jarvis-run.v1"
        scripted_handle = scripted_payload.get("execution_handle")
        assert isinstance(scripted_handle, dict), scripted_payload
        assert scripted_handle.get("scheduler_provider") == "slurm", scripted_handle
        assert scripted_handle.get("scheduler_native_id") is None, scripted_handle
        assert scripted_handle.get("cluster") is None, scripted_handle
        scripted_progress = scripted_payload.get("progress")
        assert isinstance(scripted_progress, dict), scripted_payload
        assert scripted_progress.get("schema_version") == (
            "jarvis.execution.progress.v1"
        ), scripted_progress
        runtime_metadata = scripted_payload.get("runtime_metadata")
        assert isinstance(runtime_metadata, dict), scripted_payload
        details = runtime_metadata.get("details")
        assert isinstance(details, dict), runtime_metadata
        environment = details.get("environment")
        assert isinstance(environment, dict), details
        assert environment.get("specs") == [args.spack_spec], environment
        assert environment.get("persisted") is True, environment
        assert environment.get("scheduler_reload") == "execution_snapshot", environment
        variable_names = environment.get("variable_names")
        assert isinstance(variable_names, list) and variable_names, environment

        pipeline_after_spack = _tool_payload(
            user.call_tool(
                "jarvis_describe",
                {
                    "target": "pipeline",
                    "pipeline_id": pipeline_id,
                    "include_yaml": False,
                },
            )
        )
        pipeline_document = pipeline_after_spack.get("pipeline")
        assert isinstance(pipeline_document, dict), pipeline_after_spack
        persisted_environment = pipeline_document.get("env")
        assert isinstance(persisted_environment, dict), pipeline_document
        assert set(variable_names).issubset(persisted_environment), (
            persisted_environment
        )

        script_path = scripted_payload.get("script_path")
        assert isinstance(script_path, str), scripted_payload
        assert Path(script_path).is_relative_to(shared_dir), script_path
        script = Path(script_path).read_text(encoding="utf-8")
        assert "jarvis_cd.core.execution activate" in script, script
        assert "jarvis_cd.core.execution finalize" in script, script
        assert "env JARVIS_PIPELINE_SNAPSHOT_DIR=" in script, script
        assert "-m jarvis_cd.core.cli ppl run yaml " in script, script
        assert f"jarvis cd {pipeline_id}" not in script, script

        submitted_result = user.call_tool(
            "jarvis_run",
            {
                "pipeline_id": pipeline_id,
                "execution": {"mode": "cluster"},
                "submit": True,
                "wait": True,
            },
        )
        submitted_payload = _tool_payload(submitted_result)
        assert submitted_payload.get("schema_version") == "clio-kit.jarvis-run.v1"
        submitted_handle = submitted_payload.get("execution_handle")
        assert isinstance(submitted_handle, dict), submitted_payload
        submitted_metadata = submitted_payload.get("runtime_metadata")
        assert isinstance(submitted_metadata, dict), submitted_payload
        assert submitted_payload.get("status") == "completed", submitted_payload
        assert submitted_handle.get("scheduler_provider") == "slurm", submitted_handle
        assert submitted_handle.get("scheduler_native_id"), submitted_handle
        assert "cluster" in submitted_handle, submitted_handle
        submitted_progress = submitted_payload.get("progress")
        assert isinstance(submitted_progress, dict), submitted_payload
        assert submitted_progress.get("schema_version") == (
            "jarvis.execution.progress.v1"
        ), submitted_progress
        assert (
            submitted_metadata.get("scheduler_native_id")
            == (submitted_handle["scheduler_native_id"])
        ), submitted_metadata
        assert submitted_metadata.get("scheduler_job_id"), submitted_metadata
        terminal = submitted_metadata.get("terminal")
        assert isinstance(terminal, dict) and terminal.get("terminal") is True
        assert terminal.get("returncode") == 0, terminal
        execution_id = submitted_handle.get("execution_id")
        assert isinstance(execution_id, str), submitted_handle
        execution_result = user.call_tool(
            "jarvis_get_execution",
            {
                "pipeline_id": pipeline_id,
                "execution_id": execution_id,
                "artifacts": {"package_id": "jarvis-core", "page_size": 100},
            },
        )
        execution_payload = _tool_payload(execution_result)
        assert execution_payload.get("schema_version") == (
            "clio-kit.jarvis-execution.v2"
        ), execution_payload
        progress_payload = execution_payload.get("progress")
        assert isinstance(progress_payload, dict), execution_payload
        assert progress_payload.get("schema_version") == (
            "jarvis.execution.progress.v1"
        ), progress_payload
        artifact_results: list[Json] = [execution_result]
        core_artifacts: list[Json] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        artifact_payload = execution_payload.get("artifact_page")
        while True:
            assert isinstance(artifact_payload, dict), execution_payload
            assert artifact_payload.get("producer_schema_version") == (
                "jarvis.execution.artifacts.v1"
            ), artifact_payload
            assert artifact_payload.get("execution_id") == execution_id, (
                artifact_payload
            )
            assert artifact_payload.get("pipeline_id") == pipeline_id, artifact_payload
            assert artifact_payload.get("execution_state") == "completed", (
                artifact_payload
            )
            assert artifact_payload.get("terminal") is True, artifact_payload
            page = artifact_payload.get("artifacts")
            assert isinstance(page, list) and len(page) <= 100, artifact_payload
            assert artifact_payload.get("returned_artifact_count") == len(page)
            core_artifacts.extend(page)
            next_cursor = artifact_payload.get("next_cursor")
            if next_cursor is None:
                assert artifact_payload.get("matching_artifact_count") == len(
                    core_artifacts
                ), artifact_payload
                break
            assert isinstance(next_cursor, str) and next_cursor not in seen_cursors
            seen_cursors.add(next_cursor)
            assert len(seen_cursors) <= 64, artifact_payload
            cursor = next_cursor
            artifact_result = user.call_tool(
                "jarvis_get_execution",
                {
                    "pipeline_id": pipeline_id,
                    "execution_id": execution_id,
                    "include_progress": False,
                    "artifacts": {
                        "package_id": "jarvis-core",
                        "page_size": 100,
                        "cursor": cursor,
                    },
                },
            )
            artifact_results.append(artifact_result)
            artifact_envelope = _tool_payload(artifact_result)
            assert artifact_envelope.get("progress") is None, artifact_envelope
            artifact_payload = artifact_envelope.get("artifact_page")

        assert core_artifacts, "completed execution omitted JARVIS core artifacts"
        assert all(item.get("package_id") == "jarvis-core" for item in core_artifacts)
        assert len({item.get("artifact_id") for item in core_artifacts}) == len(
            core_artifacts
        )
        required_core = {
            "pipeline-input": ("provenance", "configuration"),
            "environment-input": ("provenance", "configuration"),
            "pipeline-runtime": ("provenance", "configuration"),
            "environment-runtime": ("provenance", "configuration"),
            "scheduler-script": ("provenance", "script"),
            "stdout": ("log", "log"),
            "stderr": ("log", "log"),
        }
        core_by_name = {item.get("logical_name"): item for item in core_artifacts}
        assert required_core.keys() <= core_by_name.keys(), core_by_name
        for logical_name, (role, kind) in required_core.items():
            artifact = core_by_name[logical_name]
            assert artifact.get("execution_id") == execution_id, artifact
            assert artifact.get("role") == role, artifact
            assert artifact.get("kind") == kind, artifact
            assert artifact.get("state") == "finalized", artifact
            _assert_valid_artifact_location(artifact)
        scheduler_native_id = submitted_handle["scheduler_native_id"]
        for logical_name, extension in (("stdout", "out"), ("stderr", "err")):
            log_artifact = core_by_name[logical_name]
            log_location = log_artifact["location"]
            assert log_location["kind"] == "cluster_path", log_artifact
            log_path = Path(log_location["value"])
            assert log_path.name.endswith(f"-{scheduler_native_id}.{extension}"), (
                log_artifact
            )
            assert "%" not in log_path.name, log_artifact
            assert log_path.is_file(), log_artifact
        print(
            json.dumps(
                {
                    "schema_version": "clio-kit.live-validation.v1",
                    "status": "passed",
                    "wheel": str(Path(args.wheel).resolve()),
                    "wheel_sha256": hashlib.sha256(
                        Path(args.wheel).read_bytes()
                    ).hexdigest(),
                    "tool_executable": str(clio_kit),
                    "tool_installation": {
                        "uv_tool_dir": tool_env["UV_TOOL_DIR"],
                        "uv_tool_bin_dir": tool_env["UV_TOOL_BIN_DIR"],
                        "uv_cache_dir": tool_env["UV_CACHE_DIR"],
                        "clio_kit_cache_dir": tool_env["CLIO_KIT_CACHE_DIR"],
                    },
                    "locked_jarvis": locked_jarvis,
                    "root": str(root),
                    "jarvis_root": str(jarvis_root),
                    "spack_spec": args.spack_spec,
                    "spack_command": str(spack_command),
                    "tools": tools,
                    "paraview_description": paraview_description,
                    "pipeline_id": pipeline_id,
                    "create": create_result,
                    "add": add_result,
                    "add_removable": removable_add_result,
                    "edit": edit_result,
                    "remove": remove_result,
                    "pipeline_after_remove": pipeline_after_remove,
                    "scripted": scripted_result,
                    "pipeline_after_spack": pipeline_after_spack,
                    "submitted": submitted_result,
                    "execution": execution_result,
                    "artifact_pages": artifact_results,
                },
                indent=2,
            )
        )
    finally:
        user.close()
    return 0


if __name__ == "__main__":
    try:
        exit_code = main()
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        print(
            json.dumps(
                {
                    "schema_version": "clio-kit.live-validation.v1",
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                indent=2,
            )
        )
        exit_code = 1
    raise SystemExit(exit_code)

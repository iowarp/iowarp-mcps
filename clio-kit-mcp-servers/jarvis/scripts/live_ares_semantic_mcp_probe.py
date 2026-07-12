"""Probe the JARVIS MCP semantic user contract through a real stdio MCP server."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


Json = dict[str, Any]


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
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    config_dir = root / "config"
    private_dir = root / "private"
    shared_dir = root / "shared"
    for path in (config_dir, private_dir, shared_dir):
        path.mkdir(parents=True, exist_ok=True)

    uvx = str(Path.home() / ".local" / "bin" / "uvx")
    base_cmd = [
        uvx,
        "--isolated",
        "--no-cache",
        "--from",
        args.wheel,
        "clio-kit",
        "mcp-server",
        "jarvis",
    ]
    env = os.environ.copy()
    env["JARVIS_MCP_SCHEDULER"] = "slurm"

    admin = McpClient(base_cmd + ["--", "--profile", "admin"], env=env)
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

    user = McpClient(base_cmd, env=env)
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
            "jarvis_get_execution_progress",
        ]
        assert tools == expected, tools
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
                "package_name": "builtin.echo",
                "step_id": "echo_remove",
            },
        )
        edit_result = user.call_tool(
            "jarvis_edit_step",
            {
                "pipeline_id": pipeline_id,
                "step_id": "echo_keep",
                "operation": "edit",
                "config": {"message": "clio semantic edit"},
            },
        )
        edited_step = _tool_payload(
            user.call_tool(
                "jarvis_describe",
                {
                    "target": "step",
                    "pipeline_id": pipeline_id,
                    "step_id": "echo_keep",
                    "include_yaml": False,
                },
            )
        )
        edited_config = edited_step.get("config")
        assert isinstance(edited_config, dict), edited_step
        assert edited_config.get("config", {}).get("message") == "clio semantic edit"

        remove_result = user.call_tool(
            "jarvis_edit_step",
            {
                "pipeline_id": pipeline_id,
                "step_id": "echo_remove",
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
        assert "echo_remove" not in step_ids, step_ids

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
        assert environment.get("scheduler_reload") == ("saved_pipeline_environment"), (
            environment
        )
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
        script = Path(script_path).read_text(encoding="utf-8")
        assert f"jarvis cd {pipeline_id}" in script, script
        assert "jarvis ppl run" in script, script

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
            {"pipeline_id": pipeline_id, "execution_id": execution_id},
        )
        progress_result = user.call_tool(
            "jarvis_get_execution_progress",
            {"pipeline_id": pipeline_id, "execution_id": execution_id},
        )
        execution_payload = _tool_payload(execution_result)
        progress_payload = _tool_payload(progress_result)
        assert execution_payload.get("schema_version") == (
            "clio-kit.jarvis-execution.v1"
        ), execution_payload
        assert progress_payload.get("schema_version") == (
            "clio-kit.jarvis-execution-progress-query.v1"
        ), progress_payload
        print(
            json.dumps(
                {
                    "tools": tools,
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
                    "progress": progress_result,
                },
                indent=2,
            )
        )
    finally:
        user.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

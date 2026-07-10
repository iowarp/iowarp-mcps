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


def main() -> int:
    """Run the live semantic JARVIS MCP probe."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True)
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    config_dir = root / "config"
    private_dir = root / "private"
    shared_dir = root / "shared"
    for path in (config_dir, private_dir, shared_dir):
        path.mkdir(parents=True, exist_ok=True)

    uvx = str(Path.home() / ".local" / "bin" / "uvx")
    base_cmd = [uvx, "--from", args.wheel]
    env = os.environ.copy()
    env["JARVIS_MCP_SCHEDULER"] = "slurm"

    admin = McpClient(base_cmd + ["jarvis-admin-mcp"], env=env)
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

    user = McpClient(base_cmd + ["jarvis-mcp"], env=env)
    try:
        user.initialize()
        tools = user.tools()
        expected = [
            "jarvis_create_pipeline",
            "jarvis_describe",
            "jarvis_add_step",
            "jarvis_edit_step",
            "jarvis_remove_step",
            "jarvis_run",
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
                "step_id": "echo",
            },
        )
        scripted_result = user.call_tool(
            "jarvis_run",
            {
                "pipeline_id": pipeline_id,
                "execution": {"mode": "cluster"},
                "submit": False,
            },
        )
        submitted_result = user.call_tool(
            "jarvis_run",
            {
                "pipeline_id": pipeline_id,
                "execution": {"mode": "cluster"},
                "submit": True,
                "wait": True,
            },
        )
        print(
            json.dumps(
                {
                    "tools": tools,
                    "pipeline_id": pipeline_id,
                    "create": create_result,
                    "add": add_result,
                    "scripted": scripted_result,
                    "submitted": submitted_result,
                },
                indent=2,
            )
        )
    finally:
        user.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

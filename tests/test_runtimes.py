"""Per-runtime pinning, building and starting of an embedded MCP server.

The locked-runtime guarantee is the same in every language: source and lock
hash into an environment identity, the environment is built from the lock
without resolving, and the server starts from what was built. Only the files
carrying the pin and the commands realising it differ.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from clio_kit import (
    _build_locked_environment,
    _runtime_project_files,
    locked_server_command,
    locked_server_project_identity,
    materialize_locked_server_project,
)
from clio_kit.discovery import read_server_descriptor
from clio_kit.runtimes import (
    UnsupportedRuntime,
    build_command,
    build_runs_in_project,
    generated_directories,
    lock_file_name,
    required_project_files,
    start_command,
)

NODE_SERVER = """\
const readline = require("readline");
const rl = readline.createInterface({ input: process.stdin });
rl.on("line", (line) => {
  let msg; try { msg = JSON.parse(line); } catch { return; }
  if (msg.method === "initialize") {
    process.stdout.write(JSON.stringify({
      jsonrpc: "2.0", id: msg.id,
      result: { serverInfo: { name: "crystal", version: "1.0.0" } }
    }) + "\\n");
  }
});
"""


def _node_server(root: Path) -> Path:
    server = root / "crystal"
    server.mkdir(parents=True)
    (server / "package.json").write_text(
        json.dumps({"name": "crystal-mcp", "version": "1.0.0", "private": True}),
        encoding="utf-8",
    )
    (server / "package-lock.json").write_text(
        json.dumps(
            {
                "name": "crystal-mcp",
                "version": "1.0.0",
                "lockfileVersion": 3,
                "requires": True,
                "packages": {"": {"name": "crystal-mcp", "version": "1.0.0"}},
            }
        ),
        encoding="utf-8",
    )
    (server / "server.js").write_text(NODE_SERVER, encoding="utf-8")
    (server / "clio-server.toml").write_text(
        'name = "crystal"\nruntime = "node"\n'
        'lock = "package-lock.json"\nentry = "server.js"\n',
        encoding="utf-8",
    )
    return server


def test_each_runtime_pins_with_its_own_lock() -> None:
    assert required_project_files("python") == ("pyproject.toml", "uv.lock")
    assert required_project_files("node") == ("package.json", "package-lock.json")
    assert required_project_files("go") == ("go.mod", "go.sum")
    assert lock_file_name("node") == "package-lock.json"


def test_build_output_is_never_part_of_the_identity() -> None:
    """Hashing a build artefact would give every rebuild a new identity.

    The environment is addressed by that identity, so the cache would never
    hit and every launch would rebuild from scratch.
    """
    assert "node_modules" in generated_directories("node")
    assert "bin" in generated_directories("go")
    # Python's build output is `dist` (wheels and sdists). It is owned here
    # rather than in a shared exclusion list because the same name is a node
    # server's *shipped* artifact -- see the dist regression tests below.
    assert generated_directories("python") == frozenset({"dist"})


def test_every_build_command_refuses_to_resolve() -> None:
    """A build that resolves is a build whose result is not a function of the lock."""
    project = Path("/srv/project")

    assert build_command("python", project, executable="uv") == [
        "uv",
        "sync",
        "--frozen",
        "--no-dev",
        "--project",
        str(project),
    ]
    # `npm ci` installs the locked tree exactly and fails when the lock and the
    # manifest disagree; `npm install` would quietly rewrite the lock.
    assert build_command("node", project, executable="npm") == [
        "npm",
        "ci",
        "--omit=dev",
    ]
    assert build_runs_in_project("node") and not build_runs_in_project("python")


def test_start_commands_run_what_was_built(tmp_path: Path) -> None:
    assert start_command("node", tmp_path, "server.js", executable="npm") == [
        "node",
        str(tmp_path / "server.js"),
    ]
    assert start_command("go", tmp_path, "mesh", executable="go") == [
        str(tmp_path / "bin" / "server")
    ]


def test_an_unstartable_runtime_fails_by_name() -> None:
    """A missing toolchain must not surface as a confusing missing-file error."""
    with pytest.raises(UnsupportedRuntime, match="haskell"):
        required_project_files("haskell")


def test_a_server_without_its_lock_is_refused(tmp_path: Path) -> None:
    """The same refusal as Python: no lock means an unpinned resolution."""
    server = tmp_path / "crystal"
    server.mkdir()
    (server / "package.json").write_text("{}", encoding="utf-8")

    with pytest.raises(Exception, match="package-lock.json"):
        locked_server_command(server, "server.js", "node")


@pytest.mark.skipif(
    subprocess.run(["which", "npm"], capture_output=True).returncode != 0,
    reason="npm is not installed",
)
def test_a_node_server_builds_from_its_lock_and_speaks_mcp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End to end: descriptor, identity, locked build, and a JSON-RPC reply."""
    monkeypatch.setenv("CLIO_KIT_CACHE_DIR", str(tmp_path / "cache"))
    server = _node_server(tmp_path / "servers")
    descriptor = read_server_descriptor(server)
    assert descriptor is not None and descriptor["runtime"] == "node"

    identity = locked_server_project_identity(server, "node")
    project = materialize_locked_server_project(
        server, identity=identity, runtime="node"
    )
    assert _build_locked_environment("node", project, {"PATH": os.environ["PATH"]})

    # The build wrote node_modules into the project; the identity must not move,
    # or the environment it addresses would be orphaned on every launch.
    assert (
        locked_server_project_identity(project, "node")["project_sha256"]
        == identity["project_sha256"]
    )

    command = locked_server_command(project, descriptor["entry"], "node")
    completed = subprocess.run(
        command,
        input='{"jsonrpc":"2.0","id":1,"method":"initialize"}\n',
        capture_output=True,
        text=True,
        timeout=60,
    )
    reply = json.loads(completed.stdout.strip().splitlines()[0])

    assert reply["result"]["serverInfo"]["name"] == "crystal"


# --- `dist/` means opposite things per runtime -----------------------------
#
# Regression cover for a bug found by taking a real TypeScript MCP server
# through the launcher: `dist` was excluded from every runtime's project files
# because it is Python build output. For a node server it is the *shipped*
# artifact -- the entry point is `dist/server.js` -- so the launcher copied
# everything except the one file it was about to run and died with
# MODULE_NOT_FOUND.


def test_python_still_treats_dist_as_throwaway_build_output() -> None:
    assert "dist" in generated_directories("python")


def test_node_keeps_dist_because_it_is_the_shipped_artifact() -> None:
    assert "dist" not in generated_directories("node")
    assert "node_modules" in generated_directories("node")


def test_a_node_projects_compiled_entry_point_is_carried_into_the_copy(
    tmp_path: Path,
) -> None:
    """The file named by `entry` must survive materialisation."""
    server = tmp_path / "echo-ts"
    (server / "dist").mkdir(parents=True)
    (server / "src").mkdir()
    (server / "node_modules" / "left-pad").mkdir(parents=True)
    (server / "package.json").write_text('{"name":"echo-ts-mcp"}\n', encoding="utf-8")
    (server / "package-lock.json").write_text(
        '{"lockfileVersion":3}\n', encoding="utf-8"
    )
    (server / "dist" / "server.js").write_text("// compiled\n", encoding="utf-8")
    (server / "src" / "server.ts").write_text("// source\n", encoding="utf-8")
    (server / "node_modules" / "left-pad" / "index.js").write_text(
        "x\n", encoding="utf-8"
    )

    carried = {
        path.relative_to(server).as_posix()
        for path in _runtime_project_files(server, "node")
    }
    assert "dist/server.js" in carried, "the entry point must be copied"
    assert "package-lock.json" in carried
    assert not any(name.startswith("node_modules/") for name in carried)


def test_a_python_projects_dist_directory_is_still_left_behind(
    tmp_path: Path,
) -> None:
    """Python identity must not change: dist stays excluded there."""
    server = tmp_path / "demo"
    (server / "dist").mkdir(parents=True)
    (server / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    (server / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (server / "dist" / "demo-1.0.whl").write_text("junk\n", encoding="utf-8")

    carried = {
        path.relative_to(server).as_posix()
        for path in _runtime_project_files(server, "python")
    }
    assert carried == {"pyproject.toml", "uv.lock"}

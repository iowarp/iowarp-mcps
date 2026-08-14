"""How each supported runtime pins, builds and starts an embedded MCP server.

The locked-runtime guarantee is the same in every language: a server's source
and its lock file are hashed into an environment identity, the environment is
built from that lock without resolving anything, and the server starts from the
built environment. What differs per runtime is only which files carry the pin
and which commands realise it, which is what this table holds.

``npm ci`` against ``package-lock.json`` is a genuine equivalent of
``uv sync --frozen``: it installs exactly the locked tree and fails rather than
resolving when the lock disagrees with the manifest. Go's ``go.sum`` carries
content hashes outright, so a build against it is pinned by construction.

One asymmetry is deliberate and visible here rather than hidden: Python server
sources are vendored into the clio-kit wheel and install offline, while a node
server's dependency tree is fetched on first build. A go server is compiled on
first build and then runs as a binary.
"""

from __future__ import annotations

import shutil
from pathlib import Path


class UnsupportedRuntime(Exception):
    """A descriptor names a runtime this launcher cannot start."""


# Per runtime: the manifest and lock that must both be present for a project to
# be launchable, and the generated directory that must never be hashed into the
# environment identity. Hashing a build output would give every rebuild a new
# identity, so the cache would never hit.
RUNTIME_PROJECT_FILES: dict[str, tuple[str, str]] = {
    "python": ("pyproject.toml", "uv.lock"),
    "node": ("package.json", "package-lock.json"),
    "go": ("go.mod", "go.sum"),
}

RUNTIME_GENERATED_DIRECTORIES: dict[str, frozenset[str]] = {
    "python": frozenset(),
    "node": frozenset({"node_modules"}),
    "go": frozenset({"bin"}),
}

# The executable each runtime needs on PATH, and where to point someone when it
# is missing. A server that cannot start because a toolchain is absent should
# say which toolchain.
RUNTIME_TOOLCHAIN: dict[str, tuple[str, str]] = {
    "python": ("uv", "https://github.com/astral-sh/uv"),
    "node": ("npm", "https://nodejs.org"),
    "go": ("go", "https://go.dev/dl/"),
}


def require_runtime(runtime: str) -> None:
    """Fail with the runtime's own name when it is not one we can start."""
    if runtime not in RUNTIME_PROJECT_FILES:
        raise UnsupportedRuntime(
            f"runtime {runtime!r} is not startable by this launcher; "
            f"expected one of {sorted(RUNTIME_PROJECT_FILES)}"
        )


def runtime_executable(runtime: str) -> str:
    """Resolve a runtime's toolchain, preferring an explicit user install.

    Mirrors how the Python path resolves ``uv``: a login shell that never
    sourced a version manager's profile still has the tool under ``~/.local``,
    and failing to find it there turns a working machine into a broken one.
    """
    require_runtime(runtime)
    executable, documentation = RUNTIME_TOOLCHAIN[runtime]
    found = shutil.which(executable)
    if found is not None:
        return found
    local = Path.home() / ".local" / "bin" / executable
    if local.exists():
        return str(local)
    raise UnsupportedRuntime(
        f"{executable!r} is required to start a {runtime} MCP server "
        f"and was not found on PATH -- see {documentation}"
    )


def required_project_files(runtime: str) -> tuple[str, str]:
    """Return the manifest and lock a launchable project of this runtime needs."""
    require_runtime(runtime)
    return RUNTIME_PROJECT_FILES[runtime]


def generated_directories(runtime: str) -> frozenset[str]:
    """Return directories this runtime generates, which must not be hashed."""
    require_runtime(runtime)
    return RUNTIME_GENERATED_DIRECTORIES[runtime]


def lock_file_name(runtime: str) -> str:
    """Return the lock file whose bytes pin this runtime's dependency closure."""
    return required_project_files(runtime)[1]


def build_command(runtime: str, project: Path, *, executable: str) -> list[str]:
    """Return the command that realises a project's lock into a built state.

    Every one of these installs or compiles from the lock alone and fails
    rather than resolving, which is what makes the built environment a function
    of the hashed inputs rather than of when it happened to run.
    """
    require_runtime(runtime)
    if runtime == "python":
        return [executable, "sync", "--frozen", "--no-dev", "--project", str(project)]
    if runtime == "node":
        # npm resolves --prefix inconsistently across versions, so the project
        # is selected by working directory instead; the caller runs it there.
        return [executable, "ci", "--omit=dev"]
    return [executable, "build", "-o", str(project / "bin" / "server"), "./..."]


def start_command(
    runtime: str, project: Path, entry: str, *, executable: str
) -> list[str]:
    """Return the command that starts the server from its built environment."""
    require_runtime(runtime)
    if runtime == "python":
        return [
            executable,
            "run",
            "--no-dev",
            "--no-editable",
            "--frozen",
            "--project",
            str(project),
            entry,
        ]
    if runtime == "node":
        return ["node", str(project / entry)]
    # Go compiled to a fixed path above; `entry` names the binary for humans
    # and for the descriptor, not the file layout.
    return [str(project / "bin" / "server")]


def build_runs_in_project(runtime: str) -> bool:
    """Whether the build command must run with the project as its directory."""
    require_runtime(runtime)
    return runtime in {"node", "go"}

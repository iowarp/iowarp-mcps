"""Tests for real Spack installs: full build log, prefix, typed failures.

clio-kit#370. Covers the four owner-mandated typed outcomes -- success,
recipe-not-found, build-failure, timeout -- plus the composition with
``backend.locate_installed`` that resolves the install prefix, and that the
build log actually lands on disk (not just in the bounded in-memory tail).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spack_mcp import backend, discovery, provisioning


def _available(*, repo: str = "builtin") -> discovery.RecipeAvailability:
    return discovery.RecipeAvailability(
        available=True, repo=repo, repos_searched=[repo], message="available"
    )


def _unavailable() -> discovery.RecipeAvailability:
    return discovery.RecipeAvailability(
        available=False,
        repo=None,
        repos_searched=["builtin"],
        message="no recipe in any registered repo (repos: builtin)",
    )


def _command_result(
    *, returncode: int = 0, stdout: str = "installed", duration_seconds: float = 0.05
) -> backend._CommandResult:
    return backend._CommandResult(
        argv=("spack", "install"),
        returncode=returncode,
        stdout=stdout,
        stderr="",
        duration_seconds=duration_seconds,
    )


def _stub_run_bounded_command(
    monkeypatch: pytest.MonkeyPatch,
    *,
    returncode: int = 0,
    log_body: bytes = b"==> Installing demo\n==> demo: Successfully installed\n",
) -> None:
    def fake(
        argv: list[str], *, env: dict[str, str], timeout_seconds: int, **kwargs: object
    ) -> object:
        for sink_name in ("stdout_sink", "stderr_sink"):
            sink = kwargs.get(sink_name)
            if sink is not None:
                sink(log_body)
        return _command_result(returncode=returncode)

    monkeypatch.setattr(backend, "_run_bounded_command", fake)


@pytest.fixture(autouse=True)
def _stub_executable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend, "_spack_executable", lambda: "/opt/spack/bin/spack")


@pytest.fixture(autouse=True)
def _isolate_log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPACK_MCP_INSTALL_LOG_DIR", str(tmp_path / "install-logs"))


# ── timeout / spec validation ──


def test_install_validates_timeout_bounds() -> None:
    for timeout in (0, provisioning._MAX_INSTALL_TIMEOUT_SECONDS + 1):
        with pytest.raises(backend.SpackBackendError, match="timeout_seconds"):
            provisioning.install_spec("demo", timeout_seconds=timeout)


# ── recipe-not-found: short-circuits before ever invoking spack install ──


def test_install_raises_recipe_not_found_without_invoking_spack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _unavailable())
    invoked: list[object] = []
    monkeypatch.setattr(
        backend, "_run_bounded_command", lambda *a, **k: invoked.append(1) or _command_result()
    )

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("nonexistent", timeout_seconds=60)

    assert error.value.code == "recipe_not_found"
    assert "builtin" in (error.value.detail or "")
    assert invoked == []  # never shelled out once availability said no


# ── build failure: nonzero exit becomes a typed error with log path + tail ──


def test_install_build_failure_carries_log_path_and_tail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    _stub_run_bounded_command(
        monkeypatch, returncode=1, log_body=b"==> Error: build failed for demo\n"
    )

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo@1.0", timeout_seconds=60)

    assert error.value.code == "build_failure"
    assert error.value.returncode == 1
    assert error.value.detail is not None
    assert "log_path=" in error.value.detail
    assert "build failed for demo" in error.value.detail
    # the full log actually landed on disk, not just the bounded in-memory tail
    logged_files = list((tmp_path / "install-logs").glob("*.log"))
    assert len(logged_files) == 1
    assert b"build failed for demo" in logged_files[0].read_bytes()


# ── timeout: distinct from build failure, points at the log for progress ──


def test_install_timeout_is_distinct_from_build_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())

    def fake_timeout(
        argv: list[str], *, env: dict[str, str], timeout_seconds: int, **kwargs: object
    ) -> object:
        sink = kwargs.get("stdout_sink")
        if sink is not None:
            sink(b"==> Installing demo (partial output before timeout)\n")
        raise subprocess.TimeoutExpired(argv, timeout_seconds)

    monkeypatch.setattr(backend, "_run_bounded_command", fake_timeout)

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo@1.0", timeout_seconds=5)

    assert error.value.code == "timed_out"
    assert error.value.detail is not None
    assert "log_path=" in error.value.detail
    logged_files = list((tmp_path / "install-logs").glob("*.log"))
    assert len(logged_files) == 1
    assert b"partial output before timeout" in logged_files[0].read_bytes()


def test_install_launch_failure_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    monkeypatch.setattr(
        backend,
        "_run_bounded_command",
        lambda *a, **k: (_ for _ in ()).throw(OSError("no such file")),
    )

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo@1.0", timeout_seconds=60)

    assert error.value.code == "launch_failed"


# ── success: composes with locate_installed for prefix/load_spec ──


def test_install_success_composes_with_locate_for_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    _stub_run_bounded_command(monkeypatch)
    package = backend.SpackPackage(name="demo", version="1.0", dag_hash="abc123")
    located = backend.SpackLocateResult(
        requested_spec="demo@1.0",
        load_spec="/abc123",
        package=package,
        prefix="/opt/spack/opt/demo-1.0-abc123",
    )
    observed_spec: list[str] = []

    def fake_locate(spec: str) -> backend.SpackLocateResult:
        observed_spec.append(spec)
        return located

    monkeypatch.setattr(backend, "locate_installed", fake_locate)

    result = provisioning.install_spec("demo@1.0", timeout_seconds=60)

    assert observed_spec == ["demo@1.0"]
    assert result.status == "installed"
    assert result.prefix == "/opt/spack/opt/demo-1.0-abc123"
    assert result.load_spec == "/abc123"
    assert result.package == package
    assert result.log_tail  # non-empty; the fake install log was captured
    assert Path(result.log_path).is_file()


def test_install_forwards_reuse_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    observed_argv: list[list[str]] = []

    def fake(
        argv: list[str], *, env: dict[str, str], timeout_seconds: int, **kwargs: object
    ) -> object:
        observed_argv.append(argv)
        return _command_result()

    monkeypatch.setattr(backend, "_run_bounded_command", fake)
    monkeypatch.setattr(
        backend,
        "locate_installed",
        lambda spec: backend.SpackLocateResult(
            requested_spec=spec,
            load_spec="/hash",
            package=backend.SpackPackage(name="demo"),
            prefix="/opt/demo",
        ),
    )

    provisioning.install_spec("demo", reuse=False, timeout_seconds=60)

    assert observed_argv == [["/opt/spack/bin/spack", "install", "--fresh", "demo"]]


# ── post-install observation edge cases ──


def test_install_not_observed_when_locate_finds_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    _stub_run_bounded_command(monkeypatch)

    def fail(spec: str) -> backend.SpackLocateResult:
        raise backend.SpackBackendError("not_installed", "missing", operation="locate")

    monkeypatch.setattr(backend, "locate_installed", fail)

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo", timeout_seconds=60)

    assert error.value.code == "install_not_observed"
    assert "log_path=" in (error.value.detail or "")


def test_install_prefix_ambiguous_when_locate_finds_many(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    _stub_run_bounded_command(monkeypatch)

    def fail(spec: str) -> backend.SpackLocateResult:
        raise backend.SpackBackendError(
            "ambiguous_spec", "many matches", operation="locate", detail="[...]"
        )

    monkeypatch.setattr(backend, "locate_installed", fail)

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo", timeout_seconds=60)

    assert error.value.code == "install_prefix_ambiguous"


def test_install_reraises_unrelated_locate_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(discovery, "classify_recipe_availability", lambda name: _available())
    _stub_run_bounded_command(monkeypatch)

    def fail(spec: str) -> backend.SpackLocateResult:
        raise backend.SpackBackendError("missing_dag_hash", "no hash", operation="locate")

    monkeypatch.setattr(backend, "locate_installed", fail)

    with pytest.raises(backend.SpackBackendError) as error:
        provisioning.install_spec("demo", timeout_seconds=60)

    assert error.value.code == "missing_dag_hash"


# ── log tail bounding ──


def test_read_tail_truncates_large_logs(tmp_path: Path) -> None:
    log_path = tmp_path / "big.log"
    log_path.write_bytes(b"a" * 20_000 + b"TAIL")

    tail = provisioning._read_tail(log_path, max_bytes=100)

    assert tail.startswith("[log truncated]")
    assert tail.endswith("TAIL")


def test_read_tail_handles_missing_file(tmp_path: Path) -> None:
    tail = provisioning._read_tail(tmp_path / "does-not-exist.log")

    assert "could not read log tail" in tail


def test_new_log_path_slugifies_spec(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SPACK_MCP_INSTALL_LOG_DIR", str(tmp_path / "logs"))

    path = provisioning._new_log_path("py-numpy@1.2 +mpi ^mpich")

    assert path.parent == tmp_path / "logs"
    assert " " not in path.name
    assert path.name.startswith("py-numpy")

"""Real child temp/build/install containment, crash recovery, and cleanup failures."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
import uuid
from pathlib import Path

import pytest
import psutil

from scripts.test_run_policy import ROOT_ENV, SCHEMA, TestRun, _remove, run_base

CHECKOUT = Path(__file__).resolve().parents[1]


def test_cleanup_rejects_paths_outside_owned_base(tmp_path: Path) -> None:
    outside = tmp_path / "unrelated"
    outside.mkdir()
    (outside / "owner.json").write_text(
        json.dumps({"schema": SCHEMA, "checkout": str(CHECKOUT)})
    )
    with pytest.raises(RuntimeError, match="outside the owned run root"):
        _remove(outside, tmp_path / "owned", CHECKOUT)
    assert (outside / "owner.json").exists()


def test_pytest_state_is_inside_the_lease(
    tmp_path: Path, pytestconfig: pytest.Config
) -> None:
    root = Path(os.environ[ROOT_ENV])
    assert tmp_path.is_relative_to(root)
    assert pytestconfig.cache is not None
    assert pytestconfig.cache._cachedir.is_relative_to(root)
    assert Path(sys.pycache_prefix).is_relative_to(root)
    for key in ("CLIO_ARC_STORE_CONFIG", "CLIO_SERVER_CONF"):
        if os.environ.get(key):
            assert Path(os.environ[key]).is_relative_to(root)


def test_child_uv_build_install_and_temp_never_use_host_caches(tmp_path: Path) -> None:
    """A real uv build/install and Python import write only in the leased run."""
    uv = shutil.which("uv")
    assert uv is not None
    token = "clio_containment_" + uuid.uuid4().hex[:12]
    host = Path(os.environ["CLIO_TEST_HOST_PROFILE"])
    global_temp = host / "AppData" / "Local" / "Temp"
    global_uv = host / "AppData" / "Local" / "uv" / "cache"
    script = tmp_path / "probe.py"
    script.write_text(
        textwrap.dedent("""
        import json, os, pathlib, subprocess, sys, tempfile
        from scripts.test_run_policy import ROOT_ENV, TestRun
        checkout, uv, token = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
        run = TestRun(checkout, borrow=False)
        root = run.root
        try:
            path = pathlib.Path(tempfile.mkdtemp(prefix=token))
            assert path.is_relative_to(root)
            for key in ("TEMP", "TMP", "TMPDIR", "UV_CACHE_DIR", "PIP_CACHE_DIR",
                        "PYTHONPYCACHEPREFIX", "CLIO_USER_DIR", "CLIO_RUNTIME_STATE_DIR"):
                assert pathlib.Path(os.environ[key]).is_relative_to(root), key
            cache = subprocess.check_output([uv, "cache", "dir"], text=True).strip()
            assert pathlib.Path(cache).is_relative_to(root)
            project = root / "project"
            project.mkdir()
            (project / "pyproject.toml").write_text('[build-system]\\nrequires=[]\\nbuild-backend="backend"\\nbackend-path=["."]\\n')
            backend = "import pathlib, zipfile\\n"
            backend += "def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):\\n"
            backend += " name = " + repr(token) + "\\n"
            backend += " filename = name + '-1.0-py3-none-any.whl'\\n"
            backend += " with zipfile.ZipFile(pathlib.Path(wheel_directory)/filename, 'w') as z:\\n"
            backend += "  z.writestr(name+'/__init__.py', 'value = 42\\\\n')\\n"
            backend += "  info = name + '-1.0.dist-info/'\\n"
            backend += "  z.writestr(info+'METADATA', 'Metadata-Version: 2.1\\\\nName: '+name+'\\\\nVersion: 1.0\\\\n')\\n"
            backend += "  z.writestr(info+'WHEEL', 'Wheel-Version: 1.0\\\\nGenerator: containment-test\\\\nRoot-Is-Purelib: true\\\\nTag: py3-none-any\\\\n')\\n"
            backend += "  z.writestr(info+'RECORD', '')\\n"
            backend += " return filename\\n"
            (project / "backend.py").write_text(backend)
            output = root / "wheels"
            subprocess.run([uv, "build", "--offline", "--wheel", "--no-build-isolation", "--project", str(project), "--out-dir", str(output)], check=True)
            environment = root / "runtime"
            subprocess.run([uv, "venv", "--python", sys.executable, str(environment)], check=True)
            python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            wheel = next(output.glob("*.whl"))
            subprocess.run([uv, "pip", "install", "--offline", "--python", str(python), str(wheel)], check=True)
            subprocess.run([str(python), "-c", f"import {token}; assert {token}.value == 42"], check=True)
            assert any((root / "bytecode").rglob("*.pyc"))
            print(json.dumps({"root": str(root), "temp": str(path), "cache": cache}))
        finally:
            run.close()
        assert not root.exists()
    """),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(CHECKOUT)
    # Deliberately supply the host locations; the policy must override them.
    environment.update(
        {
            "TEMP": str(global_temp),
            "TMP": str(global_temp),
            "TMPDIR": str(global_temp),
            "UV_CACHE_DIR": str(global_uv),
        }
    )
    result = subprocess.run(
        [sys.executable, str(script), str(CHECKOUT), uv, token],
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(result.stdout.splitlines()[-1])
    assert not Path(evidence["root"]).exists()
    assert not list(global_temp.glob(token + "*"))
    assert not list(global_uv.rglob(token + "*"))


def test_dead_run_recovery_preserves_live_run(tmp_path: Path) -> None:
    """An OS-released lease is recoverable; a live test run is not deleted."""
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    live = TestRun(checkout, borrow=False)
    try:
        code = "from pathlib import Path; import os,sys,subprocess; from scripts.test_run_policy import TestRun; r=TestRun(Path(sys.argv[1]),borrow=False); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); (r.root/'orphan.pid').write_text(str(p.pid)); print(r.root,flush=True); os._exit(7)"
        env = {**os.environ, "PYTHONPATH": str(CHECKOUT)}
        child = subprocess.run(
            [sys.executable, "-c", code, str(checkout)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        assert child.returncode == 7
        abandoned = Path(child.stdout.strip())
        assert abandoned.exists()
        orphan_pid = int((abandoned / "orphan.pid").read_text())
        recovered = TestRun(checkout, borrow=False)
        try:
            assert not abandoned.exists()
            assert not psutil.pid_exists(orphan_pid)
            assert live.root.exists()
        finally:
            recovered.close()
    finally:
        live.close()
    assert list(run_base(checkout).glob("run-*")) == []


def test_cleanup_error_is_visible_and_recoverable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    run = TestRun(checkout, borrow=False)
    real_remove = shutil.rmtree

    def denied(path: Path) -> None:
        raise PermissionError("held test file")

    monkeypatch.setattr(shutil, "rmtree", denied)
    with pytest.raises(RuntimeError, match="TEST CLEANUP FAILED"):
        run.close()
    assert run.root.exists()
    monkeypatch.setattr(shutil, "rmtree", real_remove)
    recovered = TestRun(checkout, borrow=False)
    assert not run.root.exists()
    recovered.close()


@pytest.mark.parametrize("code", [0, 3])
def test_runner_cleanup_on_success_and_failure(tmp_path: Path, code: int) -> None:
    """The runner's finally block cleans even when its child returns failure."""
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location(
        "owned_test_runner", CHECKOUT / "scripts" / "run_tests.py"
    )
    assert spec is not None and spec.loader is not None
    sys.path.insert(0, str(CHECKOUT / "scripts"))
    try:
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["run_tests.py", "-q"])
        seen: list[Path] = []

        def child(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            seen.append(Path(os.environ[ROOT_ENV]))
            assert seen[0].is_dir()
            return subprocess.CompletedProcess([], code)

        patch.setattr(module.subprocess, "run", child)
        assert module.main() == code
        assert not seen[0].exists()

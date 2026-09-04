"""Contain direct pytest invocations before repository test modules import."""

import os
from pathlib import Path

import pytest

from scripts.test_run_policy import TestRun

_RUN = TestRun(Path(__file__).resolve().parent)


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:
    """Force pytest state below the same leased root as subprocess caches."""
    config.add_cleanup(_RUN.close)
    requested = config.option.basetemp
    if requested is not None and not Path(requested).resolve().is_relative_to(
        _RUN.root
    ):
        raise pytest.UsageError(
            "--basetemp must be inside CLIO_TEST_RUN_ROOT; use scripts/run_tests.py"
        )
    config.option.basetemp = str(
        Path(requested) if requested else _RUN.root / f"pytest-{os.getpid()}"
    )
    config.inicfg["cache_dir"] = str(_RUN.root / "pytest-cache")
    config._inicache.pop("cache_dir", None)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config: pytest.Config) -> None:
    """Surface cleanup errors even when the test assertions passed."""
    _RUN.close()

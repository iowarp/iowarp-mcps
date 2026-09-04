"""Run pytest through uv with checkout-drive storage and mandatory cleanup."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from test_run_policy import TestRun


def main() -> int:
    """Contain test subprocess state and return a failing code on cleanup failure."""
    checkout = Path(__file__).resolve().parents[1]
    run = TestRun(checkout, borrow=False)
    try:
        uv = shutil.which("uv")
        if uv is None:
            raise RuntimeError("uv is required")
        args = sys.argv[1:]
        if any(arg.startswith("--basetemp") for arg in args):
            raise RuntimeError(
                "The test harness owns --basetemp; use CLIO_TEST_RUNS_DIR for placement"
            )
        print(f"Contained test run: {run.root}", flush=True)
        return subprocess.run(
            [
                uv,
                "run",
                "--no-sync",
                "python",
                "-m",
                "pytest",
                *args,
                "--basetemp",
                str(run.root / "pytest"),
                "-o",
                f"cache_dir={run.root / 'pytest-cache'}",
            ],
            cwd=checkout,
            check=False,
        ).returncode
    finally:
        run.close()


if __name__ == "__main__":
    raise SystemExit(main())

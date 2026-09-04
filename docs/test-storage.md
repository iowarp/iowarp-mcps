# Contained test storage

Run repository tests with an existing development environment:

```sh
uv run --no-sync python -B scripts/run_tests.py tests -q
```

The runner creates an owned run on the checkout drive before invoking pytest
through uv. On Windows the short default is
`<checkout-drive>/.clio-test-runs/<checkout-hash>/run-<id>`; on other systems it is
`<checkout>/.test-runs/run-<id>`. `CLIO_TEST_RUNS_DIR` can select another owned base
on the checkout drive. The runner owns `--basetemp`; do not supply it separately.

The root `conftest.py` applies the same policy to direct pytest invocations before
repository fixtures import. Temporary directories, pytest cache/basetemp, child
uv and pip caches, wheel build/runtime fixtures, Python bytecode, home/app/XDG
directories, matplotlib cache, CLIO user state, and CLIO runtime state all resolve
inside the run. Agent's private CTE fixture therefore writes its configuration,
storage, and coordination state below that same temporary root.

An OS file lease protects live runs. The next invocation recovers abandoned,
marked runs, reaps subprocesses carrying their inherited run marker, and removes
only paths whose canonical location and ownership match this checkout. The
runner cleans on success, test failure, and ordinary exceptions. Cleanup errors
fail visibly and retain ownership metadata for recovery; a successful assertion
summary is not permission to ignore failed cleanup. Only the small base guard
file remains after a clean run.

JUnit reports may be explicitly written outside the temporary run for CI
collection. Keep local reports on the checkout drive. Do not retain virtual
environments or package caches as test reports.

The focused safety gate is:

```sh
uv run --no-sync python -B scripts/run_tests.py tests/test_test_run_policy.py -q
```

It performs a real offline uv wheel build/install and Python import, checks that
its unique package/temp files do not appear in the host Windows temp or global
uv cache, checks pytest/bytecode/CTE paths, exercises orphan recovery, and proves
cleanup errors are reported. Run this gate before broad wheel/runtime validation
after changing the storage policy.

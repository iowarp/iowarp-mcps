# Shared MCP runtime implementation (#1319)

The default execution boundary becomes the CLIO Kit installation, not the MCP
server name. The package manager installs a compatible dependency union once;
each `clio-kit mcp-server NAME` process imports its own server from that same
installation. No per-server venv, solver, source copy, or cache GC runs on this
path. The OS process/permission boundary remains unchanged.

## Alternatives considered

- Prewarming the current per-server environments moves the wait but retains
  duplicated environments and source-driven cache growth. Rejected as the fix.
- Installing every scientific/native dependency for every user removes duplicate
  environments but makes even small installations large and fragile. Rejected
  as the default.
- A compatible dependency union selected at installation time shares the common
  stack while allowing small deployments. Selected. A separate installation is
  appropriate for a demonstrated conflict; OS confinement owns trust isolation.

## Work sequence

1. Publish server dependency extras and a `science` union for ndp, geo, pandas,
   and plot. Keep launcher-only installation lightweight. Resolve the production
   union with uv and record any actual conflicts rather than inventing groups.
2. Generate a catalog at build time containing entry points, requirements, and
   independent source/requirement identities. Ship the existing server sources
   in the wheel. Warm invocation reads this catalog and imports only the selected
   server; source hashing is a build/inspection operation.
3. Make direct shared execution the default. Missing/incompatible dependencies
   fail with the exact installation action. Retain the old source-locked launcher
   only as explicit `--isolated` compatibility mode, never automatic fallback.
4. Add `runtime-info` to report the interpreter, shared prefix, source identity,
   declared dependency identity, and observed dependency inventory. Do not label
   the shared installation as the old per-server lock closure. Invalidate CLIO's
   persisted v1 spawn-diet plans so they cannot silently bypass this change.
5. Validate built-wheel launches and real MCP discovery for all four servers in
   one installed environment. Exercise missing dependencies, source-only changes,
   no-subprocess/no-sync warm invocation, separate processes, inherited workspace
   settings, installation upgrades, and explicit legacy mode.
6. Record installation time separately from startup latency and storage. Confirm
   repeated launches create no per-server environments. Keep old caches untouched
   until explicit maintenance; do not risk deleting environments used by older
   CLIO processes.

## Installation and lifecycle semantics

`uv tool install 'clio-kit[science]'` installs the four-server union once. All
blueprints then use the same `clio-kit mcp-server NAME` launcher. Source developers
use `uv sync --extra science` followed by `uv run --no-sync clio-kit ...`.
Choose the union of extras once for a deployment; per-server `uvx` extras would
create different package-manager environments and are not the recommended setup.

Updates and dependency changes are package-manager operations performed while
the installation's servers are stopped. Side-by-side installations support
overlapping upgrade/rollback deployments. CLIO Kit neither mutates nor garbage
collects the installation while serving. Its existing cache commands manage the
legacy isolated cache only. A source-only edit/reinstall does not create or copy
a dependency runtime in the launcher; package-manager update behavior remains
owned by the chosen install command. Exact lock reproducibility uses the joint
`uv.lock`; inventory-based installations are reported as inventory evidence.

## External artifacts and migration

Python 3.11 is the minimum for the shared launcher. All 24 server directories
have individually selectable extras. Extras mirror index dependencies; direct
URL dependencies remain explicit install inputs because PyPI rejects them in
published package dependency metadata ([packaging documentation](https://setuptools.pypa.io/en/stable/userguide/dependency_management.html#direct-url-dependencies)).
For JARVIS, install the extra and the source project's pinned artifact together:

```sh
uv tool install --with 'jarvis-cd @ https://github.com/grc-iit/jarvis-cd/releases/download/v1.8.0/jarvis_cd-1.8.0-py3-none-any.whl#sha256=2c2e2042d0256bd3d9c117d75aaf00d26d9e814fcbcca9a904abf06399fc1067' 'clio-kit[jarvis]'
```

The launcher checks the external wheel's installed URL/hash evidence. It does
not substitute an index package just because its name or version matches.
MCP Registry manifests include the selected extra and any external artifact
as `uvx --with` arguments; persistent multi-server clients use one union install.

Existing caches are not automatically removed. `clio-kit cache gc --keep 0
--dry-run` previews retirement of all idle legacy environments; omit `--dry-run`
to reclaim them. Live legacy markers still prevent deletion. Shared installations
are managed with the package manager and are outside this cache GC.

For development, regenerate source fingerprints with `uv build` after editing
embedded server source. Runtime labels are explicitly build-recorded evidence,
not a recursive integrity scan of mutable editable sources on each invocation.

These changes are not yet released. CLIO Agent's installer still pins the released
launcher version; qualification must install this branch's built wheel with the
desired extras and point CLIO at that executable. Do not advertise the candidate
as available from PyPI until the paired release is published.

HPC filesystem timings are a separate qualification: local measurements must
not be presented as proof of the reporter's ten-minute startup reduction.

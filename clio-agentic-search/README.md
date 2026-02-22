# clio-agentic-search

Phase 2 MVP of `clio-agentic-search` with multi-store connectors, namespace-scoped config/auth,
and composed multi-namespace retrieval.

## Quick start

```bash
UV_CACHE_DIR=.uv-cache uv sync --all-groups
UV_CACHE_DIR=.uv-cache uv run clio --help
UV_CACHE_DIR=.uv-cache uv run clio seed
UV_CACHE_DIR=.uv-cache uv run clio query --namespace local_fs --q "phase one plan"
UV_CACHE_DIR=.uv-cache uv run clio query --namespaces local_fs,object_s3 --q "phase two plan"
```

## Development commands

The primary workflow is direct `uv run`:

```bash
UV_CACHE_DIR=.uv-cache uv run clio query --namespace local_fs --q "hello world"
UV_CACHE_DIR=.uv-cache uv run uvicorn clio_agentic_search.api.app:app --reload
UV_CACHE_DIR=.uv-cache uv run pytest
UV_CACHE_DIR=.uv-cache uv run ruff check .
UV_CACHE_DIR=.uv-cache uv run ruff format --check .
UV_CACHE_DIR=.uv-cache uv run mypy src
UV_CACHE_DIR=.uv-cache uv run python -m build
UV_CACHE_DIR=.uv-cache uvx ruff check .
```

Make-like aliases are available through `project.scripts`:

```bash
UV_CACHE_DIR=.uv-cache uv run clio-lint
UV_CACHE_DIR=.uv-cache uv run clio-format-check
UV_CACHE_DIR=.uv-cache uv run clio-typecheck
UV_CACHE_DIR=.uv-cache uv run clio-test
UV_CACHE_DIR=.uv-cache uv run clio-build
UV_CACHE_DIR=.uv-cache uv run clio-serve
UV_CACHE_DIR=.uv-cache uv run clio-sync
```

## API

- `GET /health` returns a basic service health payload.
- `GET /version` returns the package version.
- `POST /query` executes end-to-end retrieval and returns citations + trace events.

## Phase 2 features

- Namespace registry lifecycle: `register`, `connect`, `teardown`.
- Filesystem connector with incremental indexing using `mtime + hash`.
- S3-compatible object-store connector (`object_s3`).
- Qdrant-like vector connector (`vector_qdrant`).
- Neo4j-like graph connector (`graph_neo4j`).
- Redis-stream-like KV/log connector (`kv_redis`).
- Canonical data contracts in `src/clio_agentic_search/models/contracts.py`.
- DuckDB storage adapter in `src/clio_agentic_search/storage/duckdb_store.py`.
- Retrieval coordinator with capability negotiation (lexical + vector + metadata + graph + logs).
- Multi-namespace composed query flow in CLI/API with citations and trace capture.
- Namespace-scoped runtime/auth config loaded via `src/clio_agentic_search/core/namespace_config.py`.
- Explicit `clio seed` command for reproducible demo/test data population.

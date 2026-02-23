# clio-agentic-search

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![PyPI version](https://img.shields.io/pypi/v/clio-kit.svg)](https://pypi.org/project/clio-kit/)
[![CI](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml/badge.svg)](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

> **Status: Experimental** — API surface and storage format may change between minor releases. Suitable for research and evaluation; not yet recommended for production workloads.

Part of [**CLIO Kit**](https://github.com/iowarp/clio-kit) — the IoWarp platform's tooling layer for AI agents.

---

Hybrid retrieval engine for scientific computing corpora. Indexes documents into namespace-specific backends and supports lexical (BM25), vector, graph, metadata, and scientific-operator retrieval in one pipeline. DuckDB storage, FastAPI server, async job queue, OpenTelemetry tracing, Prometheus metrics.

## Quick start

```bash
# Via the CLIO Kit launcher (recommended)
uvx clio-kit search serve                    # Start the API server
uvx clio-kit search query --namespace local_fs --q "pressure between 190 and 360 kPa"
uvx clio-kit search index --namespace local_fs
uvx clio-kit search list --namespace local_fs
```

### Development mode

```bash
cd clio-agentic-search
uv sync --all-extras --dev
uv run clio serve                            # Start dev server with hot reload
uv run clio query --namespace local_fs --q "pressure > 200 kPa"
uv run clio index --namespace local_fs
```

## Features

- **Multi-namespace registry** with runtime/auth config bundles
- **Connectors**: filesystem + DuckDB (`local_fs`), S3 object store, Qdrant vector store, Neo4j graph, Redis KV log
- **Scientific retrieval operators**: numeric range (`unit`, `min`, `max`), unit matching, formula targeting (normalized signatures)
- **Background indexing** job API with cancellation tokens and per-namespace serialized execution
- **Retry/backoff** wrappers for connect/index operations
- **Telemetry**: OpenTelemetry tracing (opt-in), Prometheus metrics at `/metrics`

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `GET` | `/version` | Package version |
| `GET` | `/documents?namespace=<ns>` | List indexed documents and chunk counts |
| `POST` | `/query` | Run retrieval, return citations + trace events |
| `POST` | `/jobs/index` | Submit async index job |
| `GET` | `/jobs/{job_id}` | Fetch job status/result |
| `DELETE` | `/jobs/{job_id}` | Request cancellation |
| `GET` | `/metrics` | Prometheus text exposition format |

## CLI commands

| Command | Description |
|---------|-------------|
| `clio query` | Run retrieval queries against a namespace |
| `clio index` | Index documents into a namespace |
| `clio list` | List indexed documents |
| `clio seed` | Seed sample data for testing |
| `clio serve` | Start the FastAPI server |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CLIO_LOCAL_ROOT` | `.` | Root directory for local filesystem connector |
| `CLIO_STORAGE_PATH` | `.clio-agentic-search.duckdb` | DuckDB database path |
| `CLIO_CORS_ORIGINS` | `*` | Allowed CORS origins |
| `CLIO_OTEL_ENABLED` | `false` | Enable OpenTelemetry tracing (`1`/`true`/`yes`) |
| `CLIO_ANN_BACKEND` | `exact` | ANN backend (`hnsw` when `[ann]` extra installed) |
| `CLIO_CACHE_SHARDS` | `16` | Vector index shard count |
| `CLIO_INDEX_DOCUMENT_BATCH_SIZE` | `32` | Documents per index batch |
| `CLIO_LEXICAL_BATCH_SIZE` | `50000` | Lexical posting write batch size |

See source for additional `CLIO_LEXICAL_*`, `CLIO_OBJECT_*`, `CLIO_VECTOR_*`, `CLIO_GRAPH_*`, `CLIO_KV_*` variables.

## Quality checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest --ignore=tests/benchmarks -v
uv run python -m clio_agentic_search.evals.quality_gate
```

## Benchmarks

`tests/benchmarks/test_throughput.py` enforces p95 latency for smaller corpora by default. For 10k-chunk SLO enforcement:

```bash
CLIO_ENFORCE_LARGE_SLO=1 uv run pytest tests/benchmarks/ -v --benchmark-disable -k "10000_chunks"
```

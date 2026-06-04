# clio-agentic-search

[![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD--3--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![PyPI version](https://img.shields.io/pypi/v/clio-kit.svg)](https://pypi.org/project/clio-kit/)
[![CI](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml/badge.svg)](https://github.com/iowarp/clio-kit/actions/workflows/quality_control.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)

> **Status: Experimental** — API surface and storage format may change between minor releases. Suitable for research and evaluation; not yet recommended for production workloads.

Part of [**CLIO Kit**](https://github.com/iowarp/clio-kit) — the IoWarp platform's tooling layer for AI agents.

---

Agentic hybrid retrieval engine for scientific computing corpora. Indexes documents into namespace-specific backends and supports lexical (BM25), vector, graph, metadata, and scientific-operator retrieval in one pipeline, with an optional multi-hop agentic loop that rewrites queries and adapts to each corpus. DuckDB storage, FastAPI server, async job queue, OpenTelemetry tracing, Prometheus metrics.

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

### Optional extras

The core install is lightweight; heavier or backend-specific dependencies ship as extras (`uv sync --extra <name>`):

| Extra | Pulls in | Enables |
|-------|----------|---------|
| `semantic` | sentence-transformers | Transformer embeddings (otherwise a hash embedder is used) |
| `ann` | numpy, hnswlib | Approximate nearest-neighbour vector backend (`CLIO_ANN_BACKEND=hnsw`) |
| `hdf5` | h5py | HDF5 connector (`hdf5_data` namespace) |
| `netcdf` | xarray, netCDF4 | NetCDF connector (`netcdf_data` namespace) |
| `llm` | anthropic, openai | LLM-based query rewriting (`--llm-rewrite`); without it, a rule-based fallback is used |
| `telemetry` | opentelemetry, prometheus-client | Tracing + `/metrics` exposition |
| `eval` | claude-agent-sdk, anthropic | SC26 evaluation harness |

## Features

- **Multi-namespace registry** with runtime/auth config bundles
- **Hybrid retrieval** across lexical (BM25), vector, graph and metadata branches in one pipeline
- **Scientific retrieval operators**: numeric range (`unit`, `min`, `max`), unit matching, formula targeting (normalized signatures)
- **Agentic retrieval**: optional multi-hop loop with LLM query rewriting (with a no-LLM fallback) and SI-unit variant inference
- **Corpus-adaptive strategy**: schema/metadata profiling drives per-query branch selection and content-quality filtering
- **Structured ingestion**: CSV/tabular detection and table-aware chunking alongside text
- **Nine connectors** spanning POSIX, object, vector, graph, KV and science formats — see [Connectors](#connectors)
- **Background indexing** job API with cancellation tokens and per-namespace serialized execution
- **Retry/backoff** wrappers for connect/index operations
- **Telemetry**: OpenTelemetry tracing (opt-in), Prometheus metrics at `/metrics`

## Retrieval pipeline

```
Query → Namespace registry → Retrieval coordinator → parallel branches
          ├── Lexical (BM25)
          ├── Vector (embeddings; hash or transformer)
          ├── Graph (BFS)
          ├── Metadata (schema-aware filters)
          └── Scientific (SI unit conversion + formula normalization)
        → Merge + rerank → Citations + trace events
```

With `--agentic`, the coordinator runs inside an observe–decide–act loop: it
inspects results, rewrites the query (LLM or rule-based), and re-runs branches
until it converges or hits `--max-hops`. A corpus profiler inspects what
metadata each namespace actually provides and adapts branch selection and
quality filtering per query.

## Connectors

| Connector | Namespace | Default registry | Extra required |
|-----------|-----------|:---------------:|----------------|
| Filesystem + DuckDB | `local_fs` | ✅ | — |
| S3 object store | `object_s3` | ✅ | — |
| Qdrant vector store | `vector_qdrant` | ✅ | — |
| HDF5 | `hdf5_data` | ✅ | `hdf5` (h5py is also a core dep) |
| NetCDF | `netcdf_data` | ✅ | `netcdf` |
| Neo4j graph | (configurable) | — | — |
| Redis KV log | (configurable) | — | — |
| IOWarp content store | (configurable) | — | `iowarp_core` wheel |
| NDP datasets | (configurable) | — | `mcp` (for MCP-backed discovery) |

`build_default_registry()` provisions the first five namespaces; the remaining
connectors are available to register explicitly.

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
| `clio query` | Run retrieval queries against a namespace (add `--agentic --max-hops N` for the multi-hop loop, `--llm-rewrite` for LLM query rewriting) |
| `clio index` | Index documents into a namespace |
| `clio list` | List indexed documents |
| `clio seed` | Seed sample data for testing |
| `clio serve` | Start the FastAPI server |

Agentic retrieval is opt-in — a plain `clio query` behaves exactly as before:

```bash
# Single-shot (default)
clio query --namespace local_fs --q "pressure 200 kPa"

# Multi-hop agentic loop (max 3 hops), with LLM query rewriting
clio query --namespace local_fs --q "pressure 200 kPa" --agentic --max-hops 3 --llm-rewrite
```

## Examples

Point the filesystem connector at a folder, index it, then run the queries below.

```bash
export CLIO_LOCAL_ROOT=./docs            # folder of .txt/.md/.csv files
export CLIO_STORAGE_PATH=./clio.duckdb
clio index --namespace local_fs          # build the index
clio list  --namespace local_fs          # show indexed docs + chunk counts
```

**Scientific numeric-range** — match by real unit math, not keywords. Only
documents whose measurements fall in the range are returned:

```bash
# "pressure between 300 and 400 kPa"
clio query --namespace local_fs --q "pressure" --numeric-range "300:400:kPa"

# Same physical range expressed in Pa — finds the same 320 kPa document,
# because values are canonicalized to SI base units before matching.
clio query --namespace local_fs --q "pressure" --numeric-range "300000:400000:Pa"
```

**Formula targeting** — match normalized equation signatures:

```bash
clio query --namespace local_fs --q "newton law" --formula "F=ma"
```

**Agentic multi-hop** — the loop rewrites/expands the query between hops
(here, `kPa` is auto-expanded to its SI variants):

```bash
clio query --namespace local_fs --q "pressure 320 kPa" --agentic --max-hops 3
```

**Science-format connectors** — index HDF5 / NetCDF datasets:

```bash
CLIO_HDF5_ROOT=./h5_files     clio index --namespace hdf5_data
CLIO_NETCDF_ROOT=./nc_files   clio index --namespace netcdf_data   # needs the `netcdf` extra
clio query --namespace hdf5_data --q "compressor pressure"
```

**HTTP API** — start the server and query over HTTP:

```bash
clio serve &                                         # FastAPI on :8000
curl -s localhost:8000/health
curl -s -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"namespace":"local_fs","query":"turbine pressure","top_k":3}'
```

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

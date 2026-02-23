# clio-agentic-search

`clio-agentic-search` is a hybrid retrieval engine for scientific computing corpora. It indexes
documents into namespace-specific backends and supports lexical, vector, graph, metadata, and
scientific-operator retrieval in one pipeline.

## Current scope

- Multi-namespace registry with runtime/auth config bundles.
- Connectors:
  - `local_fs` (filesystem + DuckDB persistence)
  - `object_s3` (in-memory S3-compatible object store + DuckDB)
  - `vector_qdrant` (in-memory vector store)
  - `graph_neo4j` (in-memory graph traversal)
  - `kv_redis` (in-memory log stream retrieval)
- Scientific retrieval operators:
  - numeric range (`unit`, `min`, `max`)
  - unit matching (`unit`, optional `value`)
  - formula targeting (normalized signatures)
- Background indexing job API with cancellation tokens and per-namespace serialized execution.
- Retry wrappers for connect/index operations with exponential backoff.
- Telemetry:
  - tracing (`NoopTracer` by default, OpenTelemetry when enabled)
  - Prometheus-style metrics export at `/metrics`

## Quick start

```bash
UV_CACHE_DIR=.uv-cache uv sync --all-groups
UV_CACHE_DIR=.uv-cache uv run clio --help
UV_CACHE_DIR=.uv-cache uv run clio index --namespace local_fs
UV_CACHE_DIR=.uv-cache uv run clio query --namespace local_fs --q "pressure between 190 and 360 kPa"
UV_CACHE_DIR=.uv-cache uv run uvicorn clio_agentic_search.api.app:app --reload
```

## API

- `GET /health`: liveness probe.
- `GET /version`: package version.
- `GET /documents?namespace=<ns>`: list indexed documents and chunk counts.
- `POST /query`: run retrieval and return citations + trace events.
- `POST /jobs/index`: submit async index job (`namespace`, `full_rebuild`).
- `GET /jobs/{job_id}`: fetch job status/result.
- `DELETE /jobs/{job_id}`: request cancellation.
- `GET /metrics`: Prometheus text exposition format.

## CLI commands

- `clio query`
- `clio index`
- `clio list`
- `clio seed`
- `clio serve`

## Environment variables

- `CLIO_LOCAL_ROOT` (default `.`)
- `CLIO_STORAGE_PATH` (default `.clio-agentic-search.duckdb`)
- `CLIO_CORS_ORIGINS` (default `*`)
- `CLIO_OTEL_ENABLED` (`1`/`true`/`yes` to enable OTel tracer)
- `OTEL_EXPORTER_OTLP_ENDPOINT` (default `http://localhost:4317`)
- `CLIO_ANN_BACKEND` (`exact` default, `hnsw` when `clio-agentic-search[ann]` installed)
- `CLIO_CACHE_SHARDS` (default `16`, vector index shard count)
- `CLIO_VECTOR_WARMUP_ASYNC` (default `1`, background vector index warmup on connect)
- `CLIO_INDEX_DOCUMENT_BATCH_SIZE` (default `32`, batched document bundle writes per index pass)
- `CLIO_LEXICAL_BATCH_SIZE` (default `50000`, lexical posting write batch size)
- `CLIO_LEXICAL_DF_PRUNE_THRESHOLD` (default `0.98`, prune tokens above this chunk-frequency ratio)
- `CLIO_LEXICAL_DF_PRUNE_MIN_CHUNKS` (default `200`, minimum indexed chunks before DF pruning applies)
- `CLIO_LEXICAL_MAX_TOKENS_PER_CHUNK` (default `96`, keep top-frequency tokens per chunk)
- `CLIO_LEXICAL_PRUNE_STOPWORDS` (default `1`, remove built-in stopwords from lexical postings)
- `CLIO_LEXICAL_POSTINGS_COMPRESSION` (`none` default, `gzip` for compressed staging during indexing)
- `CLIO_OBJECT_*`, `CLIO_VECTOR_*`/`CLIO_QDRANT_*`, `CLIO_GRAPH_*`/`CLIO_NEO4J_*`,
  `CLIO_KV_*`/`CLIO_REDIS_*` for namespace-specific connector config

## Quality checks

```bash
UV_CACHE_DIR=.uv-cache uv run ruff check .
UV_CACHE_DIR=.uv-cache uv run ruff format --check .
UV_CACHE_DIR=.uv-cache uv run mypy src/
UV_CACHE_DIR=.uv-cache uv run pytest --ignore=tests/benchmarks
UV_CACHE_DIR=.uv-cache uv run python -m clio_agentic_search.evals.quality_gate
```

## Benchmark note

`tests/benchmarks/test_throughput.py` enforces p95 latency for smaller corpora by default.  
For the 10k-chunk p95 assertion, enable hardware-specific enforcement with:

```bash
CLIO_ENFORCE_LARGE_SLO=1 UV_CACHE_DIR=.uv-cache uv run pytest tests/benchmarks/ -v --benchmark-disable -k "10000_chunks"
```

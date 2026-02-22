# Clio Agentic Search - Execution Plan

## 1) Mission and Scope
Build a production-grade, multi-namespace retrieval agent from scratch (new codebase), using this repository only as architectural reference. The new project must be `uv`-native end-to-end and support:
- Filesystem namespaces
- Object-store namespaces (S3/GCS/Azure Blob)
- Vector-store namespaces
- Graph-store namespaces
- Key-value and log-store namespaces
- Scientific-computing retrieval (tables, formulas, numeric/unit-aware search)

This plan is sequenced to produce usable milestones early while avoiding architecture dead-ends.

## 2) Guiding Principles
- `uv` first: every dev/build/test/runtime flow works via `uv run` or `uvx`.
- Namespace-first architecture: no backend-specific logic in orchestration core.
- Deterministic ingestion and reproducible retrieval quality measurements.
- Observability and evals are first-class, not post-hoc.
- Incremental indexing and scalable retrieval are mandatory from v1.

## 3) Target Architecture
### 3.1 Core Layers
1. `core/` orchestration: planner, tool router, workflow runtime, guardrails.
2. `connectors/` namespace adapters: filesystem, object store, graph, vector, kv/log.
3. `indexing/` extraction, chunking, metadata schema, embedding pipeline.
4. `retrieval/` hybrid coordinator (lexical + vector + metadata + graph + rerank).
5. `storage/` backend-independent record model and storage contracts.
6. `api/` FastAPI + WebSocket + job management.
7. `cli/` Typer-based operational interface.
8. `evals/` benchmark framework for quality/performance/scientific QA.

### 3.2 Canonical Data Contracts
Define shared records for all connectors:
- `NamespaceDescriptor`
- `DocumentRecord`
- `ChunkRecord`
- `EmbeddingRecord`
- `MetadataRecord`
- `CitationRecord`
- `TraceEvent`

All connectors map native data into these models.

### 3.3 Capability Interfaces
Use protocol-style capabilities rather than conditional spaghetti:
- `LexicalSearchCapable`
- `VectorSearchCapable`
- `MetadataFilterCapable`
- `GraphTraversalCapable`
- `StreamingLogCapable`

The retrieval coordinator composes capabilities at runtime per namespace.

## 4) Phased Delivery
## Phase 0 - Bootstrap (Week 1)
Deliverables:
- Initialize `uv` project (`pyproject.toml`, dependency groups, lockfile).
- Create monorepo-like package layout under `src/clio_agentic_search/`.
- Add baseline CLI (`uv run clio --help`) and API health endpoint.
- Add tooling: `ruff`, `pytest`, `pytest-asyncio`, `mypy/pyright` (pick one), `pre-commit`.
- Add Make-like task aliases in `pyproject` scripts or just-document `uv run` commands.

Exit criteria:
- CI green on lint, typecheck, test, build.
- One trivial namespace registered (local filesystem stub).

## Phase 1 - Minimal Viable Platform (Weeks 2-4)
Deliverables:
- Namespace registry + connector lifecycle (`register`, `connect`, `teardown`).
- Filesystem connector with incremental indexing (mtime + hash).
- Canonical storage contracts and default local persistence (DuckDB/Postgres, choose one).
- Retrieval coordinator with lexical + vector + metadata branches.
- Basic reranking hook (pluggable, default heuristic).
- End-to-end query flow with citations and trace capture.

Exit criteria:
- Queries run against local docs with deterministic citations.
- Re-index unchanged corpus shows major speedup vs full rebuild.

## Phase 2 - Multi-Store Expansion (Weeks 5-8)
Deliverables:
- Object store connector (start with S3-compatible API).
- External vector store connector (Qdrant or pgvector first).
- Graph connector (Neo4j or Memgraph first) for relationship traversal.
- KV/log connector abstraction + one implementation (Redis Streams or OpenSearch logs).
- Namespace-scoped auth/config management.

Exit criteria:
- One query can compose results across at least 2 namespace types.
- Capability negotiation works cleanly (no backend if/else in core coordinator).

## Phase 3 - Scientific Retrieval Track (Weeks 6-10, parallel)
Deliverables:
- Structure-aware chunking: tables, equations, captions, sections.
- Numeric/unit extraction and normalization (SI canonicalization).
- Formula-aware indexing (LaTeX/MathML/inline equations).
- Table cell indexing with row/column citations.
- Scientific query operators:
  - numeric range filter
  - unit-aware match
  - formula-targeted retrieval

Exit criteria:
- Scientific benchmark suite with precision@k + numeric exactness + unit consistency.
- Stable reproducibility runs on same corpus.

## Phase 4 - Reliability and Scale (Weeks 9-12)
Deliverables:
- Async job queue for indexing and long-running exploration tasks.
- Cancellation, retry/backoff, dead-letter handling.
- Connection pooling and query/result caching.
- Structured telemetry (OpenTelemetry or equivalent), metrics dashboards.
- Throughput/latency benchmarking harness for large corpora.

Exit criteria:
- Load tests at agreed concurrency and corpus size pass SLOs.
- Observability dashboards identify hot paths and failure classes.

## 5) Recommended Repository Layout
```text
clio-agentic-search/
  pyproject.toml
  uv.lock
  README.md
  docs/
    architecture.md
    operations.md
    scientific-retrieval.md
  src/clio_agentic_search/
    cli/
    api/
    core/
    connectors/
      filesystem/
      object_store/
      vector_store/
      graph_store/
      kv_log_store/
    indexing/
    retrieval/
    storage/
    models/
    telemetry/
  tests/
    unit/
    integration/
    e2e/
    benchmarks/
    scientific/
```

## 6) UV-First Developer Workflow
- Create env + install:
  - `uv sync --all-groups`
- Run CLI:
  - `uv run clio query --namespace local_fs --q "..."`
- Run API:
  - `uv run uvicorn clio_agentic_search.api.app:app --reload`
- Run tests:
  - `uv run pytest`
- Run lint/typecheck:
  - `uv run ruff check .`
  - `uv run ruff format --check .`
  - `uv run mypy src`
- Run tools without local install:
  - `uvx ruff check .`

## 7) Evaluation and Quality Gates
CI must include:
- Lint + formatting checks
- Type checks
- Unit + integration tests
- Coverage threshold (start 70%, ratchet upward)
- Benchmark smoke tests
- Scientific regression tests

Nightly CI:
- Full benchmark suite (latency/throughput/cost)
- Retrieval quality evals (MRR, Recall@k, NDCG)
- Scientific metrics (numeric accuracy, unit correctness, table-cell hit rate)

## 8) Key Design Decisions to Lock Early
1. Storage baseline: DuckDB-first local dev + optional Postgres path.
2. Vector backend primary: Qdrant or pgvector.
3. Graph backend primary: Neo4j.
4. Job system: Arq/Celery/RQ (pick one and standardize).
5. Observability stack: OpenTelemetry + Prometheus/Grafana.
6. Reranker strategy: lightweight cross-encoder first, LLM rerank optional.

## 9) Initial Backlog (First 20 Tickets)
1. Initialize project skeleton and `pyproject.toml`.
2. Add CLI shell command group and config loading.
3. Add FastAPI app with health/version routes.
4. Implement canonical models (`DocumentRecord`, `ChunkRecord`, etc.).
5. Implement namespace registry and base connector protocol.
6. Implement filesystem connector ingest/list/read.
7. Implement chunking v1 + metadata extraction v1.
8. Implement storage adapter v1 and migration setup.
9. Implement embedding service abstraction.
10. Implement lexical retrieval branch.
11. Implement vector retrieval branch.
12. Implement metadata filtering branch.
13. Implement hybrid merge + rerank interface.
14. Implement citation builder and provenance trace.
15. Implement incremental indexer (hash/mtime).
16. Add integration tests for end-to-end local namespace retrieval.
17. Add benchmark harness and baseline dataset.
18. Add scientific parser module (tables/formulas/units).
19. Add scientific retrieval tests and fixtures.
20. Add telemetry instrumentation and dashboard starter.

## 10) Migration / Reference Usage Rules
- Use current repo only for concept/reference, not direct copy.
- Reimplement abstractions cleanly in new package namespace.
- Keep API contracts explicit and versioned.
- Document every subsystem with rationale and alternatives.

## 11) Definition of Done (Program Level)
The platform is “next-level ready” when:
- New namespace type can be added without changing core retrieval orchestrator.
- Large corpus indexing is incremental and resumable.
- Hybrid retrieval quality is benchmarked and continuously monitored.
- Scientific queries return correct numeric/unit/formula/table-grounded answers.
- CLI/API operations are production-observable and operationally stable.

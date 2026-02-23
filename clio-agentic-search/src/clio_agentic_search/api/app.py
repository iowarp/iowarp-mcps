"""FastAPI application bootstrap."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from clio_agentic_search import __version__
from clio_agentic_search.core.namespace_registry import NamespaceRegistry, build_default_registry
from clio_agentic_search.jobs import JobCancelledError, get_job_queue, reset_job_queue
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)
from clio_agentic_search.retry import index_with_retry
from clio_agentic_search.telemetry import get_metrics, get_tracer, reset_telemetry


class NumericRangeRequest(BaseModel):
    unit: str
    minimum: float | None = None
    maximum: float | None = None


class UnitMatchRequest(BaseModel):
    unit: str
    value: float | None = None
    tolerance: float = 1e-9


class ScientificOperatorsRequest(BaseModel):
    numeric_range: NumericRangeRequest | None = None
    unit_match: UnitMatchRequest | None = None
    formula: str | None = None

    def to_domain(self) -> ScientificQueryOperators:
        numeric_range = None
        if self.numeric_range is not None:
            numeric_range = NumericRangeOperator(
                unit=self.numeric_range.unit,
                minimum=self.numeric_range.minimum,
                maximum=self.numeric_range.maximum,
            )

        unit_match = None
        if self.unit_match is not None:
            unit_match = UnitMatchOperator(
                unit=self.unit_match.unit,
                value=self.unit_match.value,
                tolerance=self.unit_match.tolerance,
            )

        return ScientificQueryOperators(
            numeric_range=numeric_range,
            unit_match=unit_match,
            formula=self.formula,
        )


class QueryRequest(BaseModel):
    namespace: str = "local_fs"
    namespaces: list[str] = Field(default_factory=list)
    query: str
    top_k: int = 5
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
    metadata_filters: dict[str, str] = Field(default_factory=dict)
    scientific_operators: ScientificOperatorsRequest = Field(
        default_factory=ScientificOperatorsRequest
    )
    full_reindex: bool = False


class CitationResponse(BaseModel):
    namespace: str
    document_id: str
    chunk_id: str
    uri: str
    snippet: str
    score: float


class TraceResponse(BaseModel):
    stage: str
    message: str
    timestamp_ns: int
    attributes: dict[str, str]


class QueryResponse(BaseModel):
    namespaces: list[str]
    query: str
    indexed_files: dict[str, int]
    skipped_files: dict[str, int]
    removed_files: dict[str, int]
    citations: list[CitationResponse]
    total_count: int
    offset: int
    limit: int
    trace: list[TraceResponse]


# --- Job API models ---


class IndexJobRequest(BaseModel):
    namespace: str = "local_fs"
    full_rebuild: bool = False


class JobResponse(BaseModel):
    job_id: str
    namespace: str
    status: str
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None
    result: dict[str, object] | None = None
    error: str | None = None


@lru_cache(maxsize=1)
def _registry() -> NamespaceRegistry:
    return build_default_registry()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield
    reset_app_state()


app = FastAPI(title="clio-agentic-search", version=__version__, lifespan=_lifespan)

cors_origins = os.environ.get("CLIO_CORS_ORIGINS", "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def _value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    del request
    return JSONResponse(status_code=400, content={"error": str(exc)})


@app.exception_handler(RuntimeError)
async def _runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    del request
    return JSONResponse(status_code=503, content={"error": str(exc)})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    return {"version": __version__}


class DocumentResponse(BaseModel):
    namespace: str
    document_id: str
    uri: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    namespace: str
    documents: list[DocumentResponse]
    total_documents: int
    total_chunks: int


@app.get("/documents", response_model=DocumentListResponse)
def list_documents(namespace: str = "local_fs") -> DocumentListResponse:
    registry = _registry()
    try:
        connector = registry.get_connected(namespace)
    except KeyError as error:
        available = ", ".join(registry.list_namespaces())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown namespace '{namespace}'. Available: {available}",
        ) from error
    storage = getattr(connector, "storage", None)
    if storage is None or not hasattr(storage, "list_documents"):
        raise HTTPException(status_code=400, detail="Namespace does not support document listing")
    summaries = storage.list_documents(namespace)
    docs = [
        DocumentResponse(
            namespace=s.namespace,
            document_id=s.document_id,
            uri=s.uri,
            chunk_count=s.chunk_count,
        )
        for s in summaries
    ]
    return DocumentListResponse(
        namespace=namespace,
        documents=docs,
        total_documents=len(docs),
        total_chunks=sum(d.chunk_count for d in docs),
    )


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    metrics = get_metrics()
    tracer = get_tracer()
    with tracer.start_span("query") as span:
        span.set_attribute("query.text", request.query)
        start = time.perf_counter()
        try:
            result = _execute_query(request)
            return result
        finally:
            elapsed = time.perf_counter() - start
            metrics.observe_query_latency(elapsed)
            metrics.inc_query_count()
            span.set_attribute("query.latency_s", elapsed)


def _execute_query(request: QueryRequest) -> QueryResponse:
    registry = _registry()
    target_namespaces = _dedupe_preserve_order(request.namespaces or [request.namespace])
    connectors = []
    indexed_files: dict[str, int] = {}
    skipped_files: dict[str, int] = {}
    removed_files: dict[str, int] = {}

    for namespace in target_namespaces:
        try:
            connector = registry.get_connected(namespace)
        except KeyError as error:
            available = ", ".join(registry.list_namespaces())
            raise HTTPException(
                status_code=404,
                detail=f"Unknown namespace '{namespace}'. Available namespaces: {available}",
            ) from error
        connectors.append(connector)
        report = connector.index(full_rebuild=request.full_reindex)
        indexed_files[namespace] = report.indexed_files
        skipped_files[namespace] = report.skipped_files
        removed_files[namespace] = report.removed_files

    tracer = get_tracer()
    coordinator = RetrievalCoordinator()
    scientific_operators = request.scientific_operators.to_domain()
    if len(connectors) == 1:
        with tracer.start_span("retrieval.single_namespace"):
            single_result = coordinator.query(
                connector=connectors[0],
                query=request.query,
                top_k=request.top_k,
                metadata_filters=request.metadata_filters,
                scientific_operators=scientific_operators,
            )
        namespaces = [single_result.namespace]
        citations = single_result.citations
        trace = single_result.trace
    else:
        with tracer.start_span("retrieval.multi_namespace"):
            multi_result = coordinator.query_namespaces(
                connectors=connectors,
                query=request.query,
                top_k=request.top_k,
                metadata_filters=request.metadata_filters,
                scientific_operators=scientific_operators,
            )
        namespaces = list(multi_result.namespaces)
        citations = multi_result.citations
        trace = multi_result.trace

    all_citations = [CitationResponse(**asdict(c)) for c in citations]
    total_count = len(all_citations)
    paginated = all_citations[request.offset : request.offset + request.limit]

    return QueryResponse(
        namespaces=namespaces,
        query=request.query,
        indexed_files=indexed_files,
        skipped_files=skipped_files,
        removed_files=removed_files,
        citations=paginated,
        total_count=total_count,
        offset=request.offset,
        limit=request.limit,
        trace=[TraceResponse(**asdict(event)) for event in trace],
    )


# --- Async job endpoints ---


@app.post("/jobs/index", response_model=JobResponse)
async def submit_index_job(request: IndexJobRequest) -> JobResponse:
    registry = _registry()
    if request.namespace not in registry:
        available = ", ".join(registry.list_namespaces())
        raise HTTPException(
            status_code=404,
            detail=f"Unknown namespace '{request.namespace}'. Available: {available}",
        )
    queue = get_job_queue()
    job = queue.submit(namespace=request.namespace, full_rebuild=request.full_rebuild)

    async def _run_index() -> None:
        metrics = get_metrics()
        tracer = get_tracer()
        with tracer.start_span("index.background") as span:
            span.set_attribute("index.namespace", job.namespace)
            queue.mark_running(job.job_id)
            start = time.perf_counter()
            try:
                async with queue.namespace_lock(job.namespace):
                    connector = registry.get_connected(job.namespace)
                    report = await asyncio.to_thread(
                        index_with_retry,
                        connector,
                        full_rebuild=job.full_rebuild,
                        cancellation_token=job.cancellation_token,
                    )
                queue.mark_completed(
                    job.job_id,
                    {
                        "indexed_files": report.indexed_files,
                        "skipped_files": report.skipped_files,
                        "removed_files": report.removed_files,
                        "elapsed_seconds": round(report.elapsed_seconds, 3),
                    },
                )
            except JobCancelledError:
                queue.mark_cancelled(job.job_id)
            except asyncio.CancelledError:
                queue.mark_cancelled(job.job_id)
                raise
            except Exception as exc:
                queue.mark_failed(job.job_id, str(exc))
            finally:
                elapsed = time.perf_counter() - start
                metrics.observe_index_duration(elapsed)

    queue.start(job.job_id, _run_index())
    return _job_to_response(job)


@app.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str) -> JobResponse:
    job = get_job_queue().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return _job_to_response(job)


@app.delete("/jobs/{job_id}", response_model=JobResponse)
async def cancel_job(job_id: str) -> JobResponse:
    queue = get_job_queue()
    job = queue.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    queue.cancel(job_id)
    return _job_to_response(job)


def _job_to_response(job: object) -> JobResponse:
    from clio_agentic_search.jobs import JobRecord

    assert isinstance(job, JobRecord)
    return JobResponse(
        job_id=job.job_id,
        namespace=job.namespace,
        status=job.status.value,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result,
        error=job.error,
    )


# --- Metrics endpoint ---


@app.get("/metrics")
def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(get_metrics().export(), media_type="text/plain; charset=utf-8")


def reset_app_state() -> None:
    if _registry.cache_info().currsize > 0:
        _registry().teardown()
    _registry.cache_clear()
    reset_job_queue()
    reset_telemetry()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped

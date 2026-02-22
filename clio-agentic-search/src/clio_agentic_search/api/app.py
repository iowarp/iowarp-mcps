"""FastAPI application bootstrap."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from functools import lru_cache

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from clio_agentic_search import __version__
from clio_agentic_search.core.namespace_registry import NamespaceRegistry, build_default_registry
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)


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
    trace: list[TraceResponse]


@lru_cache(maxsize=1)
def _registry() -> NamespaceRegistry:
    return build_default_registry()


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    del app
    yield
    _registry().teardown()


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


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
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

    coordinator = RetrievalCoordinator()
    scientific_operators = request.scientific_operators.to_domain()
    if len(connectors) == 1:
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

    return QueryResponse(
        namespaces=namespaces,
        query=request.query,
        indexed_files=indexed_files,
        skipped_files=skipped_files,
        removed_files=removed_files,
        citations=[CitationResponse(**asdict(citation)) for citation in citations],
        trace=[TraceResponse(**asdict(event)) for event in trace],
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        deduped.append(value)
        seen.add(value)
    return deduped

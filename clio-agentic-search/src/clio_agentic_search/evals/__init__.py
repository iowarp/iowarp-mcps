"""Evaluation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from clio_agentic_search.evals.scientific import (
    numeric_exactness,
    precision_at_k,
    unit_consistency,
)

if TYPE_CHECKING:
    from clio_agentic_search.evals.quality_gate import GateResult, GateThresholds


def run_quality_gate(
    thresholds: GateThresholds | None = None,
) -> list[GateResult]:
    from clio_agentic_search.evals.quality_gate import run_quality_gate as _run_quality_gate

    return _run_quality_gate(thresholds)


def __getattr__(name: str) -> Any:
    if name in {"GateResult", "GateThresholds"}:
        from clio_agentic_search.evals import quality_gate as _quality_gate

        return getattr(_quality_gate, name)
    raise AttributeError(name)


__all__ = [
    "GateResult",
    "GateThresholds",
    "numeric_exactness",
    "precision_at_k",
    "run_quality_gate",
    "unit_consistency",
]

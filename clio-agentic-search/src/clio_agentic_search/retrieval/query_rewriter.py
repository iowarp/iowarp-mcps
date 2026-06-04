"""LLM-driven query rewriting for iterative retrieval refinement."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from clio_agentic_search.indexing.scientific import _UNIT_CANONICALIZATION

_SYSTEM_PROMPT = """\
You are a scientific search query optimizer. Given a query and retrieved results, \
decide how to refine the query for better scientific data retrieval.

Strategies:
- "expand": Add related terms discovered in results (e.g., add unit variants, synonyms)
- "narrow": Focus on a specific aspect when results are too broad
- "pivot": Shift to a related measurement or formula when direct match fails
- "done": Results are sufficient, stop iterating

Respond in JSON: {"strategy": "...", "rewritten_query": "...", "reasoning": "..."}\
"""

_VALID_STRATEGIES = frozenset({"expand", "narrow", "pivot", "done"})


@dataclass(frozen=True, slots=True)
class RewriteResult:
    original_query: str
    rewritten_query: str
    strategy: str  # "expand", "narrow", "pivot", "done"
    reasoning: str
    input_tokens: int = 0
    output_tokens: int = 0


class QueryRewriter:
    """Rewrites queries based on retrieval results using an LLM."""

    def __init__(
        self,
        *,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ):
        if not HAS_ANTHROPIC:
            raise RuntimeError("Install anthropic: pip install 'clio-agentic-search[llm]'")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def rewrite(
        self,
        *,
        query: str,
        retrieved_snippets: list[str],
        hop_number: int,
        max_hops: int,
    ) -> RewriteResult:
        """Ask the LLM to decide whether and how to refine the query."""
        snippets_text = "\n---\n".join(retrieved_snippets) if retrieved_snippets else "(none)"
        user_message = (
            f"Current query: {query}\n"
            f"Hop: {hop_number}/{max_hops}\n"
            f"Retrieved snippets:\n{snippets_text}\n\n"
            "Decide: should the query be refined? "
            "If the results already cover the information need, use strategy 'done' "
            "and return the original query unchanged. Otherwise pick expand/narrow/pivot "
            "and provide a rewritten query."
        )

        response = self._client.messages.create(
            model=self._model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()
        result = _parse_llm_response(raw_text, original_query=query)
        input_tokens = getattr(response.usage, "input_tokens", 0)
        output_tokens = getattr(response.usage, "output_tokens", 0)
        return RewriteResult(
            original_query=result.original_query,
            rewritten_query=result.rewritten_query,
            strategy=result.strategy,
            reasoning=result.reasoning,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class FallbackQueryRewriter:
    """Offline query rewriter that expands SI unit variants without an LLM."""

    def rewrite(
        self,
        *,
        query: str,
        retrieved_snippets: list[str],
        hop_number: int,
        max_hops: int,
    ) -> RewriteResult:
        """Expand query with SI unit variants found in the canonicalization table."""
        expanded_terms = _expand_unit_variants(query)
        if expanded_terms:
            rewritten = f"{query} {' '.join(expanded_terms)}"
            return RewriteResult(
                original_query=query,
                rewritten_query=rewritten,
                strategy="expand",
                reasoning=f"Added SI unit variants: {', '.join(expanded_terms)}",
            )
        # No expansion possible — signal completion.
        return RewriteResult(
            original_query=query,
            rewritten_query=query,
            strategy="done",
            reasoning="No unit variants to expand; stopping.",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Build a reverse map: canonical_unit -> set of raw units that share it.
_CANONICAL_GROUPS: dict[str, set[str]] = {}
for _raw, (_canon, *_rest) in _UNIT_CANONICALIZATION.items():
    _CANONICAL_GROUPS.setdefault(_canon, set()).add(_raw)

# Pattern that matches any known unit as a standalone token (case-insensitive).
_KNOWN_UNITS = sorted(_UNIT_CANONICALIZATION.keys(), key=len, reverse=True)
_UNIT_TOKEN_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(u) for u in _KNOWN_UNITS) + r")\b",
    flags=re.IGNORECASE,
)


def _expand_unit_variants(query: str) -> list[str]:
    """Return unit tokens related to units already present in *query*."""
    found_units: set[str] = set()
    for match in _UNIT_TOKEN_PATTERN.finditer(query):
        found_units.add(match.group(1).lower())

    if not found_units:
        return []

    variants: list[str] = []
    seen: set[str] = set(found_units)
    for unit in found_units:
        entry = _UNIT_CANONICALIZATION.get(unit)
        if entry is None:
            continue
        canonical_unit = entry[0]
        siblings = _CANONICAL_GROUPS.get(canonical_unit, set())
        for sibling in sorted(siblings):
            if sibling not in seen:
                variants.append(sibling)
                seen.add(sibling)
    return variants


def _parse_llm_response(raw_text: str, *, original_query: str) -> RewriteResult:
    """Parse JSON from the LLM response, falling back gracefully."""
    # Strip markdown code fences if present.
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return RewriteResult(
            original_query=original_query,
            rewritten_query=original_query,
            strategy="done",
            reasoning=f"LLM returned unparseable response: {raw_text[:200]}",
        )

    strategy = str(data.get("strategy", "done")).lower()
    if strategy not in _VALID_STRATEGIES:
        strategy = "done"

    rewritten = str(data.get("rewritten_query", original_query)).strip()
    if not rewritten:
        rewritten = original_query

    reasoning = str(data.get("reasoning", "")).strip()

    return RewriteResult(
        original_query=original_query,
        rewritten_query=rewritten,
        strategy=strategy,
        reasoning=reasoning,
    )

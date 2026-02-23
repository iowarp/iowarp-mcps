"""Command-line interface for clio."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from clio_agentic_search.core.namespace_registry import build_default_registry
from clio_agentic_search.core.seeding import seed_connector
from clio_agentic_search.retrieval.coordinator import RetrievalCoordinator
from clio_agentic_search.retrieval.scientific import (
    NumericRangeOperator,
    ScientificQueryOperators,
    UnitMatchOperator,
)

_EPILOG = """\
Environment variables:
  CLIO_LOCAL_ROOT      Root directory for local_fs namespace (default: .)
  CLIO_STORAGE_PATH    DuckDB database path (default: .clio-agentic-search.duckdb)
  CLIO_CORS_ORIGINS    Allowed CORS origins for API (default: *)
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="clio",
        description="Clio agentic search CLI.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    query_parser = subparsers.add_parser(
        "query",
        help="Run a namespace query.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    query_parser.add_argument("text", nargs="?", help="Query text.")
    query_parser.add_argument("--q", dest="query_text", help="Query text.")
    query_parser.add_argument(
        "--namespace",
        default="local_fs",
        help="Namespace to query against (default: local_fs).",
    )
    query_parser.add_argument(
        "--namespaces",
        default="",
        help="Comma-separated namespaces for composed multi-namespace query.",
    )
    query_parser.add_argument("--top-k", type=int, default=5, help="Number of citations to return.")
    query_parser.add_argument(
        "--filter",
        action="append",
        default=[],
        help="Metadata filter in key=value format. Can be repeated.",
    )
    query_parser.add_argument(
        "--full-reindex",
        action="store_true",
        help="Force a full reindex before querying.",
    )
    query_parser.add_argument(
        "--numeric-range",
        default="",
        help="Scientific numeric range as min:max:unit (blank min/max allowed).",
    )
    query_parser.add_argument(
        "--unit-match",
        default="",
        help="Scientific unit match as value:unit or unit.",
    )
    query_parser.add_argument(
        "--formula",
        default="",
        help="Formula-targeted retrieval expression.",
    )

    seed_parser = subparsers.add_parser("seed", help="Seed explicit demo/test records.")
    seed_parser.add_argument(
        "--namespace",
        default="",
        help=(
            "Single namespace to seed. If omitted and --namespaces is empty, "
            "all namespaces are seeded."
        ),
    )
    seed_parser.add_argument(
        "--namespaces",
        default="",
        help="Comma-separated namespaces to seed.",
    )

    serve_parser = subparsers.add_parser("serve", help="Start the API server.")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1).")
    serve_parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000).")
    serve_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload on code changes."
    )

    index_parser = subparsers.add_parser("index", help="Index namespaces without querying.")
    index_parser.add_argument(
        "--namespace",
        default="local_fs",
        help="Namespace to index (default: local_fs).",
    )
    index_parser.add_argument(
        "--namespaces",
        default="",
        help="Comma-separated namespaces to index.",
    )
    index_parser.add_argument(
        "--full-reindex",
        action="store_true",
        help="Force a full reindex.",
    )

    list_parser = subparsers.add_parser("list", help="List indexed documents.")
    list_parser.add_argument(
        "--namespace",
        default="local_fs",
        help="Namespace to list documents from (default: local_fs).",
    )

    return parser


def _run_query(
    *,
    text: str,
    namespace: str,
    namespaces: str,
    top_k: int,
    filter_pairs: list[str],
    full_reindex: bool,
    numeric_range: str,
    unit_match: str,
    formula: str,
) -> int:
    registry = build_default_registry()
    filters = _parse_filters(filter_pairs)
    scientific_operators = _parse_scientific_operators(
        numeric_range=numeric_range,
        unit_match=unit_match,
        formula=formula,
    )
    target_namespaces = _resolve_target_namespaces(namespace=namespace, namespaces=namespaces)
    try:
        connectors = []
        index_summaries: list[str] = []
        for target in target_namespaces:
            try:
                connector = registry.get_connected(target)
            except KeyError:
                available = ", ".join(registry.list_namespaces())
                print(
                    f"Unknown namespace '{target}'. Available namespaces: {available}",
                    file=sys.stderr,
                )
                return 2
            connectors.append(connector)
            index_report = connector.index(full_rebuild=full_reindex)
            index_summaries.append(
                "namespace="
                f"{target},indexed={index_report.indexed_files},"
                f"skipped={index_report.skipped_files},removed={index_report.removed_files}"
            )
            if index_report.indexed_files == 0 and index_report.skipped_files == 0:
                print(
                    f"Warning: no documents found in namespace '{target}'. "
                    "Check CLIO_LOCAL_ROOT or directory contents.",
                    file=sys.stderr,
                )

        coordinator = RetrievalCoordinator()
        if len(connectors) == 1:
            result = coordinator.query(
                connector=connectors[0],
                query=text,
                top_k=top_k,
                metadata_filters=filters,
                scientific_operators=scientific_operators,
            )
            result_namespaces = [result.namespace]
            citations = result.citations
            trace = result.trace
        else:
            multi_result = coordinator.query_namespaces(
                connectors=connectors,
                query=text,
                top_k=top_k,
                metadata_filters=filters,
                scientific_operators=scientific_operators,
            )
            result_namespaces = list(multi_result.namespaces)
            citations = multi_result.citations
            trace = multi_result.trace

        for summary in index_summaries:
            print(summary)
        print(f"query={text},namespaces={','.join(result_namespaces)}")
        if citations:
            for citation in citations:
                print(
                    f"citation={citation.namespace}:{citation.uri}#chunk={citation.chunk_id},"
                    f"score={citation.score:.4f},"
                    f"snippet={citation.snippet}"
                )
            if citations[0].score < 0.5:
                print(
                    "note: top score is low — results may not be relevant to your query",
                    file=sys.stderr,
                )
        else:
            total_indexed = sum(int(s.split("indexed=")[1].split(",")[0]) for s in index_summaries)
            print(
                f"No results. {total_indexed} files indexed"
                f" across {len(target_namespaces)} namespaces."
            )
            stage_counts: dict[str, int] = {}
            for event in trace:
                stage_counts[event.stage] = stage_counts.get(event.stage, 0) + 1
            for stage, count in stage_counts.items():
                print(f"  trace: {stage} ({count} events)")
        print(f"trace_events={len(trace)}")
        return 0
    finally:
        registry.teardown()


def _run_index(*, namespace: str, namespaces: str, full_reindex: bool) -> int:
    registry = build_default_registry()
    target_namespaces = _resolve_target_namespaces(namespace=namespace, namespaces=namespaces)
    try:
        for target in target_namespaces:
            try:
                connector = registry.get_connected(target)
            except KeyError:
                available = ", ".join(registry.list_namespaces())
                print(
                    f"Unknown namespace '{target}'. Available namespaces: {available}",
                    file=sys.stderr,
                )
                return 2
            report = connector.index(full_rebuild=full_reindex)
            print(
                f"namespace={target},indexed={report.indexed_files},"
                f"skipped={report.skipped_files},removed={report.removed_files},"
                f"elapsed={report.elapsed_seconds:.2f}s"
            )
        return 0
    finally:
        registry.teardown()


def _run_list(*, namespace: str) -> int:
    registry = build_default_registry()
    try:
        try:
            connector = registry.get_connected(namespace)
        except KeyError:
            available = ", ".join(registry.list_namespaces())
            print(
                f"Unknown namespace '{namespace}'. Available namespaces: {available}",
                file=sys.stderr,
            )
            return 2
        storage = getattr(connector, "storage", None)
        if storage is None or not hasattr(storage, "list_documents"):
            print(f"Namespace '{namespace}' does not support document listing.", file=sys.stderr)
            return 2
        documents = storage.list_documents(namespace)
        if not documents:
            print(f"No documents indexed in namespace '{namespace}'.")
            return 0
        print(f"{'URI':<60} {'Chunks':>6}")
        print("-" * 67)
        for doc in documents:
            print(f"{doc.uri:<60} {doc.chunk_count:>6}")
        total_chunks = sum(d.chunk_count for d in documents)
        print(f"\nTotal: {len(documents)} documents, {total_chunks} chunks")
        return 0
    finally:
        registry.teardown()


def _parse_filters(filter_pairs: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for pair in filter_pairs:
        if "=" not in pair:
            raise ValueError(f"Invalid filter '{pair}'. Expected key=value")
        key, value = pair.split("=", 1)
        parsed[key.strip()] = value.strip()
    return parsed


def _parse_scientific_operators(
    *,
    numeric_range: str,
    unit_match: str,
    formula: str,
) -> ScientificQueryOperators:
    numeric_range_operator: NumericRangeOperator | None = None
    if numeric_range:
        parts = [part.strip() for part in numeric_range.split(":")]
        if len(parts) != 3:
            raise ValueError(
                "Invalid --numeric-range. Expected min:max:unit, with blank min/max allowed."
            )
        minimum_text, maximum_text, unit = parts
        if not unit:
            raise ValueError("Invalid --numeric-range. Unit is required.")
        minimum = float(minimum_text) if minimum_text else None
        maximum = float(maximum_text) if maximum_text else None
        numeric_range_operator = NumericRangeOperator(
            unit=unit,
            minimum=minimum,
            maximum=maximum,
        )

    unit_match_operator: UnitMatchOperator | None = None
    if unit_match:
        parts = [part.strip() for part in unit_match.split(":")]
        if len(parts) == 1 and parts[0]:
            unit_match_operator = UnitMatchOperator(unit=parts[0], value=None)
        elif len(parts) == 2:
            value_text, unit = parts
            if not unit:
                raise ValueError("Invalid --unit-match. Unit is required.")
            unit_match_operator = UnitMatchOperator(unit=unit, value=float(value_text))
        else:
            raise ValueError("Invalid --unit-match. Expected unit or value:unit.")

    return ScientificQueryOperators(
        numeric_range=numeric_range_operator,
        unit_match=unit_match_operator,
        formula=formula.strip() or None,
    )


def _resolve_target_namespaces(*, namespace: str, namespaces: str) -> list[str]:
    parsed = [item.strip() for item in namespaces.split(",") if item.strip()]
    if parsed:
        ordered: list[str] = []
        seen: set[str] = set()
        for item in parsed:
            if item in seen:
                continue
            ordered.append(item)
            seen.add(item)
        return ordered
    return [namespace]


def _run_seed(*, namespace: str, namespaces: str) -> int:
    registry = build_default_registry()
    try:
        if namespace:
            target_namespaces = _resolve_target_namespaces(
                namespace=namespace,
                namespaces=namespaces,
            )
        elif namespaces:
            target_namespaces = _resolve_target_namespaces(namespace="", namespaces=namespaces)
        else:
            target_namespaces = list(registry.list_namespaces())

        for target in target_namespaces:
            try:
                connector = registry.get_connected(target)
            except KeyError:
                available = ", ".join(registry.list_namespaces())
                print(
                    f"Unknown namespace '{target}'. Available namespaces: {available}",
                    file=sys.stderr,
                )
                return 2

            report = seed_connector(connector)
            print(
                "seeded namespace="
                f"{report.namespace},records={report.records_seeded},detail={report.detail}"
            )
        return 0
    finally:
        registry.teardown()


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "query":
        query_text = args.query_text or args.text
        if query_text is None:
            parser.error("query requires text via positional argument or --q")
        try:
            return _run_query(
                text=query_text,
                namespace=args.namespace,
                namespaces=args.namespaces,
                top_k=args.top_k,
                filter_pairs=args.filter,
                full_reindex=args.full_reindex,
                numeric_range=args.numeric_range,
                unit_match=args.unit_match,
                formula=args.formula,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 2
    if args.command == "seed":
        return _run_seed(namespace=args.namespace, namespaces=args.namespaces)
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "clio_agentic_search.api.app:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0
    if args.command == "index":
        return _run_index(
            namespace=args.namespace,
            namespaces=args.namespaces,
            full_reindex=args.full_reindex,
        )
    if args.command == "list":
        return _run_list(namespace=args.namespace)

    parser.print_help()
    return 0

"""
Lightweight, domain-neutral CSV/dataframe profiling.

Profiles an arbitrary CSV file using only the Python standard library so it
stays fast and dependency-light. Reports row/column counts, an inferred dtype
per column, null/blank counts, and min/max/mean for numeric columns. The logic
is generic and makes no assumptions about the meaning of any column.
"""

import csv
import math
import os
from typing import Any, Optional

# Upper bound on rows scanned so a single profile call can never run away on a
# pathologically large file. Mirrors the safety ceiling used elsewhere.
_MAX_CSV_PROFILE_ROWS = 250_000

# Default number of rows retained for statistics when the caller does not
# specify a limit.
_DEFAULT_PROFILE_ROWS = 5000

# Tokens treated as null/blank when inferring dtypes and counting nulls.
_NULL_TOKENS = frozenset({"", "na", "nan", "n/a", "null", "none"})


def _is_null_text(value: Any) -> bool:
    """Return True if ``value`` should be treated as missing/blank."""
    return str(value if value is not None else "").strip().lower() in _NULL_TOKENS


def _to_float(value: Any) -> Optional[float]:
    """Best-effort float coercion that tolerates blanks and non-numeric text."""
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> Optional[int]:
    """Best-effort int coercion (no floats, no scientific notation)."""
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _read_csv_rows(
    path: str, *, max_rows: int
) -> tuple[list[str], list[dict[str, str]], int]:
    """Read up to ``max_rows`` CSV rows.

    Returns the column names, the retained rows (capped at ``max_rows``), and
    the total number of data rows scanned (capped at ``_MAX_CSV_PROFILE_ROWS``).
    """
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        rows: list[dict[str, str]] = []
        total = 0
        for row in reader:
            total += 1
            if len(rows) < max_rows:
                rows.append(
                    {
                        str(key): str(value if value is not None else "")
                        for key, value in row.items()
                    }
                )
            if total >= _MAX_CSV_PROFILE_ROWS:
                break
    return columns, rows, total


def _infer_dtype(values: list[str]) -> str:
    """Infer a coarse dtype for a column from its non-null string values.

    Returns one of: ``empty``, ``integer``, ``float``, ``boolean``, ``string``.
    """
    non_null = [v for v in values if not _is_null_text(v)]
    if not non_null:
        return "empty"

    bool_tokens = {"true", "false", "0", "1", "yes", "no"}
    if all(v.strip().lower() in bool_tokens for v in non_null) and any(
        v.strip().lower() in {"true", "false", "yes", "no"} for v in non_null
    ):
        return "boolean"

    floats = [_to_float(v) for v in non_null]
    if all(f is not None and math.isfinite(f) for f in floats):
        if all(_to_int(v) is not None for v in non_null):
            return "integer"
        return "float"

    return "string"


def _numeric_summary(values: list[str]) -> Optional[dict[str, Any]]:
    """Return count/min/max/mean for a column, or None if it has no numbers."""
    numeric = [
        f for f in (_to_float(v) for v in values) if f is not None and math.isfinite(f)
    ]
    if not numeric:
        return None
    return {
        "count": len(numeric),
        "min": min(numeric),
        "max": max(numeric),
        "mean": sum(numeric) / len(numeric),
    }


def profile_csv(
    data_path: str,
    columns: Optional[list[str]] = None,
    max_rows: Optional[int] = None,
) -> dict:
    """Profile a CSV/dataframe file with generic, domain-neutral statistics.

    Args:
        data_path: Path to a local CSV file to profile.
        columns: Optional subset of columns to restrict the profile to. Columns
            not present in the file are ignored.
        max_rows: Maximum number of data rows to retain for statistics. Defaults
            to 5000 and is capped at 250000.

    Returns:
        A dictionary with ``success`` plus, on success, row/column counts, a
        per-column dtype map, per-column null counts, and a numeric summary
        (min/max/mean) for numeric columns. On failure it contains
        ``success=False`` with ``error`` and ``error_type``.
    """
    try:
        if not os.path.exists(data_path):
            return {
                "success": False,
                "error": f"File not found: {data_path}",
                "error_type": "FileNotFoundError",
            }
        if not os.path.isfile(data_path):
            return {
                "success": False,
                "error": f"Path is not a file: {data_path}",
                "error_type": "IsADirectoryError",
            }

        limit = _DEFAULT_PROFILE_ROWS if max_rows is None else int(max_rows)
        limit = max(1, min(limit, _MAX_CSV_PROFILE_ROWS))

        all_columns, rows, rows_scanned = _read_csv_rows(data_path, max_rows=limit)

        if columns is not None:
            requested = set(columns)
            selected_columns = [c for c in all_columns if c in requested]
        else:
            selected_columns = all_columns

        # Materialize per-column value lists once for reuse across analyses.
        column_values: dict[str, list[str]] = {
            col: [row.get(col, "") for row in rows] for col in selected_columns
        }

        dtypes = {col: _infer_dtype(vals) for col, vals in column_values.items()}
        null_counts = {
            col: sum(1 for v in vals if _is_null_text(v))
            for col, vals in column_values.items()
        }

        numeric_summary: dict[str, dict[str, Any]] = {}
        for col, vals in column_values.items():
            summary = _numeric_summary(vals)
            if summary is not None:
                numeric_summary[col] = summary

        rows_profiled = len(rows)
        return {
            "success": True,
            "file_path": data_path,
            "size_bytes": os.path.getsize(data_path),
            "columns": selected_columns,
            "column_count": len(selected_columns),
            "row_count": rows_scanned,
            "rows_profiled": rows_profiled,
            "row_scan_cap": _MAX_CSV_PROFILE_ROWS,
            "scan_limited": rows_scanned >= _MAX_CSV_PROFILE_ROWS,
            "profile_limited": rows_scanned > rows_profiled,
            "dtypes": dtypes,
            "null_counts": null_counts,
            "numeric_summary": numeric_summary,
            "sample_rows": rows[:3],
            "message": (
                f"Profiled {len(selected_columns)} columns across "
                f"{rows_profiled} of {rows_scanned} scanned rows"
            ),
        }

    except (OSError, csv.Error, UnicodeDecodeError, ValueError) as e:
        return {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }

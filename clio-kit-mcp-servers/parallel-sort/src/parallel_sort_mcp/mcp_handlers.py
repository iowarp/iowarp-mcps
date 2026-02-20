"""
MCP handlers for Parallel Sort server.
These handlers wrap all implementation for MCP protocol compliance.
"""

from typing import Dict, Any, List, Union, Optional
from fastmcp.exceptions import ToolError
from .implementation.sort_handler import sort_log_by_timestamp
from .implementation.statistics_handler import analyze_log_statistics
from .implementation.pattern_detection import detect_patterns
from .implementation.filter_handler import (
    filter_logs,
    filter_by_time_range,
    filter_by_log_level,
    filter_by_keyword,
    apply_filter_preset,
)
from .implementation.export_handler import (
    export_to_json,
    export_to_csv,
    export_to_text,
    export_summary_report,
)
from .implementation.parallel_processor import parallel_sort_large_file


async def sort_log_handler(file_path: str) -> Dict[str, Any]:
    """Handler wrapping the log sorting capability for MCP."""
    try:
        result = await sort_log_by_timestamp(file_path)
        return result
    except Exception as e:
        raise ToolError(f"sort_log failed: {e}") from e


async def parallel_sort_handler(
    file_path: str, chunk_size_mb: int = 100, max_workers: Optional[int] = None
) -> Dict[str, Any]:
    """Handler wrapping the parallel sort capability for MCP."""
    try:
        result = await parallel_sort_large_file(file_path, chunk_size_mb, max_workers)
        return result
    except Exception as e:
        raise ToolError(f"parallel_sort failed: {e}") from e


async def analyze_statistics_handler(file_path: str) -> Dict[str, Any]:
    """Handler wrapping the statistics analysis capability for MCP."""
    try:
        result = await analyze_log_statistics(file_path)
        return result
    except Exception as e:
        raise ToolError(f"analyze_statistics failed: {e}") from e


async def detect_patterns_handler(
    file_path: str, detection_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Handler wrapping the pattern detection capability for MCP."""
    try:
        result = await detect_patterns(file_path, detection_config)
        return result
    except Exception as e:
        raise ToolError(f"detect_patterns failed: {e}") from e


async def filter_logs_handler(
    file_path: str,
    filter_conditions: List[Dict[str, Any]],
    logical_operator: str = "and",
) -> Dict[str, Any]:
    """Handler wrapping the log filtering capability for MCP."""
    try:
        result = await filter_logs(file_path, filter_conditions, logical_operator)
        return result
    except Exception as e:
        raise ToolError(f"filter_logs failed: {e}") from e


async def filter_time_range_handler(
    file_path: str, start_time: str, end_time: str
) -> Dict[str, Any]:
    """Handler wrapping the time range filtering capability for MCP."""
    try:
        result = await filter_by_time_range(file_path, start_time, end_time)
        return result
    except Exception as e:
        raise ToolError(f"filter_time_range failed: {e}") from e


async def filter_level_handler(
    file_path: str, levels: Union[str, List[str]], exclude: bool = False
) -> Dict[str, Any]:
    """Handler wrapping the log level filtering capability for MCP."""
    try:
        result = await filter_by_log_level(file_path, levels, exclude)
        return result
    except Exception as e:
        raise ToolError(f"filter_level failed: {e}") from e


async def filter_keyword_handler(
    file_path: str,
    keywords: Union[str, List[str]],
    case_sensitive: bool = False,
    match_all: bool = False,
) -> Dict[str, Any]:
    """Handler wrapping the keyword filtering capability for MCP."""
    try:
        result = await filter_by_keyword(file_path, keywords, case_sensitive, match_all)
        return result
    except Exception as e:
        raise ToolError(f"filter_keyword failed: {e}") from e


async def filter_preset_handler(file_path: str, preset_name: str) -> Dict[str, Any]:
    """Handler wrapping the filter preset capability for MCP."""
    try:
        result = await apply_filter_preset(file_path, preset_name)
        return result
    except Exception as e:
        raise ToolError(f"filter_preset failed: {e}") from e


async def export_json_handler(
    data: Dict[str, Any], include_metadata: bool = True
) -> Dict[str, Any]:
    """Handler wrapping the JSON export capability for MCP."""
    try:
        result = await export_to_json(data, include_metadata)
        return result
    except Exception as e:
        raise ToolError(f"export_json failed: {e}") from e


async def export_csv_handler(
    data: Dict[str, Any], include_headers: bool = True
) -> Dict[str, Any]:
    """Handler wrapping the CSV export capability for MCP."""
    try:
        result = await export_to_csv(data, include_headers)
        return result
    except Exception as e:
        raise ToolError(f"export_csv failed: {e}") from e


async def export_text_handler(
    data: Dict[str, Any], include_summary: bool = True
) -> Dict[str, Any]:
    """Handler wrapping the text export capability for MCP."""
    try:
        result = await export_to_text(data, include_summary)
        return result
    except Exception as e:
        raise ToolError(f"export_text failed: {e}") from e


async def summary_report_handler(data: Dict[str, Any]) -> Dict[str, Any]:
    """Handler wrapping the summary report capability for MCP."""
    try:
        result = await export_summary_report(data)
        return result
    except Exception as e:
        raise ToolError(f"summary_report failed: {e}") from e

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


async def sort_log_handler(
    file_path: str,
    output_file: Optional[str] = None,
    reverse: bool = False,
) -> Dict[str, Any]:
    """Handler wrapping the log sorting capability for MCP.

    Args:
        file_path: Path to the log file to sort.
        output_file: Path for sorted output file.
        reverse: Sort in descending order.
    """
    try:
        result = await sort_log_by_timestamp(file_path)
        # Apply reverse sorting if requested
        if reverse and "sorted_lines" in result:
            result["sorted_lines"] = list(reversed(result["sorted_lines"]))
        # Write to output file if specified
        if output_file and "sorted_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["sorted_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"sort_log failed: {e}") from e


async def parallel_sort_handler(
    file_path: str,
    output_file: str,
    chunk_size_mb: int = 100,
    num_workers: Optional[int] = None,
) -> Dict[str, Any]:
    """Handler wrapping the parallel sort capability for MCP.

    Args:
        file_path: Path to the large log file.
        output_file: Path for sorted output file.
        chunk_size_mb: Chunk size in MB.
        num_workers: Number of worker processes.
    """
    try:
        result = await parallel_sort_large_file(file_path, chunk_size_mb, num_workers)
        # Write to output file if provided and no error
        if output_file and "sorted_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["sorted_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"parallel_sort failed: {e}") from e


async def analyze_statistics_handler(
    file_path: str, include_patterns: bool = True
) -> Dict[str, Any]:
    """Handler wrapping the statistics analysis capability for MCP.

    Args:
        file_path: Path to the log file.
        include_patterns: Include pattern analysis.
    """
    try:
        result = await analyze_log_statistics(file_path)
        if not include_patterns and "statistics" in result:
            result["statistics"].pop("message_analysis", None)
        return result
    except Exception as e:
        raise ToolError(f"analyze_statistics failed: {e}") from e


async def detect_patterns_handler(
    file_path: str,
    pattern_types: Optional[List[Any]] = None,
    sensitivity: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the pattern detection capability for MCP.

    Args:
        file_path: Path to the log file.
        pattern_types: Types of patterns to detect.
        sensitivity: Detection sensitivity ('low', 'medium', 'high').
    """
    try:
        # Build detection config from individual parameters
        detection_config: Optional[Dict[str, Any]] = None
        if pattern_types is not None or sensitivity is not None:
            detection_config = {}
            if pattern_types is not None:
                detection_config["pattern_types"] = pattern_types
            if sensitivity is not None:
                sensitivity_thresholds = {"low": 4.0, "medium": 3.0, "high": 2.0}
                detection_config["anomaly_threshold"] = sensitivity_thresholds.get(
                    sensitivity, 3.0
                )
        result = await detect_patterns(file_path, detection_config)
        return result
    except Exception as e:
        raise ToolError(f"detect_patterns failed: {e}") from e


async def filter_logs_handler(
    file_path: str,
    filter_conditions: List[Dict[str, Any]],
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the log filtering capability for MCP.

    Args:
        file_path: Path to the log file.
        filter_conditions: List of filter condition dictionaries.
        logical_operator: Logical operator between filters ('AND', 'OR').
        output_file: Path for filtered output.
    """
    try:
        op = logical_operator if logical_operator is not None else "and"
        result = await filter_logs(file_path, filter_conditions, op)
        if output_file and "filtered_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["filtered_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"filter_logs failed: {e}") from e


async def filter_time_range_handler(
    file_path: str,
    start_time: str,
    end_time: str,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the time range filtering capability for MCP.

    Args:
        file_path: Path to the log file.
        start_time: Start timestamp.
        end_time: End timestamp.
        output_file: Path for filtered output.
    """
    try:
        result = await filter_by_time_range(file_path, start_time, end_time)
        if output_file and "filtered_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["filtered_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"filter_time_range failed: {e}") from e


async def filter_level_handler(
    file_path: str,
    levels: Union[str, List[str]],
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the log level filtering capability for MCP.

    Args:
        file_path: Path to the log file.
        levels: List of log levels to include.
        output_file: Path for filtered output.
    """
    try:
        result = await filter_by_log_level(file_path, levels)
        if output_file and "filtered_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["filtered_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"filter_level failed: {e}") from e


async def filter_keyword_handler(
    file_path: str,
    keywords: Union[str, List[str]],
    case_sensitive: bool = False,
    logical_operator: Optional[str] = None,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the keyword filtering capability for MCP.

    Args:
        file_path: Path to the log file.
        keywords: List of keywords to search for.
        case_sensitive: Case sensitive matching.
        logical_operator: Operator between keywords ('AND', 'OR').
        output_file: Path for filtered output.
    """
    try:
        # Map logical_operator to match_all boolean
        match_all = (logical_operator or "").upper() == "AND"
        result = await filter_by_keyword(file_path, keywords, case_sensitive, match_all)
        if output_file and "filtered_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["filtered_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
        return result
    except Exception as e:
        raise ToolError(f"filter_keyword failed: {e}") from e


async def filter_preset_handler(
    file_path: str,
    preset_name: str,
    output_file: Optional[str] = None,
) -> Dict[str, Any]:
    """Handler wrapping the filter preset capability for MCP.

    Args:
        file_path: Path to the log file.
        preset_name: Preset name to apply.
        output_file: Path for filtered output.
    """
    try:
        result = await apply_filter_preset(file_path, preset_name)
        if output_file and "filtered_lines" in result and not result.get("error"):
            with open(output_file, "w", encoding="utf-8") as f:
                for line in result["filtered_lines"]:
                    f.write(line + "\n")
            result["output_file"] = output_file
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

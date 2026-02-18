"""
Multi-condition filtering capability for log processing.
Supports complex filtering operations with multiple criteria and logical operators.
"""

import re
from datetime import datetime
from typing import Dict, Any, List, Union
from enum import Enum


class FilterOperator(Enum):
    """Supported filter operators."""

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    REGEX = "regex"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    BETWEEN = "between"
    IN = "in"
    NOT_IN = "not_in"


class LogicalOperator(Enum):
    """Logical operators for combining conditions."""

    AND = "and"
    OR = "or"
    NOT = "not"


async def filter_logs(
    file_path: str,
    filter_conditions: List[Dict[str, Any]],
    logical_operator: str = "and",
) -> Dict[str, Any]:
    """
    Filter log entries based on multiple conditions.

    Args:
        file_path: Path to the log file to filter
        filter_conditions: List of filter condition dictionaries
        logical_operator: How to combine conditions ("and", "or")

    Returns:
        Dictionary containing filtered results
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        if not lines:
            return {
                "message": "File is empty",
                "filtered_lines": [],
                "total_lines": 0,
                "matched_lines": 0,
            }

        # Parse log entries
        parsed_entries = []
        for i, line in enumerate(lines, 1):
            try:
                entry = parse_log_entry(line.strip())
                entry["line_number"] = i
                parsed_entries.append(entry)
            except ValueError:
                # For filtering, we include invalid entries as-is
                parsed_entries.append(
                    {
                        "line_number": i,
                        "timestamp": None,
                        "level": "",
                        "message": line.strip(),
                        "original_line": line.strip(),
                        "is_valid": False,
                    }
                )

        # Apply filters
        filtered_entries = apply_filters(
            parsed_entries, filter_conditions, logical_operator
        )

        # Extract filtered lines
        filtered_lines = [entry["original_line"] for entry in filtered_entries]

        return {
            "filtered_lines": filtered_lines,
            "total_lines": len(lines),
            "matched_lines": len(filtered_entries),
            "filter_conditions": filter_conditions,
            "logical_operator": logical_operator,
            "match_percentage": round((len(filtered_entries) / len(lines) * 100), 2)
            if lines
            else 0,
            "filtered_at": datetime.now().isoformat(),
            "message": f"Successfully filtered {len(lines)} lines, {len(filtered_entries)} matches found",
        }

    except FileNotFoundError:
        return {"error": f"File not found: {file_path}", "filtered_lines": []}
    except Exception as e:
        return {"error": f"Filtering failed: {str(e)}", "filtered_lines": []}


def parse_log_entry(line: str) -> Dict[str, Any]:
    """Parse a single log line into structured components."""
    timestamp_pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    match = re.search(timestamp_pattern, line)

    if not match:
        raise ValueError("No valid timestamp found")

    timestamp_str = match.group(1)
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    remainder = line[match.end() :].strip()
    parts = remainder.split(" ", 1)

    level = parts[0] if parts else ""
    message = parts[1] if len(parts) > 1 else ""

    return {
        "timestamp": timestamp,
        "level": level.upper(),
        "message": message,
        "original_line": line,
        "is_valid": True,
    }


def apply_filters(
    entries: List[Dict[str, Any]], conditions: List[Dict[str, Any]], logical_op: str
) -> List[Dict[str, Any]]:
    """
    Apply filter conditions to log entries.

    Args:
        entries: List of parsed log entries
        conditions: List of filter conditions
        logical_op: Logical operator to combine conditions

    Returns:
        List of entries that match the filter criteria
    """
    if not conditions:
        return entries

    filtered_entries = []

    for entry in entries:
        if evaluate_entry_conditions(entry, conditions, logical_op):
            filtered_entries.append(entry)

    return filtered_entries


def evaluate_entry_conditions(
    entry: Dict[str, Any], conditions: List[Dict[str, Any]], logical_op: str
) -> bool:
    """
    Evaluate whether an entry matches the filter conditions.

    Args:
        entry: Log entry to evaluate
        conditions: List of filter conditions
        logical_op: Logical operator for combining conditions

    Returns:
        True if entry matches conditions, False otherwise
    """
    if not conditions:
        return True

    results = []
    for condition in conditions:
        result = evaluate_single_condition(entry, condition)
        results.append(result)

    # Apply logical operator
    if logical_op.lower() == "and":
        return all(results)
    elif logical_op.lower() == "or":
        return any(results)
    else:
        # Default to AND
        return all(results)


def evaluate_single_condition(entry: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    """
    Evaluate a single filter condition against a log entry.

    Args:
        entry: Log entry to evaluate
        condition: Single filter condition

    Returns:
        True if condition matches, False otherwise
    """
    try:
        field = condition.get("field", "").lower()
        operator = condition.get("operator", "").lower()
        value = condition.get("value")

        # Get the field value from the entry
        field_value = get_field_value(entry, field)

        # Apply the operator
        return apply_operator(field_value, operator, value)

    except Exception:
        # If condition evaluation fails, return False
        return False


def get_field_value(entry: Dict[str, Any], field: str) -> Any:
    """
    Extract field value from log entry.

    Args:
        entry: Log entry
        field: Field name to extract

    Returns:
        Field value or empty string if field doesn't exist
    """
    # Handle nested field access (e.g., "metadata.user")
    if "." in field:
        parts = field.split(".")
        value = entry
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return ""
        return value

    # Check if field exists directly in entry first
    if field in entry:
        return entry[field]

    field_mapping = {
        "timestamp": entry.get("timestamp"),
        "level": entry.get("level", ""),
        "message": entry.get("message", ""),
        "line": entry.get("original_line", ""),
        "line_number": entry.get("line_number", 0),
    }

    return field_mapping.get(field, "")


def apply_operator(field_value: Any, operator: str, filter_value: Any) -> bool:
    """
    Apply a filter operator to compare field value with filter value.

    Args:
        field_value: Value from log entry field
        operator: Filter operator to apply
        filter_value: Value to compare against

    Returns:
        True if comparison matches, False otherwise
    """
    if field_value is None:
        field_value = ""

    # Convert to string for most operations
    field_str = (
        str(field_value).lower() if isinstance(field_value, str) else str(field_value)
    )
    filter_str = (
        str(filter_value).lower()
        if isinstance(filter_value, str)
        else str(filter_value)
    )

    if operator == FilterOperator.EQUALS.value:
        return field_str == filter_str

    elif operator == FilterOperator.NOT_EQUALS.value:
        return field_str != filter_str

    elif operator == FilterOperator.CONTAINS.value:
        return filter_str in field_str

    elif operator == FilterOperator.NOT_CONTAINS.value:
        return filter_str not in field_str

    elif operator == FilterOperator.STARTS_WITH.value:
        return field_str.startswith(filter_str)

    elif operator == FilterOperator.ENDS_WITH.value:
        return field_str.endswith(filter_str)

    elif operator == FilterOperator.REGEX.value:
        try:
            return bool(re.search(str(filter_value), str(field_value), re.IGNORECASE))
        except re.error:
            return False

    elif operator == FilterOperator.GREATER_THAN.value:
        return compare_values(field_value, filter_value, ">")

    elif operator == FilterOperator.LESS_THAN.value:
        return compare_values(field_value, filter_value, "<")

    elif operator == FilterOperator.BETWEEN.value:
        if isinstance(filter_value, list) and len(filter_value) == 2:
            return compare_values(
                field_value, filter_value[0], ">="
            ) and compare_values(field_value, filter_value[1], "<=")
        return False

    elif operator == FilterOperator.IN.value:
        if isinstance(filter_value, list):
            return field_str in [str(v).lower() for v in filter_value]
        return False

    elif operator == FilterOperator.NOT_IN.value:
        if isinstance(filter_value, list):
            return field_str not in [str(v).lower() for v in filter_value]
        return True

    return False


def compare_values(field_value: Any, filter_value: Any, operator: str) -> bool:
    """
    Compare two values with numeric or datetime comparison.

    Args:
        field_value: Value from log entry
        filter_value: Value to compare against
        operator: Comparison operator (>, <, >=, <=)

    Returns:
        True if comparison is true, False otherwise
    """
    try:
        # Handle datetime comparison
        if isinstance(field_value, datetime):
            if isinstance(filter_value, str):
                try:
                    filter_dt = datetime.fromisoformat(
                        filter_value.replace("Z", "+00:00")
                    )
                except ValueError:
                    try:
                        filter_dt = datetime.strptime(filter_value, "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        return False
            else:
                filter_dt = filter_value

            if operator == ">":
                return field_value > filter_dt
            elif operator in ["<", "less_than"]:
                return field_value < filter_dt
            elif operator in [">=", "greater_than_or_equal"]:
                return field_value >= filter_dt
            elif operator in ["<=", "less_than_or_equal"]:
                return field_value <= filter_dt

        # Handle numeric comparison
        else:
            try:
                field_num = float(field_value)
                filter_num = float(filter_value)

                if operator == ">":
                    return field_num > filter_num
                elif operator in ["<", "less_than"]:
                    return field_num < filter_num
                elif operator in [">=", "greater_than_or_equal"]:
                    return field_num >= filter_num
                elif operator in ["<=", "less_than_or_equal"]:
                    return field_num <= filter_num
                elif operator == "equals":
                    return field_num == filter_num
            except (ValueError, TypeError):
                # Fall back to string comparison
                field_str = str(field_value)
                filter_str = str(filter_value)

                if operator == ">":
                    return field_str > filter_str
                elif operator in ["<", "less_than"]:
                    return field_str < filter_str
                elif operator in [">=", "greater_than_or_equal"]:
                    return field_str >= filter_str
                elif operator in ["<=", "less_than_or_equal"]:
                    return field_str <= filter_str

    except Exception:
        return False

    return False


async def filter_by_time_range(
    file_path: str, start_time: str, end_time: str
) -> Dict[str, Any]:
    """
    Filter log entries by time range.

    Args:
        file_path: Path to the log file
        start_time: Start time in ISO format or 'YYYY-MM-DD HH:MM:SS'
        end_time: End time in ISO format or 'YYYY-MM-DD HH:MM:SS'

    Returns:
        Dictionary containing filtered results
    """
    try:
        # Parse time strings
        start_dt = parse_time_string(start_time)
        end_dt = parse_time_string(end_time)

        filter_conditions = [
            {"field": "timestamp", "operator": "between", "value": [start_dt, end_dt]}
        ]

        return await filter_logs(file_path, filter_conditions, "and")

    except ValueError as e:
        return {"error": f"Invalid time format: {str(e)}", "filtered_lines": []}


async def filter_by_log_level(
    file_path: str, levels: Union[str, List[str]], exclude: bool = False
) -> Dict[str, Any]:
    """
    Filter log entries by log level.

    Args:
        file_path: Path to the log file
        levels: Single level or list of levels to filter
        exclude: If True, exclude these levels instead of including

    Returns:
        Dictionary containing filtered results
    """
    if isinstance(levels, str):
        levels = [levels]

    # Convert to uppercase
    levels = [level.upper() for level in levels]

    operator = "not_in" if exclude else "in"

    filter_conditions = [{"field": "level", "operator": operator, "value": levels}]

    return await filter_logs(file_path, filter_conditions, "and")


async def filter_by_keyword(
    file_path: str,
    keywords: Union[str, List[str]],
    case_sensitive: bool = False,
    match_all: bool = False,
) -> Dict[str, Any]:
    """
    Filter log entries by keywords in the message.

    Args:
        file_path: Path to the log file
        keywords: Single keyword or list of keywords
        case_sensitive: Whether to perform case-sensitive matching
        match_all: If True, all keywords must be present (AND), else any (OR)

    Returns:
        Dictionary containing filtered results
    """
    if isinstance(keywords, str):
        keywords = [keywords]

    filter_conditions = []
    for keyword in keywords:
        filter_conditions.append(
            {
                "field": "message",
                "operator": "contains",
                "value": keyword if case_sensitive else keyword.lower(),
            }
        )

    logical_op = "and" if match_all else "or"

    return await filter_logs(file_path, filter_conditions, logical_op)


def parse_time_string(time_str: str) -> datetime:
    """
    Parse various time string formats.

    Args:
        time_str: Time string to parse

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If time string cannot be parsed
    """
    # Try different formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    # Try ISO format
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        pass

    raise ValueError(f"Unable to parse time string: {time_str}")


# Predefined filter presets
FILTER_PRESETS: Dict[str, Dict[str, Any]] = {
    "errors_only": {
        "description": "Show only ERROR, FATAL, and CRITICAL level entries",
        "conditions": [
            {
                "field": "level",
                "operator": "in",
                "value": ["ERROR", "FATAL", "CRITICAL"],
            }
        ],
        "logical_operator": "and",
    },
    "warnings_and_errors": {
        "description": "Show WARNING, ERROR, FATAL, and CRITICAL level entries",
        "conditions": [
            {
                "field": "level",
                "operator": "in",
                "value": ["WARNING", "WARN", "ERROR", "FATAL", "CRITICAL"],
            }
        ],
        "logical_operator": "and",
    },
    "exclude_debug": {
        "description": "Exclude DEBUG and TRACE level entries",
        "conditions": [
            {"field": "level", "operator": "not_in", "value": ["DEBUG", "TRACE"]}
        ],
        "logical_operator": "and",
    },
    "connection_issues": {
        "description": "Find connection-related issues",
        "conditions": [
            {
                "field": "message",
                "operator": "regex",
                "value": r"(?i)(connection|connect|disconnect|timeout|refused|network)",
            }
        ],
        "logical_operator": "and",
    },
    "authentication_events": {
        "description": "Find authentication-related events",
        "conditions": [
            {
                "field": "message",
                "operator": "regex",
                "value": r"(?i)(auth|login|logout|credential|password|token|permission)",
            }
        ],
        "logical_operator": "and",
    },
}


async def apply_filter_preset(file_path: str, preset_name: str) -> Dict[str, Any]:
    """
    Apply a predefined filter preset.

    Args:
        file_path: Path to the log file
        preset_name: Name of the preset to apply

    Returns:
        Dictionary containing filtered results
    """
    if preset_name not in FILTER_PRESETS:
        return {
            "error": f"Unknown preset: {preset_name}. Available presets: {list(FILTER_PRESETS.keys())}",
            "filtered_lines": [],
        }

    preset = FILTER_PRESETS[preset_name]
    result = await filter_logs(
        file_path, preset["conditions"], preset["logical_operator"]
    )

    # Add preset information to result
    result["preset_used"] = preset_name
    result["preset_description"] = preset["description"]

    return result

"""
Sort handler capability for processing log files.
Sorts log entries by timestamps in YYYY-MM-DD HH:MM:SS format.
"""

import re
import os
from datetime import datetime
from typing import Dict, Any


def parse_timestamp(line: str) -> tuple[datetime, str]:
    """
    Extract and parse timestamp from a log line.

    Args:
        line: Log line to parse

    Returns:
        Tuple of (parsed_datetime, original_line)

    Raises:
        ValueError: If timestamp format is invalid
    """
    # Match YYYY-MM-DD HH:MM:SS pattern
    timestamp_pattern = r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    match = re.search(timestamp_pattern, line)

    if not match:
        raise ValueError(f"No valid timestamp found in line: {line.strip()}")

    timestamp_str = match.group(1)
    try:
        parsed_dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        return parsed_dt, line
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format '{timestamp_str}': {e}")


async def sort_log_by_timestamp(file_path: str) -> Dict[str, Any]:
    """
    Sort log file lines by timestamps in YYYY-MM-DD HH:MM:SS format.

    Args:
        file_path: Path to the log file to sort

    Returns:
        Dictionary containing sorted lines or error information
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            return {
                "error": f"File not found: {file_path}",
                "sorted_lines": [],
                "total_lines": 0,
                "valid_lines": 0,
                "invalid_lines": 0,
            }

        # Read file content
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Handle empty file
        if not lines:
            return {
                "message": "File is empty",
                "sorted_lines": [],
                "total_lines": 0,
                "valid_lines": 0,
                "invalid_lines": 0,
            }

        valid_entries = []
        invalid_lines = []

        # Parse and collect valid timestamp entries
        for i, line in enumerate(lines, 1):
            try:
                parsed_dt, original_line = parse_timestamp(line.strip())
                valid_entries.append((parsed_dt, original_line.strip()))
            except ValueError as e:
                invalid_lines.append(
                    {"line_number": i, "content": line.strip(), "error": str(e)}
                )

        # Sort valid entries by timestamp
        valid_entries.sort(key=lambda x: x[0])
        sorted_lines = [entry[1] for entry in valid_entries]

        result = {
            "sorted_lines": sorted_lines,
            "total_lines": len(lines),
            "valid_lines": len(valid_entries),
            "invalid_lines": len(invalid_lines),
        }

        # Include invalid lines info if any
        if invalid_lines:
            result["invalid_entries"] = invalid_lines
            result["message"] = (
                f"Successfully sorted {len(valid_entries)} lines. {len(invalid_lines)} lines had invalid timestamps."
            )
        else:
            result["message"] = f"Successfully sorted all {len(valid_entries)} lines."

        return result

    except FileNotFoundError:
        return {
            "error": f"File not found: {file_path}",
            "sorted_lines": [],
            "total_lines": 0,
            "valid_lines": 0,
            "invalid_lines": 0,
        }
    except PermissionError:
        return {
            "error": f"Permission denied accessing file: {file_path}",
            "sorted_lines": [],
            "total_lines": 0,
            "valid_lines": 0,
            "invalid_lines": 0,
        }
    except Exception as e:
        return {
            "error": f"Unexpected error processing file: {str(e)}",
            "sorted_lines": [],
            "total_lines": 0,
            "valid_lines": 0,
            "invalid_lines": 0,
        }

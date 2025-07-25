"""
Export handler capability for log processing results.
Supports multiple export formats: JSON, CSV, plain text, and summary reports.
"""

import json
import csv
import io
from datetime import datetime
from typing import Dict, Any, cast


async def export_to_json(
    data: Dict[str, Any], include_metadata: bool = True
) -> Dict[str, Any]:
    """
    Export log processing results to JSON format.

    Args:
        data: Processing results to export
        include_metadata: Whether to include processing metadata

    Returns:
        Dictionary containing JSON export results
    """
    try:
        # Validate input data
        if data is None or not isinstance(data, dict):
            return {
                "error": f"Invalid data type for JSON export: expected dict, got {type(data).__name__}",
                "format": "json",
            }

        export_data = {
            "export_format": "json",
            "exported_at": datetime.now().isoformat(),
            "data": data,
        }

        if not include_metadata:
            # Strip metadata if requested
            clean_data = {
                k: v
                for k, v in data.items()
                if k not in ["_meta", "isError", "export_format", "exported_at"]
            }
            export_data["data"] = clean_data

        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

        return {
            "format": "json",
            "content": json_str,
            "size_bytes": len(json_str.encode("utf-8")),
            "exported_at": export_data["exported_at"],
            "message": f"Successfully exported to JSON format ({len(json_str.encode('utf-8'))} bytes)",
        }

    except Exception as e:
        return {"error": f"JSON export failed: {str(e)}", "format": "json"}


async def export_to_csv(
    data: Dict[str, Any], include_headers: bool = True
) -> Dict[str, Any]:
    """
    Export log entries to CSV format.

    Args:
        data: Processing results containing sorted_lines
        include_headers: Whether to include CSV headers

    Returns:
        Dictionary containing CSV export results
    """
    try:
        if "sorted_lines" not in data:
            return {
                "error": "No sorted_lines found in data for CSV export",
                "format": "csv",
            }

        lines = data["sorted_lines"]
        if not lines:
            return {"error": "No log entries to export", "format": "csv"}

        # Parse log entries into structured data
        csv_data = []
        for i, line in enumerate(lines):
            parts = line.split(" ", 3)  # Split into timestamp, level, and message
            if len(parts) >= 3:
                timestamp = f"{parts[0]} {parts[1]}"
                level = parts[2] if len(parts) > 2 else ""
                message = parts[3] if len(parts) > 3 else ""
            else:
                timestamp = ""
                level = ""
                message = line

            csv_data.append(
                {
                    "line_number": i + 1,
                    "timestamp": timestamp,
                    "level": level,
                    "message": message,
                    "original_line": line,
                }
            )

        # Convert to CSV string
        output = io.StringIO()
        if csv_data:
            fieldnames = csv_data[0].keys()
            writer = csv.DictWriter(output, fieldnames=fieldnames)

            if include_headers:
                writer.writeheader()

            writer.writerows(csv_data)

        csv_content = output.getvalue()
        output.close()

        return {
            "format": "csv",
            "content": csv_content,
            "size_bytes": len(csv_content.encode("utf-8")),
            "exported_at": datetime.now().isoformat(),
            "rows_exported": len(csv_data),
            "headers_included": include_headers,
            "message": f"Successfully exported {len(csv_data)} entries to CSV format",
        }

    except Exception as e:
        return {"error": f"CSV export failed: {str(e)}", "format": "csv"}


async def export_to_text(
    data: Dict[str, Any], include_summary: bool = True
) -> Dict[str, Any]:
    """
    Export log entries to plain text format.

    Args:
        data: Processing results containing sorted_lines
        include_summary: Whether to include processing summary at the top

    Returns:
        Dictionary containing text export results
    """
    try:
        lines = data.get("sorted_lines", [])
        text_content = []

        if include_summary:
            text_content.append("=" * 50)
            text_content.append("LOG PROCESSING SUMMARY")
            text_content.append("=" * 50)
            text_content.append(f"Total lines processed: {data.get('total_lines', 0)}")
            text_content.append(f"Valid entries: {data.get('valid_lines', 0)}")
            text_content.append(f"Invalid entries: {data.get('invalid_lines', 0)}")
            text_content.append(f"Exported at: {datetime.now().isoformat()}")
            text_content.append("")
            text_content.append("SORTED LOG ENTRIES:")
            text_content.append("-" * 50)

        text_content.extend(lines)

        if include_summary and data.get("invalid_entries"):
            text_content.append("")
            text_content.append("INVALID ENTRIES:")
            text_content.append("-" * 50)
            for invalid in data["invalid_entries"]:
                text_content.append(
                    f"Line {invalid['line_number']}: {invalid['content']}"
                )
                text_content.append(f"  Error: {invalid['error']}")

        full_text = "\n".join(text_content)

        return {
            "format": "text",
            "content": full_text,
            "size_bytes": len(full_text.encode("utf-8")),
            "exported_at": datetime.now().isoformat(),
            "lines_exported": len(lines),
            "summary_included": include_summary,
            "message": f"Successfully exported {len(lines)} entries to text format",
        }

    except Exception as e:
        return {"error": f"Text export failed: {str(e)}", "format": "text"}


async def export_summary_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a comprehensive summary report of log processing results.

    Args:
        data: Processing results to summarize

    Returns:
        Dictionary containing summary report
    """
    try:
        lines = data.get("sorted_lines", [])

        # Basic statistics
        total_lines = data.get("total_lines", 0)
        valid_lines = data.get("valid_lines", 0)
        invalid_lines = data.get("invalid_lines", 0)

        # Analyze log levels
        level_counts: Dict[str, int] = {}
        timestamps = []

        for line in lines:
            parts = line.split(" ", 3)
            if len(parts) >= 3:
                level = parts[2].upper()
                level_counts[level] = level_counts.get(level, 0) + 1

                # Extract timestamp for time analysis
                try:
                    timestamp_str = f"{parts[0]} {parts[1]}"
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    timestamps.append(timestamp)
                except ValueError:
                    pass

        # Time analysis
        time_analysis = {}
        if timestamps:
            timestamps.sort()
            time_analysis = {
                "earliest_timestamp": timestamps[0].isoformat(),
                "latest_timestamp": timestamps[-1].isoformat(),
                "time_span_seconds": (timestamps[-1] - timestamps[0]).total_seconds(),
                "total_events": len(timestamps),
            }

        # Generate report
        report = {
            "report_type": "summary",
            "generated_at": datetime.now().isoformat(),
            "processing_statistics": {
                "total_lines_processed": total_lines,
                "valid_entries": valid_lines,
                "invalid_entries": invalid_lines,
                "success_rate": round((valid_lines / total_lines * 100), 2)
                if total_lines > 0
                else 0,
            },
            "log_level_distribution": level_counts,
            "time_analysis": time_analysis,
            "data_quality": {
                "has_invalid_entries": invalid_lines > 0,
                "invalid_entry_details": data.get("invalid_entries", []),
            },
        }

        # Convert to formatted text
        report_text = []
        report_text.append("LOG PROCESSING SUMMARY REPORT")
        report_text.append("=" * 50)
        report_text.append(f"Generated: {report['generated_at']}")
        report_text.append("")

        report_text.append("PROCESSING STATISTICS:")
        processing_stats = cast(Dict[str, Any], report["processing_statistics"])
        report_text.append(
            f"  Total lines processed: {processing_stats['total_lines_processed']}"
        )
        report_text.append(f"  Valid entries: {processing_stats['valid_entries']}")
        report_text.append(f"  Invalid entries: {processing_stats['invalid_entries']}")
        report_text.append(f"  Success rate: {processing_stats['success_rate']}%")
        report_text.append("")

        if level_counts:
            report_text.append("LOG LEVEL DISTRIBUTION:")
            for level, count in sorted(level_counts.items()):
                percentage = (
                    round((count / valid_lines * 100), 1) if valid_lines > 0 else 0
                )
                report_text.append(f"  {level}: {count} ({percentage}%)")
            report_text.append("")

        if time_analysis:
            report_text.append("TIME ANALYSIS:")
            report_text.append(
                f"  Earliest entry: {time_analysis['earliest_timestamp']}"
            )
            report_text.append(f"  Latest entry: {time_analysis['latest_timestamp']}")
            report_text.append(
                f"  Time span: {time_analysis['time_span_seconds']} seconds"
            )
            report_text.append(f"  Total events: {time_analysis['total_events']}")

        report_content = "\n".join(report_text)

        return {
            "format": "summary_report",
            "content": report_content,
            "structured_data": report,
            "size_bytes": len(report_content.encode("utf-8")),
            "exported_at": report["generated_at"],
            "message": "Summary report generated successfully",
        }

    except Exception as e:
        return {
            "error": f"Summary report generation failed: {str(e)}",
            "format": "summary_report",
        }

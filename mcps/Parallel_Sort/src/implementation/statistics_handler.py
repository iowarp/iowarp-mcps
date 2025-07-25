"""
Statistics and analysis handler for log processing.
Provides comprehensive log analysis, statistics, and summaries.
"""
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, Any, List, Tuple
import pandas as pd


async def analyze_log_statistics(file_path: str) -> Dict[str, Any]:
    """
    Analyze log file and generate comprehensive statistics.
    
    Args:
        file_path: Path to the log file to analyze
        
    Returns:
        Dictionary containing detailed log statistics
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return {
                "message": "File is empty",
                "total_lines": 0,
                "statistics": {}
            }
        
        # Parse log entries
        parsed_entries = []
        invalid_entries = []
        
        for i, line in enumerate(lines, 1):
            try:
                entry = parse_log_entry(line.strip())
                entry["line_number"] = i
                parsed_entries.append(entry)
            except ValueError as e:
                invalid_entries.append({
                    "line_number": i,
                    "content": line.strip(),
                    "error": str(e)
                })
        
        # Generate statistics
        stats = {
            "basic_statistics": generate_basic_statistics(lines, parsed_entries, invalid_entries),
            "temporal_analysis": generate_temporal_analysis(parsed_entries),
            "log_level_analysis": generate_log_level_analysis(parsed_entries),
            "message_analysis": generate_message_analysis(parsed_entries),
            "quality_metrics": generate_quality_metrics(lines, parsed_entries, invalid_entries)
        }
        
        return {
            "total_lines": len(lines),
            "valid_entries": len(parsed_entries),
            "invalid_entries": len(invalid_entries),
            "statistics": stats,
            "invalid_entry_details": invalid_entries[:10],  # Limit to first 10 for brevity
            "analyzed_at": datetime.now().isoformat(),
            "message": f"Successfully analyzed {len(lines)} lines with {len(parsed_entries)} valid entries"
        }
        
    except FileNotFoundError:
        return {
            "error": f"File not found: {file_path}",
            "statistics": {}
        }
    except Exception as e:
        return {
            "error": f"Analysis failed: {str(e)}",
            "statistics": {}
        }


def parse_log_entry(line: str) -> Dict[str, Any]:
    """
    Parse a single log line into structured components.
    
    Args:
        line: Log line to parse
        
    Returns:
        Dictionary with parsed components
        
    Raises:
        ValueError: If line cannot be parsed
    """
    # Match YYYY-MM-DD HH:MM:SS pattern
    timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
    match = re.search(timestamp_pattern, line)
    
    if not match:
        raise ValueError(f"No valid timestamp found")
    
    timestamp_str = match.group(1)
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    except ValueError as e:
        raise ValueError(f"Invalid timestamp format: {e}")
    
    # Extract remaining parts
    remainder = line[match.end():].strip()
    parts = remainder.split(' ', 1)
    
    level = parts[0] if parts else ""
    message = parts[1] if len(parts) > 1 else ""
    
    return {
        "timestamp": timestamp,
        "timestamp_str": timestamp_str,
        "level": level.upper(),
        "message": message,
        "original_line": line
    }


def generate_basic_statistics(lines: List[str], parsed_entries: List[Dict], invalid_entries: List[Dict]) -> Dict[str, Any]:
    """Generate basic statistics about the log file."""
    total_lines = len(lines)
    valid_lines = len(parsed_entries)
    invalid_lines = len(invalid_entries)
    
    # File size estimation
    total_chars = sum(len(line) for line in lines)
    avg_line_length = total_chars / total_lines if total_lines > 0 else 0
    
    return {
        "total_lines": total_lines,
        "valid_entries": valid_lines,
        "invalid_entries": invalid_lines,
        "success_rate": round((valid_lines / total_lines * 100), 2) if total_lines > 0 else 0,
        "average_line_length": round(avg_line_length, 2),
        "total_characters": total_chars,
        "estimated_size_bytes": total_chars  # Rough estimate
    }


def generate_temporal_analysis(parsed_entries: List[Dict]) -> Dict[str, Any]:
    """Generate temporal analysis of log entries."""
    if not parsed_entries:
        return {}
    
    timestamps = [entry["timestamp"] for entry in parsed_entries]
    timestamps.sort()
    
    # Basic time range
    earliest = timestamps[0]
    latest = timestamps[-1]
    duration = latest - earliest
    
    # Entries per hour analysis
    hourly_counts = defaultdict(int)
    daily_counts = defaultdict(int)
    
    for ts in timestamps:
        hour_key = ts.strftime('%Y-%m-%d %H:00')
        day_key = ts.strftime('%Y-%m-%d')
        hourly_counts[hour_key] += 1
        daily_counts[day_key] += 1
    
    # Find peak hours and days
    peak_hour = max(hourly_counts.items(), key=lambda x: x[1]) if hourly_counts else ("", 0)
    peak_day = max(daily_counts.items(), key=lambda x: x[1]) if daily_counts else ("", 0)
    
    # Calculate average entries per hour/day
    hours_span = max(1, duration.total_seconds() / 3600)
    days_span = max(1, duration.days + 1)
    
    return {
        "earliest_entry": earliest.isoformat(),
        "latest_entry": latest.isoformat(),
        "duration_seconds": duration.total_seconds(),
        "duration_human": str(duration),
        "total_events": len(timestamps),
        "average_events_per_hour": round(len(timestamps) / hours_span, 2),
        "average_events_per_day": round(len(timestamps) / days_span, 2),
        "peak_hour": {
            "time": peak_hour[0],
            "count": peak_hour[1]
        },
        "peak_day": {
            "date": peak_day[0],
            "count": peak_day[1]
        },
        "unique_hours": len(hourly_counts),
        "unique_days": len(daily_counts)
    }


def generate_log_level_analysis(parsed_entries: List[Dict]) -> Dict[str, Any]:
    """Generate analysis of log levels."""
    if not parsed_entries:
        return {}
    
    level_counts = Counter(entry["level"] for entry in parsed_entries)
    total_entries = len(parsed_entries)
    
    # Calculate percentages and sort by frequency
    level_stats = {}
    for level, count in level_counts.most_common():
        percentage = round((count / total_entries * 100), 2)
        level_stats[level] = {
            "count": count,
            "percentage": percentage
        }
    
    # Identify severity distribution
    severity_mapping = {
        "ERROR": "high",
        "FATAL": "high",
        "CRITICAL": "high",
        "WARN": "medium",
        "WARNING": "medium",
        "INFO": "low",
        "DEBUG": "low",
        "TRACE": "low"
    }
    
    severity_counts = defaultdict(int)
    for level, count in level_counts.items():
        severity = severity_mapping.get(level, "unknown")
        severity_counts[severity] += count
    
    return {
        "level_distribution": level_stats,
        "total_unique_levels": len(level_counts),
        "most_common_level": level_counts.most_common(1)[0] if level_counts else ("", 0),
        "severity_distribution": dict(severity_counts),
        "error_rate": round((level_counts.get("ERROR", 0) / total_entries * 100), 2) if total_entries > 0 else 0
    }


def generate_message_analysis(parsed_entries: List[Dict]) -> Dict[str, Any]:
    """Generate analysis of log messages."""
    if not parsed_entries:
        return {}
    
    messages = [entry["message"] for entry in parsed_entries if entry["message"]]
    
    # Basic message statistics
    total_messages = len(messages)
    unique_messages = len(set(messages))
    
    # Message length analysis
    message_lengths = [len(msg) for msg in messages]
    avg_length = sum(message_lengths) / len(message_lengths) if message_lengths else 0
    max_length = max(message_lengths) if message_lengths else 0
    min_length = min(message_lengths) if message_lengths else 0
    
    # Find common patterns (simple word frequency)
    all_words = []
    for message in messages:
        words = re.findall(r'\b\w+\b', message.lower())
        all_words.extend(words)
    
    common_words = Counter(all_words).most_common(10)
    
    # Find repeated messages
    message_counts = Counter(messages)
    repeated_messages = [(msg, count) for msg, count in message_counts.most_common(5) if count > 1]
    
    return {
        "total_messages": total_messages,
        "unique_messages": unique_messages,
        "uniqueness_ratio": round((unique_messages / total_messages * 100), 2) if total_messages > 0 else 0,
        "message_length_stats": {
            "average": round(avg_length, 2),
            "maximum": max_length,
            "minimum": min_length
        },
        "common_words": common_words,
        "repeated_messages": repeated_messages
    }


def generate_quality_metrics(lines: List[str], parsed_entries: List[Dict], invalid_entries: List[Dict]) -> Dict[str, Any]:
    """Generate data quality metrics."""
    total_lines = len(lines)
    valid_lines = len(parsed_entries)
    
    # Completeness metrics
    completeness_score = (valid_lines / total_lines * 100) if total_lines > 0 else 0
    
    # Consistency metrics (timestamp format consistency)
    timestamp_formats = set()
    for entry in parsed_entries:
        timestamp_formats.add(len(entry["timestamp_str"]))
    
    consistency_score = 100 if len(timestamp_formats) <= 1 else 90
    
    # Overall quality score
    quality_score = (completeness_score + consistency_score) / 2
    
    return {
        "completeness_score": round(completeness_score, 2),
        "consistency_score": consistency_score,
        "overall_quality_score": round(quality_score, 2),
        "data_issues": {
            "invalid_entries": len(invalid_entries),
            "multiple_timestamp_formats": len(timestamp_formats) > 1,
            "empty_messages": sum(1 for entry in parsed_entries if not entry["message"])
        },
        "recommendations": generate_quality_recommendations(completeness_score, consistency_score, invalid_entries)
    }


def generate_quality_recommendations(completeness: float, consistency: float, invalid_entries: List) -> List[str]:
    """Generate recommendations based on quality metrics."""
    recommendations = []
    
    if completeness < 95:
        recommendations.append("Consider reviewing log format - some entries could not be parsed")
    
    if consistency < 100:
        recommendations.append("Multiple timestamp formats detected - consider standardizing")
    
    if len(invalid_entries) > 0:
        recommendations.append(f"{len(invalid_entries)} invalid entries found - review log generation process")
    
    if not recommendations:
        recommendations.append("Log quality is excellent - no issues detected")
    
    return recommendations
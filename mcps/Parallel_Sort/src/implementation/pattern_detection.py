"""
Pattern detection capability for log analysis.
Detects anomalies, repeated patterns, error clusters, and trending issues.
"""
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter, deque
from typing import Dict, Any, List, Tuple, Pattern
import statistics


async def detect_patterns(file_path: str, 
                         detection_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Detect various patterns in log files including anomalies, trends, and clusters.
    
    Args:
        file_path: Path to the log file to analyze
        detection_config: Configuration for pattern detection algorithms
        
    Returns:
        Dictionary containing detected patterns and analysis
    """
    try:
        # Default configuration
        config = {
            "error_cluster_window": 300,  # 5 minutes in seconds
            "anomaly_threshold": 3.0,     # Standard deviations
            "pattern_min_frequency": 3,   # Minimum occurrences to be considered a pattern
            "trending_window": 3600,      # 1 hour in seconds
            **(detection_config or {})
        }
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if not lines:
            return {
                "message": "File is empty",
                "patterns": {}
            }
        
        # Parse log entries
        parsed_entries = []
        for i, line in enumerate(lines, 1):
            try:
                entry = parse_log_entry(line.strip())
                entry["line_number"] = i
                parsed_entries.append(entry)
            except ValueError:
                continue  # Skip invalid entries for pattern detection
        
        if not parsed_entries:
            return {
                "message": "No valid log entries found for pattern detection",
                "patterns": {}
            }
        
        # Run pattern detection algorithms
        patterns = {
            "error_clusters": detect_error_clusters(parsed_entries, config),
            "anomalies": detect_anomalies(parsed_entries, config),
            "repeated_patterns": detect_repeated_patterns(parsed_entries, config),
            "trending_issues": detect_trending_issues(parsed_entries, config),
            "temporal_patterns": detect_temporal_patterns(parsed_entries, config),
            "message_patterns": detect_message_patterns(parsed_entries, config)
        }
        
        # Generate summary
        summary = generate_pattern_summary(patterns)
        
        return {
            "total_entries_analyzed": len(parsed_entries),
            "patterns": patterns,
            "summary": summary,
            "analyzed_at": datetime.now().isoformat(),
            "detection_config": config,
            "message": f"Successfully analyzed {len(parsed_entries)} entries for patterns"
        }
        
    except FileNotFoundError:
        return {
            "error": f"File not found: {file_path}",
            "patterns": {}
        }
    except Exception as e:
        return {
            "error": f"Pattern detection failed: {str(e)}",
            "patterns": {}
        }


def parse_log_entry(line: str) -> Dict[str, Any]:
    """Parse a single log line into structured components."""
    timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
    match = re.search(timestamp_pattern, line)
    
    if not match:
        raise ValueError("No valid timestamp found")
    
    timestamp_str = match.group(1)
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
    
    remainder = line[match.end():].strip()
    parts = remainder.split(' ', 1)
    
    level = parts[0] if parts else ""
    message = parts[1] if len(parts) > 1 else ""
    
    return {
        "timestamp": timestamp,
        "level": level.upper(),
        "message": message,
        "original_line": line
    }


def detect_error_clusters(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect clusters of errors occurring within a time window.
    """
    error_entries = [entry for entry in parsed_entries 
                    if entry["level"] in ["ERROR", "FATAL", "CRITICAL"]]
    
    if len(error_entries) < 2:
        return {"clusters": [], "total_clusters": 0}
    
    clusters = []
    window_seconds = config["error_cluster_window"]
    
    i = 0
    while i < len(error_entries):
        cluster_start = error_entries[i]["timestamp"]
        cluster_entries = [error_entries[i]]
        
        # Find all errors within the time window
        j = i + 1
        while j < len(error_entries):
            time_diff = (error_entries[j]["timestamp"] - cluster_start).total_seconds()
            if time_diff <= window_seconds:
                cluster_entries.append(error_entries[j])
                j += 1
            else:
                break
        
        # Only consider it a cluster if there are multiple errors
        if len(cluster_entries) >= 2:
            cluster_end = cluster_entries[-1]["timestamp"]
            clusters.append({
                "start_time": cluster_start.isoformat(),
                "end_time": cluster_end.isoformat(),
                "duration_seconds": (cluster_end - cluster_start).total_seconds(),
                "error_count": len(cluster_entries),
                "error_types": list(set(entry["level"] for entry in cluster_entries)),
                "sample_messages": [entry["message"][:100] for entry in cluster_entries[:3]]
            })
        
        i = max(i + 1, j)
    
    return {
        "clusters": clusters,
        "total_clusters": len(clusters),
        "total_errors_in_clusters": sum(cluster["error_count"] for cluster in clusters)
    }


def detect_anomalies(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect temporal anomalies in log entry frequency.
    """
    if len(parsed_entries) < 10:
        return {"anomalies": [], "total_anomalies": 0}
    
    # Group entries by hour
    hourly_counts = defaultdict(int)
    for entry in parsed_entries:
        hour_key = entry["timestamp"].strftime('%Y-%m-%d %H')
        hourly_counts[hour_key] += 1
    
    counts = list(hourly_counts.values())
    if len(counts) < 3:
        return {"anomalies": [], "total_anomalies": 0}
    
    # Calculate statistical thresholds
    mean_count = statistics.mean(counts)
    stdev_count = statistics.stdev(counts) if len(counts) > 1 else 0
    threshold = config["anomaly_threshold"]
    
    upper_bound = mean_count + (threshold * stdev_count)
    lower_bound = max(0, mean_count - (threshold * stdev_count))
    
    # Find anomalous hours
    anomalies = []
    for hour, count in hourly_counts.items():
        if count > upper_bound:
            anomalies.append({
                "hour": hour,
                "count": count,
                "type": "high_volume",
                "deviation": round((count - mean_count) / stdev_count, 2) if stdev_count > 0 else 0,
                "expected_range": f"{round(lower_bound)}-{round(upper_bound)}"
            })
        elif count < lower_bound and lower_bound > 0:
            anomalies.append({
                "hour": hour,
                "count": count,
                "type": "low_volume",
                "deviation": round((count - mean_count) / stdev_count, 2) if stdev_count > 0 else 0,
                "expected_range": f"{round(lower_bound)}-{round(upper_bound)}"
            })
    
    return {
        "anomalies": sorted(anomalies, key=lambda x: abs(x["deviation"]), reverse=True),
        "total_anomalies": len(anomalies),
        "baseline_stats": {
            "mean_hourly_count": round(mean_count, 2),
            "std_deviation": round(stdev_count, 2),
            "detection_threshold": threshold
        }
    }


def detect_repeated_patterns(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect frequently repeated message patterns.
    """
    min_frequency = config["pattern_min_frequency"]
    
    # Extract message patterns (simplified)
    message_counts = Counter()
    normalized_messages = {}
    
    for entry in parsed_entries:
        message = entry["message"]
        # Normalize message (remove numbers, IPs, timestamps for pattern matching)
        normalized = normalize_message_for_pattern(message)
        message_counts[normalized] += 1
        if normalized not in normalized_messages:
            normalized_messages[normalized] = message
    
    # Find patterns that occur frequently
    patterns = []
    for normalized_msg, count in message_counts.items():
        if count >= min_frequency:
            patterns.append({
                "pattern": normalized_msg,
                "original_example": normalized_messages[normalized_msg],
                "frequency": count,
                "percentage": round((count / len(parsed_entries) * 100), 2)
            })
    
    # Sort by frequency
    patterns.sort(key=lambda x: x["frequency"], reverse=True)
    
    return {
        "patterns": patterns[:20],  # Top 20 patterns
        "total_patterns": len(patterns),
        "total_unique_messages": len(message_counts)
    }


def normalize_message_for_pattern(message: str) -> str:
    """
    Normalize a message for pattern detection by removing variable parts.
    """
    # Remove common variable patterns
    normalized = message
    
    # Remove IP addresses (must come before general number replacement)
    normalized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', 'IP_ADDRESS', normalized)
    
    # Remove numbers
    normalized = re.sub(r'\b\d+\b', 'NUMBER', normalized)
    
    # Remove UUIDs
    normalized = re.sub(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', 'UUID', normalized)
    
    # Remove URLs (must come before file paths since URLs contain /)
    normalized = re.sub(r'https?://[^\s]+', 'URL', normalized)
    
    # Remove file paths
    normalized = re.sub(r'/[^\s]*', 'FILE_PATH', normalized)
    
    # Normalize whitespace
    normalized = ' '.join(normalized.split())
    
    return normalized


def detect_trending_issues(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect issues that are trending upward over time.
    """
    window_seconds = config["trending_window"]
    
    # Group entries by time windows
    time_windows = defaultdict(lambda: defaultdict(int))
    
    for entry in parsed_entries:
        # Create time window key (rounded to hour)
        window_start = entry["timestamp"].replace(minute=0, second=0, microsecond=0)
        normalized_msg = normalize_message_for_pattern(entry["message"])
        time_windows[window_start][normalized_msg] += 1
    
    # Find trending patterns
    trending_issues = []
    
    for pattern in set().union(*[window.keys() for window in time_windows.values()]):
        # Get counts over time for this pattern
        time_series = []
        for window_time in sorted(time_windows.keys()):
            count = time_windows[window_time].get(pattern, 0)
            time_series.append((window_time, count))
        
        if len(time_series) >= 3:  # Need at least 3 data points
            # Simple trend detection: compare first half with second half
            mid_point = len(time_series) // 2
            first_half_avg = sum(count for _, count in time_series[:mid_point]) / mid_point
            second_half_avg = sum(count for _, count in time_series[mid_point:]) / (len(time_series) - mid_point)
            
            if second_half_avg > first_half_avg * 1.5:  # 50% increase
                trending_issues.append({
                    "pattern": pattern,
                    "trend_factor": round(second_half_avg / max(first_half_avg, 1), 2),
                    "early_average": round(first_half_avg, 2),
                    "recent_average": round(second_half_avg, 2),
                    "time_series": [(ts.isoformat(), count) for ts, count in time_series]
                })
    
    # Sort by trend factor
    trending_issues.sort(key=lambda x: x["trend_factor"], reverse=True)
    
    return {
        "trending_issues": trending_issues[:10],  # Top 10 trending issues
        "total_trending": len(trending_issues)
    }


def detect_temporal_patterns(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect patterns based on time of day, day of week, etc.
    """
    hour_counts = defaultdict(int)
    day_counts = defaultdict(int)
    level_by_hour = defaultdict(lambda: defaultdict(int))
    
    for entry in parsed_entries:
        hour = entry["timestamp"].hour
        day = entry["timestamp"].strftime('%A')
        level = entry["level"]
        
        hour_counts[hour] += 1
        day_counts[day] += 1
        level_by_hour[hour][level] += 1
    
    # Find peak hours and days
    peak_hour = max(hour_counts.items(), key=lambda x: x[1]) if hour_counts else (0, 0)
    peak_day = max(day_counts.items(), key=lambda x: x[1]) if day_counts else ("", 0)
    
    # Find error-prone hours
    error_hours = []
    for hour in range(24):
        total_hour = hour_counts.get(hour, 0)
        errors_hour = level_by_hour[hour].get("ERROR", 0) + level_by_hour[hour].get("FATAL", 0)
        if total_hour > 0:
            error_rate = errors_hour / total_hour
            if error_rate > 0.1:  # More than 10% errors
                error_hours.append({
                    "hour": hour,
                    "error_rate": round(error_rate * 100, 2),
                    "total_entries": total_hour,
                    "error_count": errors_hour
                })
    
    return {
        "hourly_distribution": dict(hour_counts),
        "daily_distribution": dict(day_counts),
        "peak_hour": {"hour": peak_hour[0], "count": peak_hour[1]},
        "peak_day": {"day": peak_day[0], "count": peak_day[1]},
        "error_prone_hours": sorted(error_hours, key=lambda x: x["error_rate"], reverse=True),
        "business_hours_vs_off_hours": analyze_business_hours(hour_counts)
    }


def analyze_business_hours(hour_counts: Dict[int, int]) -> Dict[str, Any]:
    """Analyze activity during business hours vs off hours."""
    business_hours = range(9, 18)  # 9 AM to 6 PM
    
    business_count = sum(hour_counts.get(hour, 0) for hour in business_hours)
    off_hours_count = sum(hour_counts.get(hour, 0) for hour in range(24) if hour not in business_hours)
    
    total = business_count + off_hours_count
    
    return {
        "business_hours_count": business_count,
        "off_hours_count": off_hours_count,
        "business_hours_percentage": round((business_count / total * 100), 2) if total > 0 else 0,
        "off_hours_percentage": round((off_hours_count / total * 100), 2) if total > 0 else 0
    }


def detect_message_patterns(parsed_entries: List[Dict], config: Dict) -> Dict[str, Any]:
    """
    Detect patterns in message content using regex patterns.
    """
    # Common log patterns
    patterns = {
        "connection_issues": r'(?i)(connection|connect|disconnect|timeout|refused)',
        "authentication": r'(?i)(auth|login|logout|credential|password|token)',
        "performance": r'(?i)(slow|timeout|latency|response.*time|performance)',
        "database": r'(?i)(database|db|sql|query|transaction)',
        "memory_issues": r'(?i)(memory|heap|oom|out.*of.*memory)',
        "file_operations": r'(?i)(file|read|write|open|close|permission)',
        "network": r'(?i)(network|http|tcp|udp|socket|port)',
        "security": r'(?i)(security|attack|breach|unauthorized|forbidden)'
    }
    
    pattern_matches = defaultdict(list)
    
    for entry in parsed_entries:
        message = entry["message"]
        for pattern_name, regex in patterns.items():
            if re.search(regex, message):
                pattern_matches[pattern_name].append({
                    "timestamp": entry["timestamp"].isoformat(),
                    "level": entry["level"],
                    "message": message[:100]  # Truncate for brevity
                })
    
    # Calculate statistics for each pattern
    pattern_stats = {}
    for pattern_name, matches in pattern_matches.items():
        if matches:
            levels = [match["level"] for match in matches]
            level_counts = Counter(levels)
            
            pattern_stats[pattern_name] = {
                "total_matches": len(matches),
                "percentage": round((len(matches) / len(parsed_entries) * 100), 2),
                "level_distribution": dict(level_counts),
                "sample_messages": matches[:3]  # First 3 examples
            }
    
    return {
        "detected_patterns": pattern_stats,
        "total_pattern_types": len(pattern_stats)
    }


def generate_pattern_summary(patterns: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a summary of all detected patterns."""
    summary = {
        "high_priority_findings": [],
        "medium_priority_findings": [],
        "low_priority_findings": [],
        "overall_assessment": "normal"
    }
    
    # Analyze error clusters
    if patterns["error_clusters"]["total_clusters"] > 0:
        summary["high_priority_findings"].append(
            f"{patterns['error_clusters']['total_clusters']} error clusters detected"
        )
        summary["overall_assessment"] = "concerning"
    
    # Analyze anomalies
    if patterns["anomalies"]["total_anomalies"] > 0:
        summary["medium_priority_findings"].append(
            f"{patterns['anomalies']['total_anomalies']} temporal anomalies detected"
        )
    
    # Analyze trending issues
    if patterns["trending_issues"]["total_trending"] > 0:
        summary["medium_priority_findings"].append(
            f"{patterns['trending_issues']['total_trending']} trending issues detected"
        )
    
    # Analyze repeated patterns
    if patterns["repeated_patterns"]["total_patterns"] > 10:
        summary["low_priority_findings"].append(
            f"{patterns['repeated_patterns']['total_patterns']} repeated message patterns found"
        )
    
    # Set overall assessment
    if summary["high_priority_findings"]:
        summary["overall_assessment"] = "critical"
    elif summary["medium_priority_findings"]:
        summary["overall_assessment"] = "attention_needed"
    elif summary["low_priority_findings"]:
        summary["overall_assessment"] = "normal_with_patterns"
    
    return summary
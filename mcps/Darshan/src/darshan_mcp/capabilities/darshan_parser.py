"""
Darshan log file parser and analyzer for I/O performance analysis.
"""

import asyncio
import subprocess
import json
import os
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


async def _run_darshan_command(
    args: List[str], log_file: str
) -> Tuple[str, str, Optional[int]]:
    """
    Run a darshan command and return stdout, stderr, and return code.

    Args:
        args: Command arguments (e.g., ['-l', '--json'])
        log_file: Path to the Darshan log file

    Returns:
        tuple: (stdout, stderr, return_code)
    """
    try:
        # Check if darshan-parser is available
        cmd = ["darshan-parser"] + args + [log_file]

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        stdout_str = stdout.decode("utf-8") if stdout else ""
        stderr_str = stderr.decode("utf-8") if stderr else ""

        return stdout_str, stderr_str, process.returncode
    except FileNotFoundError:
        return "", "darshan-parser command not found. Is Darshan installed?", 1
    except Exception as e:
        return "", f"Error running darshan command: {str(e)}", 1


async def _parse_darshan_json(log_file: str) -> Dict[str, Any]:
    """Parse Darshan log to JSON format."""

    stdout, stderr, returncode = await _run_darshan_command(["--json"], log_file)

    if returncode != 0:
        # Try alternative parsing methods if JSON not available
        return await _parse_darshan_text(log_file)

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return await _parse_darshan_text(log_file)


async def _parse_darshan_text(log_file: str) -> Dict[str, Any]:
    """Parse Darshan log using text output format."""

    stdout, stderr, returncode = await _run_darshan_command(["-l"], log_file)

    if returncode != 0:
        return {"error": stderr or "Failed to parse Darshan log", "success": False}

    # Parse text output to extract key information
    parsed_data: Dict[str, Any] = {
        "job": {},
        "modules": [],
        "files": {},
        "success": True,
    }

    lines = stdout.split("\n")
    current_section: Optional[str] = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse job information
        if "Job ID:" in line:
            parsed_data["job"]["job_id"] = line.split(":", 1)[1].strip()
        elif "User ID:" in line:
            parsed_data["job"]["user_id"] = line.split(":", 1)[1].strip()
        elif "Start time:" in line:
            parsed_data["job"]["start_time"] = line.split(":", 1)[1].strip()
        elif "End time:" in line:
            parsed_data["job"]["end_time"] = line.split(":", 1)[1].strip()
        elif "Number of processes:" in line:
            parsed_data["job"]["nprocs"] = int(line.split(":", 1)[1].strip())
        elif "Modules in log:" in line:
            current_section = "modules"
        elif current_section == "modules" and line.startswith("-"):
            module_name = line.lstrip("- ").strip()
            parsed_data["modules"].append(module_name)

    return parsed_data


async def load_darshan_log(log_file_path: str) -> Dict[str, Any]:
    """Load and parse a Darshan log file."""
    if not os.path.exists(log_file_path):
        return {
            "success": False,
            "error": f"Log file not found: {log_file_path}",
            "log_file": log_file_path,
        }

    try:
        parsed_data = await _parse_darshan_json(log_file_path)

        if not parsed_data.get("success", True):
            return parsed_data

        # Extract basic information
        result = {
            "success": True,
            "log_file": log_file_path,
            "file_size": os.path.getsize(log_file_path),
            "job_info": parsed_data.get("job", {}),
            "modules": parsed_data.get("modules", []),
            "file_count": len(parsed_data.get("files", {})),
            "available_analyses": [
                "job_summary",
                "file_access_patterns",
                "io_performance_metrics",
                "posix_operations",
                "mpiio_operations",
                "timeline_analysis",
            ],
        }

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Error parsing Darshan log: {str(e)}",
            "log_file": log_file_path,
        }


async def get_job_summary(log_file_path: str) -> Dict[str, Any]:
    """Get job-level summary information."""
    try:
        parsed_data = await _parse_darshan_json(log_file_path)

        if not parsed_data.get("success", True):
            return parsed_data

        job_info = parsed_data.get("job", {})

        # Calculate runtime if start/end times available
        runtime = None
        if "start_time" in job_info and "end_time" in job_info:
            try:
                start = datetime.fromisoformat(
                    job_info["start_time"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    job_info["end_time"].replace("Z", "+00:00")
                )
                runtime = (end - start).total_seconds()
            except (ValueError, TypeError, KeyError):
                runtime = job_info.get("runtime", None)

        # Aggregate I/O statistics from all files
        total_bytes_read = 0
        total_bytes_written = 0
        total_read_ops = 0
        total_write_ops = 0

        files = parsed_data.get("files", {})
        for file_data in files.values():
            if isinstance(file_data, dict):
                total_bytes_read += file_data.get("bytes_read", 0)
                total_bytes_written += file_data.get("bytes_written", 0)
                total_read_ops += file_data.get("read_ops", 0)
                total_write_ops += file_data.get("write_ops", 0)

        summary = {
            "success": True,
            "job_id": job_info.get("job_id", "unknown"),
            "user_id": job_info.get("user_id", "unknown"),
            "nprocs": job_info.get("nprocs", 1),
            "runtime_seconds": runtime,
            "total_files": len(files),
            "total_bytes_read": total_bytes_read,
            "total_bytes_written": total_bytes_written,
            "total_read_operations": total_read_ops,
            "total_write_operations": total_write_ops,
            "total_io_volume": total_bytes_read + total_bytes_written,
            "modules_used": parsed_data.get("modules", []),
        }

        # Calculate derived metrics
        if runtime and runtime > 0:
            summary["avg_read_bandwidth_mbps"] = (
                total_bytes_read / (1024 * 1024)
            ) / runtime
            summary["avg_write_bandwidth_mbps"] = (
                total_bytes_written / (1024 * 1024)
            ) / runtime
            summary["total_bandwidth_mbps"] = (
                summary["avg_read_bandwidth_mbps"] + summary["avg_write_bandwidth_mbps"]
            )

        return summary

    except Exception as e:
        return {"success": False, "error": f"Error generating job summary: {str(e)}"}


async def analyze_file_access_patterns(
    log_file_path: str, file_pattern: Optional[str] = None
) -> Dict[str, Any]:
    """Analyze file access patterns."""
    try:
        parsed_data = await _parse_darshan_json(log_file_path)

        if not parsed_data.get("success", True):
            return parsed_data

        files = parsed_data.get("files", {})

        # Filter files by pattern if provided
        if file_pattern:
            import fnmatch

            filtered_files = {
                path: data
                for path, data in files.items()
                if fnmatch.fnmatch(path, file_pattern)
            }
        else:
            filtered_files = files

        if not filtered_files:
            return {
                "success": True,
                "message": "No files match the specified pattern"
                if file_pattern
                else "No files found",
                "file_count": 0,
                "files": [],
            }

        # Analyze access patterns
        access_patterns: Dict[str, Any] = {
            "read_only_files": 0,
            "write_only_files": 0,
            "read_write_files": 0,
            "sequential_access": 0,
            "random_access": 0,
            "file_sizes": [],
            "files_analysis": [],
        }

        for file_path, file_data in filtered_files.items():
            if not isinstance(file_data, dict):
                continue

            bytes_read = file_data.get("bytes_read", 0)
            bytes_written = file_data.get("bytes_written", 0)

            # Categorize access type
            if bytes_read > 0 and bytes_written == 0:
                access_patterns["read_only_files"] += 1
                access_type = "read_only"
            elif bytes_read == 0 and bytes_written > 0:
                access_patterns["write_only_files"] += 1
                access_type = "write_only"
            elif bytes_read > 0 and bytes_written > 0:
                access_patterns["read_write_files"] += 1
                access_type = "read_write"
            else:
                access_type = "no_io"

            # Analyze access pattern (sequential vs random)
            seq_reads = file_data.get("sequential_reads", 0)
            seq_writes = file_data.get("sequential_writes", 0)
            total_reads = file_data.get("read_ops", 0)
            total_writes = file_data.get("write_ops", 0)

            is_sequential = False
            if total_reads + total_writes > 0:
                seq_ratio = (seq_reads + seq_writes) / (total_reads + total_writes)
                is_sequential = seq_ratio >= 0.75

            if is_sequential:
                access_patterns["sequential_access"] += 1
                pattern_type = "sequential"
            else:
                access_patterns["random_access"] += 1
                pattern_type = "random"

            file_size = file_data.get("file_size", 0)
            access_patterns["file_sizes"].append(file_size)

            access_patterns["files_analysis"].append(
                {
                    "file_path": file_path,
                    "access_type": access_type,
                    "pattern_type": pattern_type,
                    "bytes_read": bytes_read,
                    "bytes_written": bytes_written,
                    "file_size": file_size,
                    "read_ops": total_reads,
                    "write_ops": total_writes,
                }
            )

        # Calculate statistics
        file_sizes = access_patterns["file_sizes"]
        if file_sizes:
            access_patterns["file_size_stats"] = {
                "min_size": min(file_sizes),
                "max_size": max(file_sizes),
                "avg_size": sum(file_sizes) / len(file_sizes),
                "total_size": sum(file_sizes),
            }

        access_patterns["success"] = True
        access_patterns["file_count"] = len(filtered_files)
        access_patterns["filter_pattern"] = file_pattern

        return access_patterns

    except Exception as e:
        return {
            "success": False,
            "error": f"Error analyzing file access patterns: {str(e)}",
        }


async def get_io_performance_metrics(log_file_path: str) -> Dict[str, Any]:
    """Get I/O performance metrics."""
    try:
        parsed_data = await _parse_darshan_json(log_file_path)

        if not parsed_data.get("success", True):
            return parsed_data

        parsed_data.get("job", {})
        files = parsed_data.get("files", {})

        # Calculate performance metrics
        metrics: Dict[str, Any] = {
            "success": True,
            "read_metrics": {},
            "write_metrics": {},
            "overall_metrics": {},
        }

        # Aggregate data for calculations
        total_read_bytes = 0
        total_write_bytes = 0
        total_read_ops = 0
        total_write_ops = 0
        total_read_time = 0
        total_write_time = 0

        read_sizes: List[float] = []
        write_sizes: List[float] = []

        for file_data in files.values():
            if not isinstance(file_data, dict):
                continue

            bytes_read = file_data.get("bytes_read", 0)
            bytes_written = file_data.get("bytes_written", 0)
            read_ops = file_data.get("read_ops", 0)
            write_ops = file_data.get("write_ops", 0)

            total_read_bytes += bytes_read
            total_write_bytes += bytes_written
            total_read_ops += read_ops
            total_write_ops += write_ops

            # Collect request sizes
            if read_ops > 0:
                avg_read_size = bytes_read / read_ops
                read_sizes.extend([avg_read_size] * read_ops)

            if write_ops > 0:
                avg_write_size = bytes_written / write_ops
                write_sizes.extend([avg_write_size] * write_ops)

            # Time metrics (if available)
            total_read_time += file_data.get("read_time", 0)
            total_write_time += file_data.get("write_time", 0)

        # Calculate read metrics
        if total_read_ops > 0:
            metrics["read_metrics"] = {
                "total_bytes": total_read_bytes,
                "total_operations": total_read_ops,
                "avg_request_size": total_read_bytes / total_read_ops,
                "total_time_seconds": total_read_time,
            }

            if total_read_time > 0:
                metrics["read_metrics"]["bandwidth_mbps"] = (
                    total_read_bytes / (1024 * 1024)
                ) / total_read_time
                metrics["read_metrics"]["iops"] = total_read_ops / total_read_time

            if read_sizes:
                metrics["read_metrics"]["request_size_stats"] = {
                    "min": min(read_sizes),
                    "max": max(read_sizes),
                    "avg": sum(read_sizes) / len(read_sizes),
                    "std": np.std(read_sizes) if len(read_sizes) > 1 else 0,
                }

        # Calculate write metrics
        if total_write_ops > 0:
            metrics["write_metrics"] = {
                "total_bytes": total_write_bytes,
                "total_operations": total_write_ops,
                "avg_request_size": total_write_bytes / total_write_ops,
                "total_time_seconds": total_write_time,
            }

            if total_write_time > 0:
                metrics["write_metrics"]["bandwidth_mbps"] = (
                    total_write_bytes / (1024 * 1024)
                ) / total_write_time
                metrics["write_metrics"]["iops"] = total_write_ops / total_write_time

            if write_sizes:
                metrics["write_metrics"]["request_size_stats"] = {
                    "min": min(write_sizes),
                    "max": max(write_sizes),
                    "avg": sum(write_sizes) / len(write_sizes),
                    "std": np.std(write_sizes) if len(write_sizes) > 1 else 0,
                }

        # Overall metrics
        total_time = max(total_read_time, total_write_time)
        if total_time > 0:
            metrics["overall_metrics"] = {
                "total_io_volume": total_read_bytes + total_write_bytes,
                "total_operations": total_read_ops + total_write_ops,
                "total_bandwidth_mbps": (
                    (total_read_bytes + total_write_bytes) / (1024 * 1024)
                )
                / total_time,
                "total_iops": (total_read_ops + total_write_ops) / total_time,
                "read_write_ratio": total_read_bytes / max(total_write_bytes, 1),
            }

        return metrics

    except Exception as e:
        return {
            "success": False,
            "error": f"Error calculating I/O performance metrics: {str(e)}",
        }


async def analyze_posix_operations(log_file_path: str) -> Dict[str, Any]:
    """Analyze POSIX I/O operations."""
    try:
        # Use darshan-parser to get POSIX module data
        stdout, stderr, returncode = await _run_darshan_command(
            ["--module", "POSIX"], log_file_path
        )

        if returncode != 0:
            return {
                "success": False,
                "error": "Failed to extract POSIX module data",
                "message": stderr,
            }

        # Parse POSIX operations from output
        posix_analysis: Dict[str, Any] = {
            "success": True,
            "operations": {
                "opens": 0,
                "closes": 0,
                "reads": 0,
                "writes": 0,
                "seeks": 0,
                "stats": 0,
                "fsyncs": 0,
            },
            "timing": {},
            "patterns": {},
        }

        # Parse the text output for POSIX statistics
        lines = stdout.split("\n")
        for line in lines:
            line = line.strip()
            if "POSIX_OPENS:" in line:
                posix_analysis["operations"]["opens"] = int(line.split(":")[1].strip())
            elif "POSIX_READS:" in line:
                posix_analysis["operations"]["reads"] = int(line.split(":")[1].strip())
            elif "POSIX_WRITES:" in line:
                posix_analysis["operations"]["writes"] = int(line.split(":")[1].strip())
            elif "POSIX_SEEKS:" in line:
                posix_analysis["operations"]["seeks"] = int(line.split(":")[1].strip())

        # Type cast the nested dictionaries to avoid mypy errors
        posix_analysis["operations"] = dict(posix_analysis["operations"])

        return posix_analysis

    except Exception as e:
        return {
            "success": False,
            "error": f"Error analyzing POSIX operations: {str(e)}",
        }


async def analyze_mpiio_operations(log_file_path: str) -> Dict[str, Any]:
    """Analyze MPI-IO operations."""
    try:
        # Use darshan-parser to get MPI-IO module data
        stdout, stderr, returncode = await _run_darshan_command(
            ["--module", "MPIIO"], log_file_path
        )

        if returncode != 0:
            return {
                "success": True,
                "message": "No MPI-IO operations found in trace",
                "operations": {},
            }

        mpiio_analysis: Dict[str, Any] = {
            "success": True,
            "collective_operations": {"reads": 0, "writes": 0},
            "independent_operations": {"reads": 0, "writes": 0},
            "file_views": 0,
            "performance_metrics": {},
        }

        # Type cast the nested dictionaries to avoid mypy errors
        mpiio_analysis["collective_operations"] = dict(
            mpiio_analysis["collective_operations"]
        )
        mpiio_analysis["independent_operations"] = dict(
            mpiio_analysis["independent_operations"]
        )

        # Parse MPI-IO specific operations from output
        lines = stdout.split("\n")
        for line in lines:
            line = line.strip()
            if "MPIIO_COLL_READS:" in line:
                mpiio_analysis["collective_operations"]["reads"] = int(
                    line.split(":")[1].strip()
                )
            elif "MPIIO_COLL_WRITES:" in line:
                mpiio_analysis["collective_operations"]["writes"] = int(
                    line.split(":")[1].strip()
                )
            elif "MPIIO_INDEP_READS:" in line:
                mpiio_analysis["independent_operations"]["reads"] = int(
                    line.split(":")[1].strip()
                )
            elif "MPIIO_INDEP_WRITES:" in line:
                mpiio_analysis["independent_operations"]["writes"] = int(
                    line.split(":")[1].strip()
                )

        return mpiio_analysis

    except Exception as e:
        return {
            "success": False,
            "error": f"Error analyzing MPI-IO operations: {str(e)}",
        }


async def identify_io_bottlenecks(log_file_path: str) -> Dict[str, Any]:
    """Identify I/O performance bottlenecks."""
    try:
        # Get performance metrics first
        perf_metrics = await get_io_performance_metrics(log_file_path)
        file_patterns = await analyze_file_access_patterns(log_file_path)

        if not perf_metrics.get("success") or not file_patterns.get("success"):
            return {
                "success": False,
                "error": "Failed to get required metrics for bottleneck analysis",
            }

        bottlenecks: Dict[str, Any] = {
            "success": True,
            "identified_issues": [],
            "recommendations": [],
            "severity_score": 0,  # 0-10 scale
        }

        # Check for small I/O operations
        read_metrics = perf_metrics.get("read_metrics", {})
        write_metrics = perf_metrics.get("write_metrics", {})

        avg_read_size = read_metrics.get("avg_request_size", 0)
        avg_write_size = write_metrics.get("avg_request_size", 0)

        if avg_read_size > 0 and avg_read_size < 64 * 1024:  # Less than 64KB
            bottlenecks["identified_issues"].append(
                {
                    "type": "small_reads",
                    "description": f"Average read size is {avg_read_size / 1024:.1f}KB, which may be inefficient",
                    "severity": "medium",
                }
            )
            bottlenecks["recommendations"].append(
                "Consider using larger read buffer sizes"
            )
            bottlenecks["severity_score"] += 2

        if avg_write_size > 0 and avg_write_size < 64 * 1024:  # Less than 64KB
            bottlenecks["identified_issues"].append(
                {
                    "type": "small_writes",
                    "description": f"Average write size is {avg_write_size / 1024:.1f}KB, which may be inefficient",
                    "severity": "medium",
                }
            )
            bottlenecks["recommendations"].append(
                "Consider using larger write buffer sizes or buffering writes"
            )
            bottlenecks["severity_score"] += 2

        # Check for excessive random access
        total_files = file_patterns.get("file_count", 0)
        random_files = file_patterns.get("random_access", 0)

        if total_files > 0 and random_files / total_files > 0.5:
            bottlenecks["identified_issues"].append(
                {
                    "type": "random_access",
                    "description": f"{random_files}/{total_files} files show random access patterns",
                    "severity": "high",
                }
            )
            bottlenecks["recommendations"].append(
                "Consider data layout optimizations or prefetching"
            )
            bottlenecks["severity_score"] += 3

        # Check for low bandwidth utilization
        read_bw = read_metrics.get("bandwidth_mbps", 0)
        write_bw = write_metrics.get("bandwidth_mbps", 0)
        total_bw = read_bw + write_bw

        if total_bw > 0 and total_bw < 100:  # Less than 100 MB/s
            bottlenecks["identified_issues"].append(
                {
                    "type": "low_bandwidth",
                    "description": f"Total I/O bandwidth is {total_bw:.1f} MB/s, which may be suboptimal",
                    "severity": "medium",
                }
            )
            bottlenecks["recommendations"].append(
                "Investigate storage system performance and I/O patterns"
            )
            bottlenecks["severity_score"] += 2

        # Check for excessive file count
        if total_files > 1000:
            bottlenecks["identified_issues"].append(
                {
                    "type": "many_files",
                    "description": f"Application accessed {total_files} files, which may cause metadata overhead",
                    "severity": "medium",
                }
            )
            bottlenecks["recommendations"].append(
                "Consider file aggregation or using fewer, larger files"
            )
            bottlenecks["severity_score"] += 1

        # Normalize severity score
        bottlenecks["severity_score"] = min(bottlenecks["severity_score"], 10)

        return bottlenecks

    except Exception as e:
        return {
            "success": False,
            "error": f"Error identifying I/O bottlenecks: {str(e)}",
        }


async def get_timeline_analysis(
    log_file_path: str, time_resolution: str = "1s"
) -> Dict[str, Any]:
    """Generate timeline analysis of I/O activity."""
    try:
        # This would require timestamp data from Darshan logs
        # For now, provide a basic analysis structure
        timeline: Dict[str, Any] = {
            "success": True,
            "time_resolution": time_resolution,
            "message": "Timeline analysis requires timestamp data from Darshan logs",
            "analysis": {
                "total_duration": None,
                "peak_periods": [],
                "idle_periods": [],
                "io_phases": [],
            },
        }

        # Try to get basic timing information
        parsed_data = await _parse_darshan_json(log_file_path)
        job_info = parsed_data.get("job", {})

        if "start_time" in job_info and "end_time" in job_info:
            try:
                start = datetime.fromisoformat(
                    job_info["start_time"].replace("Z", "+00:00")
                )
                end = datetime.fromisoformat(
                    job_info["end_time"].replace("Z", "+00:00")
                )
                duration = (end - start).total_seconds()
                timeline["analysis"]["total_duration"] = duration
            except (ValueError, TypeError, KeyError):
                pass

        return timeline

    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating timeline analysis: {str(e)}",
        }


async def compare_darshan_logs(
    log_file_1: str, log_file_2: str, comparison_metrics: List[str]
) -> Dict[str, Any]:
    """Compare two Darshan log files."""
    try:
        # Get metrics for both logs
        metrics_1 = await get_io_performance_metrics(log_file_1)
        metrics_2 = await get_io_performance_metrics(log_file_2)

        if not metrics_1.get("success") or not metrics_2.get("success"):
            return {
                "success": False,
                "error": "Failed to get metrics for one or both log files",
            }

        comparison: Dict[str, Any] = {
            "success": True,
            "log_file_1": log_file_1,
            "log_file_2": log_file_2,
            "comparison_metrics": comparison_metrics,
            "differences": {},
            "summary": {},
        }

        # Compare specified metrics
        for metric in comparison_metrics:
            if metric == "bandwidth":
                bw1 = metrics_1.get("overall_metrics", {}).get(
                    "total_bandwidth_mbps", 0
                )
                bw2 = metrics_2.get("overall_metrics", {}).get(
                    "total_bandwidth_mbps", 0
                )
                comparison["differences"]["bandwidth"] = {
                    "log_1": bw1,
                    "log_2": bw2,
                    "difference": bw2 - bw1,
                    "percent_change": ((bw2 - bw1) / bw1 * 100) if bw1 > 0 else 0,
                }

            elif metric == "iops":
                iops1 = metrics_1.get("overall_metrics", {}).get("total_iops", 0)
                iops2 = metrics_2.get("overall_metrics", {}).get("total_iops", 0)
                comparison["differences"]["iops"] = {
                    "log_1": iops1,
                    "log_2": iops2,
                    "difference": iops2 - iops1,
                    "percent_change": ((iops2 - iops1) / iops1 * 100)
                    if iops1 > 0
                    else 0,
                }

        return comparison

    except Exception as e:
        return {"success": False, "error": f"Error comparing Darshan logs: {str(e)}"}


async def generate_io_summary_report(
    log_file_path: str, include_visualizations: bool = False
) -> Dict[str, Any]:
    """Generate comprehensive I/O summary report."""
    try:
        # Gather all analyses
        job_summary = await get_job_summary(log_file_path)
        file_patterns = await analyze_file_access_patterns(log_file_path)
        performance = await get_io_performance_metrics(log_file_path)
        bottlenecks = await identify_io_bottlenecks(log_file_path)

        report: Dict[str, Any] = {
            "success": True,
            "log_file": log_file_path,
            "generated_at": datetime.now().isoformat(),
            "executive_summary": {},
            "detailed_analysis": {
                "job_summary": job_summary,
                "file_access_patterns": file_patterns,
                "performance_metrics": performance,
                "bottleneck_analysis": bottlenecks,
            },
            "key_findings": [],
            "recommendations": [],
        }

        # Generate executive summary
        if job_summary.get("success"):
            total_io = job_summary.get("total_io_volume", 0)
            runtime = job_summary.get("runtime_seconds", 0)
            nprocs = job_summary.get("nprocs", 1)

            report["executive_summary"] = {
                "total_io_volume_gb": total_io / (1024**3) if total_io else 0,
                "runtime_minutes": runtime / 60 if runtime else 0,
                "process_count": nprocs,
                "avg_bandwidth_mbps": performance.get("overall_metrics", {}).get(
                    "total_bandwidth_mbps", 0
                ),
            }

        # Extract key findings
        if bottlenecks.get("success") and bottlenecks.get("identified_issues"):
            for issue in bottlenecks["identified_issues"]:
                report["key_findings"].append(issue["description"])

        # Collect recommendations
        if bottlenecks.get("success") and bottlenecks.get("recommendations"):
            report["recommendations"].extend(bottlenecks["recommendations"])

        return report

    except Exception as e:
        return {
            "success": False,
            "error": f"Error generating I/O summary report: {str(e)}",
        }

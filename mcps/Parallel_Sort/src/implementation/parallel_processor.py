"""
Parallel processing capability for handling large log files.
Implements true parallel processing using multiprocessing and chunked processing.
"""
import os
import re
import asyncio
import aiofiles
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from multiprocessing import cpu_count
from datetime import datetime
from typing import Dict, Any, List, Tuple
import tempfile
import math


async def parallel_sort_large_file(file_path: str, 
                                  chunk_size_mb: int = 100,
                                  max_workers: int = None) -> Dict[str, Any]:
    """
    Sort large log files using parallel processing with chunked approach.
    
    Args:
        file_path: Path to the log file to sort
        chunk_size_mb: Size of each chunk in MB (default: 100MB)
        max_workers: Maximum number of worker processes (default: CPU count)
        
    Returns:
        Dictionary containing sorted results and processing statistics
    """
    try:
        if not os.path.exists(file_path):
            return {
                "error": f"File not found: {file_path}",
                "sorted_lines": []
            }
        
        # Get file size
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Determine if parallel processing is needed
        if file_size_mb < chunk_size_mb:
            # Use regular sorting for small files
            from .sort_handler import sort_log_by_timestamp
            return await sort_log_by_timestamp(file_path)
        
        # Configure parallel processing
        if max_workers is None:
            max_workers = min(cpu_count(), 8)  # Cap at 8 to avoid overwhelming system
        
        chunk_size_bytes = chunk_size_mb * 1024 * 1024
        
        start_time = datetime.now()
        
        # Step 1: Split file into chunks
        chunks = await split_file_into_chunks(file_path, chunk_size_bytes)
        
        # Step 2: Process chunks in parallel
        sorted_chunks = await process_chunks_parallel(chunks, max_workers)
        
        # Step 3: Merge sorted chunks
        final_result = await merge_sorted_chunks(sorted_chunks)
        
        # Step 4: Clean up temporary files
        await cleanup_temp_files(chunks + [chunk['temp_file'] for chunk in sorted_chunks])
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Add processing statistics
        final_result.update({
            "file_size_mb": round(file_size_mb, 2),
            "chunks_processed": len(chunks),
            "max_workers_used": max_workers,
            "processing_time_seconds": round(processing_time, 2),
            "parallel_processing": True,
            "processed_at": end_time.isoformat(),
            "message": f"Large file processed using {len(chunks)} chunks in {processing_time:.2f} seconds"
        })
        
        return final_result
        
    except Exception as e:
        return {
            "error": f"Parallel processing failed: {str(e)}",
            "sorted_lines": []
        }


async def split_file_into_chunks(file_path: str, chunk_size_bytes: int) -> List[str]:
    """
    Split a large file into smaller chunks for parallel processing.
    
    Args:
        file_path: Path to the file to split
        chunk_size_bytes: Size of each chunk in bytes
        
    Returns:
        List of temporary file paths containing chunks
    """
    chunks = []
    
    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
        chunk_num = 0
        
        while True:
            # Create temporary file for this chunk
            temp_fd, temp_path = tempfile.mkstemp(suffix=f'_chunk_{chunk_num}.log')
            os.close(temp_fd)
            
            bytes_read = 0
            lines_in_chunk = []
            
            # Read lines until chunk size is reached
            async for line in f:
                line_bytes = len(line.encode('utf-8'))
                
                if bytes_read + line_bytes > chunk_size_bytes and lines_in_chunk:
                    # Chunk is full, break here to avoid splitting in middle of line
                    break
                
                lines_in_chunk.append(line)
                bytes_read += line_bytes
            
            if not lines_in_chunk:
                # No more data, remove empty temp file
                os.unlink(temp_path)
                break
            
            # Write chunk to temporary file
            async with aiofiles.open(temp_path, 'w', encoding='utf-8') as chunk_file:
                await chunk_file.writelines(lines_in_chunk)
            
            chunks.append(temp_path)
            chunk_num += 1
    
    return chunks


async def process_chunks_parallel(chunk_paths: List[str], max_workers: int) -> List[Dict[str, Any]]:
    """
    Process chunks in parallel using ProcessPoolExecutor.
    
    Args:
        chunk_paths: List of chunk file paths to process
        max_workers: Maximum number of worker processes
        
    Returns:
        List of processing results for each chunk
    """
    loop = asyncio.get_event_loop()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        # Submit all chunk processing tasks
        tasks = []
        for chunk_path in chunk_paths:
            task = loop.run_in_executor(executor, process_single_chunk, chunk_path)
            tasks.append(task)
        
        # Wait for all chunks to be processed
        results = await asyncio.gather(*tasks)
    
    return results


def process_single_chunk(chunk_path: str) -> Dict[str, Any]:
    """
    Process a single chunk (sort it). This runs in a separate process.
    
    Args:
        chunk_path: Path to the chunk file to process
        
    Returns:
        Dictionary containing processing results
    """
    try:
        # Import here to avoid issues with multiprocessing
        import re
        from datetime import datetime
        
        # Read chunk
        with open(chunk_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse and sort lines
        valid_entries = []
        invalid_lines = []
        
        for i, line in enumerate(lines, 1):
            try:
                timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
                match = re.search(timestamp_pattern, line.strip())
                
                if match:
                    timestamp_str = match.group(1)
                    parsed_dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    valid_entries.append((parsed_dt, line.strip()))
                else:
                    invalid_lines.append({
                        "line_number": i,
                        "content": line.strip(),
                        "error": "No valid timestamp found"
                    })
            except ValueError as e:
                invalid_lines.append({
                    "line_number": i,
                    "content": line.strip(),
                    "error": str(e)
                })
        
        # Sort valid entries
        valid_entries.sort(key=lambda x: x[0])
        sorted_lines = [entry[1] for entry in valid_entries]
        
        # Create temporary file for sorted chunk
        temp_fd, sorted_temp_path = tempfile.mkstemp(suffix='_sorted.log')
        os.close(temp_fd)
        
        # Write sorted lines to temporary file
        with open(sorted_temp_path, 'w', encoding='utf-8') as f:
            for line in sorted_lines:
                f.write(line + '\n')
        
        return {
            "temp_file": sorted_temp_path,
            "original_chunk": chunk_path,
            "total_lines": len(lines),
            "valid_lines": len(valid_entries),
            "invalid_lines": len(invalid_lines),
            "invalid_entries": invalid_lines,
            "sorted_lines": sorted_lines  # Keep in memory for merging
        }
        
    except Exception as e:
        return {
            "error": f"Chunk processing failed: {str(e)}",
            "temp_file": None,
            "original_chunk": chunk_path,
            "sorted_lines": []
        }


async def merge_sorted_chunks(sorted_chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge sorted chunks using k-way merge algorithm.
    
    Args:
        sorted_chunks: List of sorted chunk results
        
    Returns:
        Dictionary containing final merged results
    """
    try:
        # Collect all sorted lines with their timestamps for merging
        all_entries = []
        total_lines = 0
        total_valid = 0
        total_invalid = 0
        all_invalid_entries = []
        
        for chunk_result in sorted_chunks:
            if "error" in chunk_result:
                continue
                
            # Parse lines from this chunk to get timestamps for merging
            for line in chunk_result.get("sorted_lines", []):
                try:
                    timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
                    match = re.search(timestamp_pattern, line)
                    if match:
                        timestamp_str = match.group(1)
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        all_entries.append((timestamp, line))
                except ValueError:
                    continue
            
            # Accumulate statistics
            total_lines += chunk_result.get("total_lines", 0)
            total_valid += chunk_result.get("valid_lines", 0)
            total_invalid += chunk_result.get("invalid_lines", 0)
            all_invalid_entries.extend(chunk_result.get("invalid_entries", []))
        
        # Sort all entries globally
        all_entries.sort(key=lambda x: x[0])
        final_sorted_lines = [entry[1] for entry in all_entries]
        
        result = {
            "sorted_lines": final_sorted_lines,
            "total_lines": total_lines,
            "valid_lines": total_valid,
            "invalid_lines": total_invalid
        }
        
        if all_invalid_entries:
            result["invalid_entries"] = all_invalid_entries[:50]  # Limit for performance
            result["message"] = f"Successfully sorted {total_valid} lines from {len(sorted_chunks)} chunks. {total_invalid} lines had invalid timestamps."
        else:
            result["message"] = f"Successfully sorted all {total_valid} lines from {len(sorted_chunks)} chunks."
        
        return result
        
    except Exception as e:
        return {
            "error": f"Chunk merging failed: {str(e)}",
            "sorted_lines": []
        }


async def cleanup_temp_files(temp_files: List[str]) -> None:
    """
    Clean up temporary files created during processing.
    
    Args:
        temp_files: List of temporary file paths to clean up
    """
    for temp_file in temp_files:
        try:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
        except Exception:
            # Ignore cleanup errors
            pass


async def parallel_analyze_large_file(file_path: str,
                                     chunk_size_mb: int = 50,
                                     max_workers: int = None) -> Dict[str, Any]:
    """
    Analyze large log files using parallel processing.
    
    Args:
        file_path: Path to the log file to analyze
        chunk_size_mb: Size of each chunk in MB
        max_workers: Maximum number of worker processes
        
    Returns:
        Dictionary containing analysis results
    """
    try:
        if not os.path.exists(file_path):
            return {
                "error": f"File not found: {file_path}",
                "statistics": {}
            }
        
        file_size = os.path.getsize(file_path)
        file_size_mb = file_size / (1024 * 1024)
        
        # Use regular analysis for small files
        if file_size_mb < chunk_size_mb:
            from .statistics_handler import analyze_log_statistics
            return await analyze_log_statistics(file_path)
        
        if max_workers is None:
            max_workers = min(cpu_count(), 6)
        
        chunk_size_bytes = chunk_size_mb * 1024 * 1024
        start_time = datetime.now()
        
        # Split into chunks
        chunks = await split_file_into_chunks(file_path, chunk_size_bytes)
        
        # Analyze chunks in parallel
        chunk_analyses = await analyze_chunks_parallel(chunks, max_workers)
        
        # Merge analysis results
        merged_analysis = merge_analysis_results(chunk_analyses)
        
        # Clean up
        await cleanup_temp_files(chunks)
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        merged_analysis.update({
            "file_size_mb": round(file_size_mb, 2),
            "chunks_analyzed": len(chunks),
            "processing_time_seconds": round(processing_time, 2),
            "parallel_analysis": True,
            "analyzed_at": end_time.isoformat()
        })
        
        return merged_analysis
        
    except Exception as e:
        return {
            "error": f"Parallel analysis failed: {str(e)}",
            "statistics": {}
        }


async def analyze_chunks_parallel(chunk_paths: List[str], max_workers: int) -> List[Dict[str, Any]]:
    """
    Analyze chunks in parallel.
    
    Args:
        chunk_paths: List of chunk file paths
        max_workers: Maximum number of workers
        
    Returns:
        List of analysis results for each chunk
    """
    loop = asyncio.get_event_loop()
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        tasks = []
        for chunk_path in chunk_paths:
            task = loop.run_in_executor(executor, analyze_single_chunk, chunk_path)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
    
    return results


def analyze_single_chunk(chunk_path: str) -> Dict[str, Any]:
    """
    Analyze a single chunk. Runs in separate process.
    
    Args:
        chunk_path: Path to chunk file
        
    Returns:
        Analysis results for the chunk
    """
    try:
        import re
        from datetime import datetime
        from collections import defaultdict, Counter
        
        with open(chunk_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        parsed_entries = []
        invalid_count = 0
        
        # Parse entries
        for line in lines:
            try:
                timestamp_pattern = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
                match = re.search(timestamp_pattern, line.strip())
                
                if match:
                    timestamp_str = match.group(1)
                    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    
                    remainder = line[match.end():].strip()
                    parts = remainder.split(' ', 1)
                    level = parts[0] if parts else ""
                    message = parts[1] if len(parts) > 1 else ""
                    
                    parsed_entries.append({
                        "timestamp": timestamp,
                        "level": level.upper(),
                        "message": message
                    })
                else:
                    invalid_count += 1
            except ValueError:
                invalid_count += 1
        
        # Generate statistics for this chunk
        level_counts = Counter(entry["level"] for entry in parsed_entries)
        
        # Time analysis
        timestamps = [entry["timestamp"] for entry in parsed_entries]
        time_stats = {}
        if timestamps:
            timestamps.sort()
            time_stats = {
                "earliest": timestamps[0],
                "latest": timestamps[-1],
                "count": len(timestamps)
            }
        
        return {
            "total_lines": len(lines),
            "valid_entries": len(parsed_entries),
            "invalid_entries": invalid_count,
            "level_counts": dict(level_counts),
            "time_stats": time_stats,
            "chunk_file": chunk_path
        }
        
    except Exception as e:
        return {
            "error": f"Chunk analysis failed: {str(e)}",
            "chunk_file": chunk_path
        }


def merge_analysis_results(chunk_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Merge analysis results from multiple chunks.
    
    Args:
        chunk_analyses: List of chunk analysis results
        
    Returns:
        Merged analysis results
    """
    try:
        total_lines = 0
        total_valid = 0
        total_invalid = 0
        merged_level_counts = {}
        all_timestamps = []
        
        for analysis in chunk_analyses:
            if "error" in analysis:
                continue
                
            total_lines += analysis.get("total_lines", 0)
            total_valid += analysis.get("valid_entries", 0)
            total_invalid += analysis.get("invalid_entries", 0)
            
            # Merge level counts
            for level, count in analysis.get("level_counts", {}).items():
                merged_level_counts[level] = merged_level_counts.get(level, 0) + count
            
            # Collect timestamps
            time_stats = analysis.get("time_stats", {})
            if "earliest" in time_stats and "latest" in time_stats:
                all_timestamps.extend([time_stats["earliest"], time_stats["latest"]])
        
        # Generate merged statistics
        merged_stats = {
            "basic_statistics": {
                "total_lines": total_lines,
                "valid_entries": total_valid,
                "invalid_entries": total_invalid,
                "success_rate": round((total_valid / total_lines * 100), 2) if total_lines > 0 else 0
            },
            "log_level_analysis": {
                "level_distribution": {
                    level: {
                        "count": count,
                        "percentage": round((count / total_valid * 100), 2) if total_valid > 0 else 0
                    }
                    for level, count in merged_level_counts.items()
                }
            }
        }
        
        if all_timestamps:
            all_timestamps.sort()
            merged_stats["temporal_analysis"] = {
                "earliest_entry": all_timestamps[0].isoformat(),
                "latest_entry": all_timestamps[-1].isoformat(),
                "duration_seconds": (all_timestamps[-1] - all_timestamps[0]).total_seconds(),
                "total_events": total_valid
            }
        
        return {
            "total_lines": total_lines,
            "valid_entries": total_valid,
            "invalid_entries": total_invalid,
            "statistics": merged_stats,
            "message": f"Successfully analyzed {total_lines} lines from {len(chunk_analyses)} chunks"
        }
        
    except Exception as e:
        return {
            "error": f"Analysis merging failed: {str(e)}",
            "statistics": {}
        }
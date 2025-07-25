#!/usr/bin/env python3
"""
Performance tests for the Slurm MCP server.

This module tests the performance characteristics of the Slurm MCP server,
including job submission latency, concurrent operations, throughput, and
scalability under various workloads.
"""

import pytest
import time
import statistics
import tempfile
import os
import sys
import asyncio
import concurrent.futures
from typing import List, Dict, Any
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import implementation modules directly
from implementation.job_submission import submit_slurm_job
from implementation.job_status import get_job_status
from implementation.job_cancellation import cancel_slurm_job
from implementation.job_listing import list_slurm_jobs
from implementation.cluster_info import get_slurm_info
from implementation.job_details import get_job_details
from implementation.job_output import get_job_output
from implementation.queue_info import get_queue_info
from implementation.array_jobs import submit_array_job
from implementation.node_info import get_node_info


class TestSlurmMCPPerformance:
    """Performance test suite for Slurm MCP server."""

    @pytest.fixture(scope="class")
    def quick_script(self):
        """Create a minimal test script for quick execution."""
        script_content = """#!/bin/bash
#SBATCH --time=00:01:00
echo "Quick test: $(date)"
sleep 1
echo "Done: $(date)"
"""
        fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='quick_test_')
        with os.fdopen(fd, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        
        yield script_path
        
        # Cleanup
        if os.path.exists(script_path):
            os.unlink(script_path)

    @pytest.fixture(scope="class")  
    def medium_script(self):
        """Create a medium-duration test script."""
        script_content = """#!/bin/bash
#SBATCH --time=00:03:00
echo "Medium test: $(date)"
for i in {1..5}; do
    echo "Iteration $i"
    sleep 1
done
echo "Done: $(date)"
"""
        fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='medium_test_')
        with os.fdopen(fd, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        
        yield script_path
        
        # Cleanup
        if os.path.exists(script_path):
            os.unlink(script_path)

    @pytest.fixture(scope="class")
    def cpu_intensive_script(self):
        """Create a CPU-intensive test script."""
        script_content = """#!/bin/bash
#SBATCH --time=00:02:00
echo "CPU intensive test: $(date)"
# Light CPU work
python3 -c "
import time
start = time.time()
result = sum(i*i for i in range(10000))
print(f'Computation result: {result}')
print(f'Execution time: {time.time() - start:.2f}s')
"
echo "Done: $(date)"
"""
        fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='cpu_test_')
        with os.fdopen(fd, 'w') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)
        
        yield script_path
        
        # Cleanup
        if os.path.exists(script_path):
            os.unlink(script_path)

    def test_job_submission_latency(self, quick_script):
        """Test the latency of single job submission."""
        latencies = []
        num_tests = 5
        
        for _ in range(num_tests):
            start_time = time.time()
            result = submit_slurm_job(quick_script, cores=1)
            end_time = time.time()
            
            latency = end_time - start_time
            latencies.append(latency)
            
            # Clean up job if submitted successfully
            if not result.get("isError") and "job_id" in result:
                cancel_slurm_job(str(result["job_id"]))
        
        # Performance assertions
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        min_latency = min(latencies)
        
        print(f"\n=== Job Submission Latency Metrics ===")
        print(f"Average latency: {avg_latency:.3f}s")
        print(f"Min latency: {min_latency:.3f}s") 
        print(f"Max latency: {max_latency:.3f}s")
        print(f"Latency std dev: {statistics.stdev(latencies):.3f}s")
        
        # Performance requirements
        assert avg_latency < 2.0, f"Average submission latency too high: {avg_latency:.3f}s"
        assert max_latency < 6.0, f"Maximum submission latency too high: {max_latency:.3f}s"

    def test_job_status_query_performance(self, quick_script):
        """Test the performance of job status queries."""
        # First submit a job
        result = submit_slurm_job(quick_script, cores=1)
        if result.get("isError"):
            pytest.skip("Could not submit job for status testing")
            
        job_id = str(result["job_id"])
        
        try:
            latencies = []
            num_queries = 10
            
            for _ in range(num_queries):
                start_time = time.time()
                status_result = get_job_status(job_id)
                end_time = time.time()
                
                latency = end_time - start_time
                latencies.append(latency)
            
            # Performance metrics
            avg_latency = statistics.mean(latencies)
            max_latency = max(latencies)
            
            print(f"\n=== Job Status Query Metrics ===")
            print(f"Average query latency: {avg_latency:.3f}s")
            print(f"Max query latency: {max_latency:.3f}s")
            print(f"Queries per second: {1/avg_latency:.1f}")
            
            # Performance requirements
            assert avg_latency < 1.0, f"Status query latency too high: {avg_latency:.3f}s"
            assert max_latency < 3.0, f"Max status query latency too high: {max_latency:.3f}s"
            
        finally:
            # Cleanup
            cancel_slurm_job(job_id)

    def test_concurrent_job_submissions(self, quick_script):
        """Test concurrent job submission performance."""
        num_concurrent = 5
        submitted_jobs = []
        
        def submit_job():
            result = submit_slurm_job(quick_script, cores=1)
            return result, time.time()
        
        start_time = time.time()
        
        # Use ThreadPoolExecutor for concurrent submissions
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent) as executor:
            futures = [executor.submit(submit_job) for _ in range(num_concurrent)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Collect job IDs for cleanup
        for result, _ in results:
            if not result.get("isError") and "job_id" in result:
                submitted_jobs.append(str(result["job_id"]))
        
        # Performance metrics
        successful_submissions = len(submitted_jobs)
        throughput = successful_submissions / total_time if total_time > 0 else 0
        
        print(f"\n=== Concurrent Submission Metrics ===")
        print(f"Successful submissions: {successful_submissions}/{num_concurrent}")
        print(f"Total time: {total_time:.3f}s")
        print(f"Throughput: {throughput:.2f} jobs/second")
        
        # Cleanup submitted jobs
        for job_id in submitted_jobs:
            try:
                cancel_slurm_job(job_id)
            except Exception:
                pass  # Best effort cleanup
        
        # Performance requirements
        assert successful_submissions >= num_concurrent * 0.8, "Too many failed submissions"
        assert total_time < 10.0, f"Concurrent submissions took too long: {total_time:.3f}s"

    def test_cluster_info_performance(self):
        """Test cluster information retrieval performance."""
        latencies = []
        num_tests = 8
        
        for _ in range(num_tests):
            start_time = time.time()
            result = get_slurm_info()
            end_time = time.time()
            
            latency = end_time - start_time
            latencies.append(latency)
        
        # Performance metrics
        avg_latency = statistics.mean(latencies)
        max_latency = max(latencies)
        
        print(f"\n=== Cluster Info Query Metrics ===")
        print(f"Average latency: {avg_latency:.3f}s")
        print(f"Max latency: {max_latency:.3f}s")
        print(f"Queries per second: {1/avg_latency:.1f}")
        
        # Performance requirements
        assert avg_latency < 2.0, f"Cluster info query too slow: {avg_latency:.3f}s"

    def test_job_listing_performance(self, quick_script):
        """Test performance of job listing operations."""
        # Submit a few jobs first
        submitted_jobs = []
        for i in range(3):
            result = submit_slurm_job(quick_script, cores=1, job_name=f"perf_test_{i}")
            if not result.get("isError") and "job_id" in result:
                submitted_jobs.append(str(result["job_id"]))
        
        try:
            latencies = []
            num_tests = 5
            
            for _ in range(num_tests):
                start_time = time.time()
                result = list_slurm_jobs()
                end_time = time.time()
                
                latency = end_time - start_time
                latencies.append(latency)
            
            # Performance metrics
            avg_latency = statistics.mean(latencies)
            
            print(f"\n=== Job Listing Metrics ===")
            print(f"Average listing latency: {avg_latency:.3f}s")
            print(f"Listings per second: {1/avg_latency:.1f}")
            
            # Performance requirements
            assert avg_latency < 3.0, f"Job listing too slow: {avg_latency:.3f}s"
            
        finally:
            # Cleanup
            for job_id in submitted_jobs:
                try:
                    cancel_slurm_job(job_id)
                except Exception:
                    pass

    def test_node_info_performance(self):
        """Test node information retrieval performance."""
        latencies = []
        num_tests = 5
        
        for _ in range(num_tests):
            start_time = time.time()
            result = get_node_info()
            end_time = time.time()
            
            latency = end_time - start_time
            latencies.append(latency)
        
        # Performance metrics
        avg_latency = statistics.mean(latencies)
        
        print(f"\n=== Node Info Query Metrics ===")
        print(f"Average latency: {avg_latency:.3f}s")
        print(f"Queries per second: {1/avg_latency:.1f}")
        
        # Performance requirements
        assert avg_latency < 2.5, f"Node info query too slow: {avg_latency:.3f}s"

    def test_queue_info_performance(self):
        """Test queue information retrieval performance."""
        latencies = []
        num_tests = 5
        
        for _ in range(num_tests):
            start_time = time.time()
            result = get_queue_info()
            end_time = time.time()
            
            latency = end_time - start_time
            latencies.append(latency)
        
        # Performance metrics
        avg_latency = statistics.mean(latencies)
        
        print(f"\n=== Queue Info Query Metrics ===")
        print(f"Average latency: {avg_latency:.3f}s")
        print(f"Queries per second: {1/avg_latency:.1f}")
        
        # Performance requirements
        assert avg_latency < 2.0, f"Queue info query too slow: {avg_latency:.3f}s"

    def test_job_lifecycle_performance(self, quick_script):
        """Test the performance of a complete job lifecycle."""
        start_time = time.time()
        
        # Submit job
        submit_start = time.time()
        result = submit_slurm_job(quick_script, cores=1, job_name="lifecycle_test")
        submit_end = time.time()
        
        if result.get("isError"):
            pytest.skip("Could not submit job for lifecycle testing")
        
        job_id = str(result["job_id"])
        submit_time = submit_end - submit_start
        
        try:
            # Query status
            status_start = time.time()
            status_result = get_job_status(job_id)
            status_end = time.time()
            status_time = status_end - status_start
            
            # Get job details
            details_start = time.time()
            details_result = get_job_details(job_id)
            details_end = time.time()
            details_time = details_end - details_start
            
            # Cancel job
            cancel_start = time.time()
            cancel_result = cancel_slurm_job(job_id)
            cancel_end = time.time()
            cancel_time = cancel_end - cancel_start
            
            total_time = cancel_end - start_time
            
            print(f"\n=== Job Lifecycle Performance ===")
            print(f"Submit time: {submit_time:.3f}s")
            print(f"Status query time: {status_time:.3f}s")
            print(f"Details query time: {details_time:.3f}s")
            print(f"Cancel time: {cancel_time:.3f}s")
            print(f"Total lifecycle time: {total_time:.3f}s")
            
            # Performance requirements
            assert submit_time < 3.0, f"Job submission too slow: {submit_time:.3f}s"
            assert status_time < 1.0, f"Status query too slow: {status_time:.3f}s"
            assert details_time < 2.0, f"Details query too slow: {details_time:.3f}s"
            assert cancel_time < 2.0, f"Job cancellation too slow: {cancel_time:.3f}s"
            assert total_time < 8.0, f"Total lifecycle too slow: {total_time:.3f}s"
            
        except Exception as e:
            # Cleanup on error
            try:
                cancel_slurm_job(job_id)
            except Exception:
                pass
            raise e

    def test_array_job_performance(self):
        """Test array job submission performance."""
        # Create array job script
        script_content = """#!/bin/bash
#SBATCH --time=00:01:00
echo "Array task ${SLURM_ARRAY_TASK_ID}"
sleep 1
"""
        fd, script_path = tempfile.mkstemp(suffix='.sh', prefix='array_perf_')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(script_content)
            os.chmod(script_path, 0o755)
            
            start_time = time.time()
            result = submit_array_job(
                script_path, 
                array_range="1-3", 
                cores=1, 
                job_name="array_perf_test"
            )
            end_time = time.time()
            
            submission_time = end_time - start_time
            
            print(f"\n=== Array Job Performance ===")
            print(f"Array job submission time: {submission_time:.3f}s")
            
            # Cleanup if successful
            if not result.get("isError") and "job_id" in result:
                job_id = str(result["job_id"])
                try:
                    cancel_slurm_job(job_id)
                except Exception:
                    pass
            
            # Performance requirements
            assert submission_time < 5.0, f"Array job submission too slow: {submission_time:.3f}s"
            
        finally:
            # Cleanup script file
            if os.path.exists(script_path):
                os.unlink(script_path)

    @pytest.mark.slow
    def test_sustained_load_performance(self, quick_script):
        """Test performance under sustained load."""
        duration_seconds = 30
        max_concurrent = 3
        submitted_jobs = []
        
        def submit_and_track():
            result = submit_slurm_job(quick_script, cores=1)
            if not result.get("isError") and "job_id" in result:
                return str(result["job_id"])
            return None
        
        start_time = time.time()
        submission_times = []
        
        print(f"\n=== Starting Sustained Load Test ({duration_seconds}s) ===")
        
        while time.time() - start_time < duration_seconds:
            # Submit jobs in small batches
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                batch_start = time.time()
                futures = [executor.submit(submit_and_track) for _ in range(max_concurrent)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]
                batch_end = time.time()
                
                batch_time = batch_end - batch_start
                submission_times.append(batch_time)
                
                # Collect successful job IDs
                for job_id in results:
                    if job_id:
                        submitted_jobs.append(job_id)
                
                # Brief pause between batches
                time.sleep(1)
        
        total_time = time.time() - start_time
        total_submissions = len(submitted_jobs)
        avg_throughput = total_submissions / total_time if total_time > 0 else 0
        
        print(f"=== Sustained Load Results ===")
        print(f"Total submissions: {total_submissions}")
        print(f"Total time: {total_time:.1f}s")
        print(f"Average throughput: {avg_throughput:.2f} jobs/second")
        print(f"Average batch time: {statistics.mean(submission_times):.3f}s")
        
        # Cleanup all jobs
        print("Cleaning up submitted jobs...")
        cleanup_start = time.time()
        for job_id in submitted_jobs:
            try:
                cancel_slurm_job(job_id)
            except Exception:
                pass
        cleanup_time = time.time() - cleanup_start
        print(f"Cleanup time: {cleanup_time:.1f}s")
        
        # Performance requirements
        assert avg_throughput > 0.1, f"Throughput too low: {avg_throughput:.3f} jobs/s"
        assert total_submissions > 5, f"Too few successful submissions: {total_submissions}"

    def test_memory_usage_stability(self, quick_script):
        """Test that memory usage remains stable during operations."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Perform multiple operations
        operations = 0
        for _ in range(20):
            # Submit and cancel job
            result = submit_slurm_job(quick_script, cores=1)
            if not result.get("isError") and "job_id" in result:
                job_id = str(result["job_id"])
                cancel_slurm_job(job_id)
                operations += 1
            
            # Query cluster info
            get_slurm_info()
            operations += 1
        
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        print(f"\n=== Memory Usage Analysis ===")
        print(f"Initial memory: {initial_memory:.1f} MB")
        print(f"Final memory: {final_memory:.1f} MB")
        print(f"Memory increase: {memory_increase:.1f} MB")
        print(f"Operations performed: {operations}")
        print(f"Memory per operation: {memory_increase/operations:.3f} MB/op")
        
        # Memory requirements (should not grow excessively)
        assert memory_increase < 50, f"Excessive memory growth: {memory_increase:.1f} MB"
"""
Slurm node allocation capabilities.
Handles interactive resource allocation using salloc.
"""

import subprocess
import re
import time
import os
from typing import Optional, Dict, Any
from .utils import check_slurm_available


def allocate_nodes(
    nodes: int = 1,
    cores: int = 1,
    memory: Optional[str] = None,
    time_limit: Optional[str] = None,
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
    immediate: bool = False,
) -> Dict[str, Any]:
    """
    Allocate nodes using salloc for interactive sessions.

    Args:
        nodes: Number of nodes to allocate (default: 1)
        cores: Number of cores per node (default: 1)
        memory: Memory requirement (e.g., "4G", "2048M")
        time_limit: Time limit (e.g., "1:00:00", default: "01:00:00")
        partition: Slurm partition to use
        job_name: Name for the allocation
        immediate: Whether to return immediately without waiting for allocation

    Returns:
        Dictionary containing allocation information
    """
    if not check_slurm_available():
        return {
            "error": "Slurm is not available on this system",
            "status": "failed",
            "real_slurm": False,
        }

    # Only use real Slurm allocation - no mock mode
    return _allocate_real_slurm_nodes(
        nodes, cores, memory, time_limit, partition, job_name, immediate
    )


def _allocate_real_slurm_nodes(
    nodes: int,
    cores: int,
    memory: Optional[str] = None,
    time_limit: Optional[str] = None,
    partition: Optional[str] = None,
    job_name: Optional[str] = None,
    immediate: bool = False,
) -> Dict[str, Any]:
    """Allocate real Slurm nodes using salloc."""

    # Build salloc command
    cmd = ["salloc"]
    cmd.extend([f"--nodes={nodes}"])
    cmd.extend([f"--ntasks-per-node={cores}"])

    if memory:
        cmd.extend([f"--mem={memory}"])
    if time_limit:
        cmd.extend([f"--time={time_limit}"])
    else:
        cmd.extend(["--time=01:00:00"])  # Default 1 hour
    if partition:
        cmd.extend([f"--partition={partition}"])
    if job_name:
        cmd.extend([f"--job-name={job_name}"])
    else:
        cmd.extend(["--job-name=mcp_allocation"])

    # For immediate allocations, try a different approach
    if immediate:
        # Use shorter timeout and no-shell but avoid --immediate flag
        cmd.extend(["--no-shell"])
        timeout_duration = 10
    else:
        # For non-immediate, allow waiting
        cmd.extend(["--no-shell"])
        timeout_duration = 60

    print(f"🔄 Requesting allocation with command: {' '.join(cmd)}")
    print(f"⏱️  Timeout: {timeout_duration} seconds")

    try:
        # Run salloc command with proper timeout handling
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_duration,
            check=False,  # Don't raise on non-zero return codes, handle manually
        )

        print(f"🔍 salloc return code: {result.returncode}")
        print(f"🔍 salloc stdout: '{result.stdout.strip()}'")
        print(f"🔍 salloc stderr: '{result.stderr.strip()}'")

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            print(f"❌ salloc failed with return code {result.returncode}")
            print(f"❌ Error message: {error_msg}")

            if (
                "Immediate allocation impossible" in error_msg
                or "Unable to allocate resources" in error_msg
            ):
                return {
                    "error": "No resources available for allocation",
                    "status": "failed",
                    "real_slurm": True,
                    "message": error_msg,
                    "reason": "resources_unavailable",
                }
            elif "Job violates accounting/QOS policy" in error_msg:
                return {
                    "error": "Allocation violates policy constraints",
                    "status": "failed",
                    "real_slurm": True,
                    "message": error_msg,
                    "reason": "policy_violation",
                }
            else:
                return {
                    "error": f"salloc command failed: {error_msg}",
                    "status": "failed",
                    "real_slurm": True,
                    "message": error_msg,
                }

        output = result.stdout.strip()

        # Try alternative approach: check if allocation was actually created
        # by looking at recent jobs in squeue
        allocation_id = _get_recent_allocation_id()

        if allocation_id:
            print(f"✅ Found recent allocation ID: {allocation_id}")

            # Get node information
            time.sleep(1)  # Brief wait for allocation to be visible in squeue
            node_info = _get_allocation_nodes(allocation_id)

            allocation_info = {
                "allocation_id": allocation_id,
                "status": "allocated",
                "nodes": nodes,
                "cores": cores,
                "memory": memory,
                "time_limit": time_limit or "01:00:00",
                "partition": partition,
                "job_name": job_name or "mcp_allocation",
                "real_slurm": True,
            }

            if node_info:
                allocation_info.update(node_info)
                print(
                    f"🖥️  Allocated nodes: {allocation_info.get('allocated_nodes', 'Unknown')}"
                )

            print(f"💻 Cores per node: {cores}")
            return allocation_info

        # Parse allocation information from salloc output (fallback)
        allocation_info = _parse_salloc_output(output)

        if allocation_info.get("allocation_id"):
            allocation_id = str(allocation_info["allocation_id"])
            print(
                f"✅ Real Slurm allocation successful! Allocation ID: {allocation_id}"
            )

            # Get additional info if not already present
            if not allocation_info.get("allocated_nodes") and allocation_id:
                time.sleep(1)  # Brief wait for allocation to be visible in squeue
                node_info = _get_allocation_nodes(allocation_id)
                if node_info:
                    allocation_info.update(node_info)

            print(
                f"🖥️  Allocated nodes: {allocation_info.get('allocated_nodes', 'Unknown')}"
            )
            print(f"💻 Cores per node: {cores}")

            allocation_info.update(
                {
                    "status": "allocated",
                    "nodes": nodes,
                    "cores": cores,
                    "memory": memory,
                    "time_limit": time_limit or "01:00:00",
                    "partition": partition,
                    "job_name": job_name or "mcp_allocation",
                    "real_slurm": True,
                }
            )

            return allocation_info
        else:
            return {
                "error": "Could not parse allocation ID from salloc output and no recent allocations found",
                "status": "failed",
                "real_slurm": True,
                "salloc_output": output,
                "debug_info": "salloc completed successfully but allocation ID could not be determined",
            }

    except subprocess.TimeoutExpired:
        timeout_msg = f"Allocation request timed out ({timeout_duration} seconds)"
        print(f"⏰ {timeout_msg}")
        return {
            "error": timeout_msg,
            "status": "timeout",
            "real_slurm": True,
            "message": "The allocation request took too long. Resources may not be immediately available.",
            "timeout_duration": timeout_duration,
            "suggestion": "Try with immediate=True for quicker response or check resource availability",
        }
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        print(f"❌ salloc process failed: {error_msg}")
        return {
            "error": f"salloc process failed: {error_msg}",
            "status": "failed",
            "real_slurm": True,
            "return_code": e.returncode,
        }
    except Exception as e:
        print(f"❌ Exception during allocation: {e}")
        return {"error": str(e), "status": "failed", "real_slurm": True}


def _parse_salloc_output(output: str) -> Dict[str, Any]:
    """
    Parse salloc output to extract allocation information.

    Args:
        output: Raw output from salloc command

    Returns:
        Dictionary containing parsed allocation information
    """
    allocation_info = {}

    # Look for allocation granted message
    alloc_match = re.search(r"salloc: Granted job allocation (\d+)", output)
    if alloc_match:
        allocation_id = alloc_match.group(1)
        allocation_info["allocation_id"] = allocation_id

        # Get node information using squeue since salloc doesn't always provide it
        try:
            node_info = _get_allocation_nodes(allocation_id)
            if node_info:
                allocation_info.update(node_info)
        except Exception as e:
            print(f"⚠️  Could not get node info for allocation {allocation_id}: {e}")

    # Look for node list (alternative format)
    nodes_match = re.search(r"salloc: Nodes (.+) are ready for job", output)
    if nodes_match:
        node_list = nodes_match.group(1)
        # Expand node ranges if necessary (e.g., node[001-003] -> [node001, node002, node003])
        allocated_nodes = _expand_node_list(node_list)
        allocation_info["allocated_nodes"] = allocated_nodes

    return allocation_info


def _get_allocation_nodes(allocation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get node information for an allocation using squeue.

    Args:
        allocation_id: The allocation ID

    Returns:
        Dictionary with node information or None if not found
    """
    try:
        cmd = ["squeue", "-j", allocation_id, "--format=%N", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            nodelist = result.stdout.strip()
            if nodelist and nodelist != "(null)":
                return {
                    "allocated_nodes": _expand_node_list(nodelist),
                    "nodelist": nodelist,
                }
    except Exception:
        pass

    return None


def _expand_node_list(node_list: str) -> list:
    """
    Expand Slurm node list notation to individual node names.

    Args:
        node_list: Node list string (e.g., "node[001-003]" or "node001,node002")

    Returns:
        List of individual node names
    """
    nodes = []

    # Handle comma-separated nodes
    for part in node_list.split(","):
        part = part.strip()

        # Handle range notation like node[001-003]
        range_match = re.match(r"(.+)\[(\d+)-(\d+)\]", part)
        if range_match:
            prefix = range_match.group(1)
            start = int(range_match.group(2))
            end = int(range_match.group(3))
            width = len(range_match.group(2))  # Preserve zero-padding

            for i in range(start, end + 1):
                nodes.append(f"{prefix}{i:0{width}d}")
        else:
            # Single node
            nodes.append(part)

    return nodes


def deallocate_nodes(allocation_id: str) -> Dict[str, Any]:
    """
    Deallocate nodes by canceling the allocation.

    Args:
        allocation_id: The allocation ID to cancel

    Returns:
        Dictionary containing deallocation status
    """
    if not check_slurm_available():
        return {
            "error": "Slurm is not available on this system",
            "status": "failed",
            "real_slurm": False,
        }

    # Only use real Slurm deallocation - no mock mode
    return _deallocate_real_slurm_nodes(allocation_id)


def _deallocate_real_slurm_nodes(allocation_id: str) -> Dict[str, Any]:
    """Deallocate real Slurm allocation using scancel."""
    try:
        cmd = ["scancel", allocation_id]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            error_msg = result.stderr.strip()
            if "Invalid job id specified" in error_msg:
                return {
                    "error": f"Allocation {allocation_id} not found or already completed",
                    "status": "not_found",
                    "real_slurm": True,
                }
            raise RuntimeError(f"scancel failed: {error_msg}")

        print(f"✅ Allocation {allocation_id} deallocated successfully")

        return {
            "allocation_id": allocation_id,
            "status": "deallocated",
            "message": f"Allocation {allocation_id} deallocated successfully",
            "real_slurm": True,
        }

    except Exception as e:
        return {"error": str(e), "status": "failed", "real_slurm": True}


def get_allocation_status(allocation_id: str) -> Dict[str, Any]:
    """
    Get status of a node allocation.

    Args:
        allocation_id: The allocation ID to check

    Returns:
        Dictionary containing allocation status information
    """
    if not check_slurm_available():
        return {
            "error": "Slurm is not available on this system",
            "status": "failed",
            "real_slurm": False,
        }

    # Only use real Slurm status checking - no mock mode
    return _get_real_allocation_status(allocation_id)


def _get_real_allocation_status(allocation_id: str) -> Dict[str, Any]:
    """Get real Slurm allocation status using squeue."""
    try:
        cmd = ["squeue", "-j", allocation_id, "--format=%i,%T,%M,%N", "--noheader"]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            return {
                "allocation_id": allocation_id,
                "status": "not_found",
                "message": f"Allocation {allocation_id} not found in queue",
                "real_slurm": True,
            }

        output = result.stdout.strip()
        if not output:
            return {
                "allocation_id": allocation_id,
                "status": "completed",
                "message": f"Allocation {allocation_id} has completed or been cancelled",
                "real_slurm": True,
            }

        # Parse squeue output
        parts = output.split(",")
        if len(parts) >= 4:
            job_id, state, time_used, nodelist = parts

            return {
                "allocation_id": allocation_id,
                "status": "active" if state == "RUNNING" else "pending",
                "state": state,
                "time_used": time_used,
                "nodes": _expand_node_list(nodelist) if nodelist else [],
                "real_slurm": True,
            }
        else:
            return {
                "allocation_id": allocation_id,
                "status": "unknown",
                "message": f"Could not parse status for allocation {allocation_id}",
                "real_slurm": True,
            }

    except Exception as e:
        return {"error": str(e), "status": "error", "real_slurm": True}


def _get_recent_allocation_id() -> Optional[str]:
    """
    Get the most recent allocation ID for the current user.
    This is a fallback when salloc doesn't provide clear output.

    Returns:
        The most recent allocation ID or None if not found
    """
    try:
        # Get jobs for current user, sorted by job ID (newest first)
        cmd = [
            "squeue",
            "-u",
            os.getenv("USER", "unknown"),
            "--format=%i,%T,%j",
            "--noheader",
            "--sort=-i",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)

        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            for line in lines:
                parts = line.split(",")
                if len(parts) >= 3:
                    job_id, state, job_name = parts[0], parts[1], parts[2]
                    # Look for our allocation jobs that are running
                    if job_name.strip() == "mcp_allocation" and state.strip() in [
                        "RUNNING",
                        "PENDING",
                    ]:
                        return job_id.strip()
    except Exception as e:
        print(f"⚠️  Could not get recent allocation ID: {e}")

    return None

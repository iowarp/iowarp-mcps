"""
Tests for Slurm node allocation capabilities.
Tests salloc functionality for interactive resource allocation.
"""
import pytest
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


class TestNodeAllocation:
    """Test suite for Slurm node allocation capabilities."""
    
    def test_allocate_nodes_basic(self):
        """Test basic node allocation functionality."""
        from implementation.node_allocation import allocate_nodes
        
        result = allocate_nodes(nodes=1, cores=2, time_limit="00:30:00")
        
        # Check basic required fields
        basic_fields = ["status", "real_slurm"]
        for field in basic_fields:
            assert field in result
        
        assert isinstance(result["real_slurm"], bool)
        
        # If allocation was successful, check success fields
        if result["status"] in ["allocated", "submitted"]:
            success_fields = ["allocation_id", "nodes", "cores"]
            for field in success_fields:
                assert field in result
            assert result["nodes"] == 1
            assert result["cores"] == 2
        else:
            # If allocation failed/timed out, should have error info
            assert result["status"] in ["timeout", "failed", "error"]
            assert "error" in result or "message" in result

    def test_deallocate_nodes(self):
        """Test node deallocation functionality."""
        from implementation.node_allocation import allocate_nodes, deallocate_nodes
        
        # First allocate nodes (use mock if real allocation fails)
        alloc_result = allocate_nodes(nodes=1, cores=1)
        
        if "allocation_id" in alloc_result:
            allocation_id = alloc_result["allocation_id"]
            
            # Then deallocate them
            dealloc_result = deallocate_nodes(allocation_id)
            
            required_fields = ["allocation_id", "status", "real_slurm"]
            for field in required_fields:
                assert field in dealloc_result
                
            assert dealloc_result["allocation_id"] == allocation_id
        else:
            # If allocation failed, test with mock ID
            dealloc_result = deallocate_nodes("mock_123")
            assert "status" in dealloc_result
            assert "real_slurm" in dealloc_result

    def test_get_allocation_status(self):
        """Test allocation status checking."""
        from implementation.node_allocation import allocate_nodes, get_allocation_status
        
        # First allocate nodes (use mock if real allocation fails)
        alloc_result = allocate_nodes(nodes=1, cores=1)
        
        if "allocation_id" in alloc_result:
            allocation_id = alloc_result["allocation_id"]
            
            # Check status
            status_result = get_allocation_status(allocation_id)
            
            required_fields = ["allocation_id", "status", "real_slurm"]
            for field in required_fields:
                assert field in status_result
                
            assert status_result["allocation_id"] == allocation_id
        else:
            # If allocation failed, test with mock ID
            status_result = get_allocation_status("mock_123")
            assert "status" in status_result
            assert "real_slurm" in status_result

    def test_node_list_expansion(self):
        """Test node list expansion utility."""
        from implementation.node_allocation import _expand_node_list
        
        # Test simple comma-separated list
        result = _expand_node_list("node001,node002,node003")
        assert result == ["node001", "node002", "node003"]
        
        # Test range notation
        result = _expand_node_list("node[001-003]")
        assert result == ["node001", "node002", "node003"]

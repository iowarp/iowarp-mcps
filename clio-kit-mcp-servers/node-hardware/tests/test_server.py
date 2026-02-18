"""
Server tests - basic functionality tests for FastMCP v3.
"""

import pytest
from unittest.mock import patch

from node_hardware_mcp import server


class TestServerFixed:
    """Server tests for FastMCP v3"""

    def test_server_initialization(self):
        """Test server initialization"""
        assert hasattr(server, "mcp")
        assert server.mcp is not None
        assert hasattr(server.mcp, "name")
        assert server.mcp.name == "node-hardware"

    def test_server_tools_exist(self):
        """Test that all expected tools exist as module-level functions"""
        tools = [
            "get_cpu_info_tool",
            "get_memory_info_tool",
            "get_system_info_tool",
            "get_disk_info_tool",
            "get_network_info_tool",
            "get_gpu_info_tool",
            "get_sensor_info_tool",
            "get_process_info_tool",
            "get_performance_info_tool",
            "get_remote_node_info_tool",
        ]

        for tool_name in tools:
            assert hasattr(server, tool_name), f"Tool {tool_name} should exist"
            tool = getattr(server, tool_name)
            assert tool is not None, f"Tool {tool_name} should not be None"
            assert callable(tool), f"Tool {tool_name} should be callable"

    def test_server_logger(self):
        """Test server logger"""
        assert hasattr(server, "logger")
        assert server.logger is not None

    def test_server_exception(self):
        """Test custom exception"""
        assert hasattr(server, "NodeHardwareMCPError")

        try:
            raise server.NodeHardwareMCPError("Test error")
        except server.NodeHardwareMCPError as e:
            assert str(e) == "Test error"

    def test_server_main_function(self):
        """Test server main function with stdio transport"""
        assert hasattr(server, "main")

        with patch("sys.argv", ["node-hardware-mcp"]):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(transport="stdio")

    def test_server_resource_exists(self):
        """Test that the system_info resource function exists"""
        assert hasattr(server, "system_info")
        assert callable(server.system_info)

    def test_server_prompt_exists(self):
        """Test that the system_health_check prompt function exists"""
        assert hasattr(server, "system_health_check")
        assert callable(server.system_health_check)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

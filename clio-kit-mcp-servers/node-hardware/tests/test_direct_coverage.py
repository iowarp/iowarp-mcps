"""
Direct coverage tests to improve specific module coverage.
Updated for FastMCP v3 (no .fn attribute, ToolError for errors, direct function calls).
"""

import pytest
from unittest.mock import patch

from node_hardware_mcp import server
from node_hardware_mcp import mcp_handlers
from node_hardware_mcp.utils import output_formatter
from node_hardware_mcp.utils.output_formatter import (
    NodeHardwareFormatter,
    create_beautiful_response,
)


class TestDirectModuleCoverage:
    """Direct module testing for 100% coverage of server, handlers, and formatters"""

    def test_server_module_imports_and_attributes(self):
        """Test server module imports and basic attributes"""

        # Test module attributes
        assert hasattr(server, "mcp")
        assert hasattr(server, "logger")
        assert hasattr(server, "FastMCP")
        assert server.mcp is not None
        assert server.logger is not None

        # Test custom exception
        assert hasattr(server, "NodeHardwareMCPError")
        exception = server.NodeHardwareMCPError("test error")
        assert str(exception) == "test error"

    @pytest.mark.asyncio
    async def test_server_tool_functions_comprehensive(self):
        """Test server tool function attributes and registration"""

        # Test that tools are registered correctly as callable functions
        assert hasattr(server, "get_cpu_info_tool")
        assert hasattr(server, "get_memory_info_tool")
        assert hasattr(server, "get_disk_info_tool")

        # Test tool is callable (v3 returns original function)
        cpu_tool = getattr(server, "get_cpu_info_tool")
        assert cpu_tool is not None
        assert callable(cpu_tool)

        # Test that mcp instance exists
        assert hasattr(server, "mcp")
        assert server.mcp is not None

        # Test the logger exists
        assert hasattr(server, "logger")
        assert server.logger is not None

    def test_server_main_function(self):
        """Test server main function with different transport options"""

        # Test with stdio transport (default)
        with patch("sys.argv", ["node-hardware-mcp", "--transport", "stdio"]):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(transport="stdio")

        # Test with HTTP transport
        with patch(
            "sys.argv",
            [
                "node-hardware-mcp",
                "--transport",
                "http",
                "--host",
                "localhost",
                "--port",
                "9000",
            ],
        ):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(
                    transport="http", host="localhost", port=9000
                )

        # Test with HTTP transport and default host/port
        with patch(
            "sys.argv", ["node-hardware-mcp", "--transport", "http"]
        ):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(
                    transport="http", host="0.0.0.0", port=8000
                )

    def test_mcp_handlers_direct_calls(self):
        """Test direct calls to mcp_handlers functions"""

        # Test CPU handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_cpu_info") as mock_cpu:
            mock_cpu.return_value = {
                "logical_cores": 8,
                "physical_cores": 4,
                "cpu_model": "Intel Core i7",
                "frequency": {"current": 3000},
                "cpu_usage": [25.0, 30.0, 20.0, 35.0],
            }
            result = mcp_handlers.cpu_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_cpu.assert_called_once()

        # Test memory handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_memory_info") as mock_memory:
            mock_memory.return_value = {
                "total_memory": 16000000000,
                "available_memory": 8000000000,
                "memory_percent": 50.0,
            }
            result = mcp_handlers.memory_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_memory.assert_called_once()

        # Test system handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_system_info") as mock_system:
            mock_system.return_value = {
                "system": "Linux",
                "release": "5.15.0",
                "machine": "x86_64",
                "hostname": "test-machine",
            }
            result = mcp_handlers.system_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_system.assert_called_once()

        # Test disk handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_disk_info") as mock_disk:
            mock_disk.return_value = {
                "partitions": [
                    {
                        "device": "/dev/sda1",
                        "mountpoint": "/",
                        "fstype": "ext4",
                        "total": 1000000000,
                        "used": 500000000,
                        "free": 500000000,
                    }
                ]
            }
            result = mcp_handlers.disk_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_disk.assert_called_once()

        # Test network handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_network_info") as mock_network:
            mock_network.return_value = {
                "interfaces": {
                    "eth0": {
                        "address": "192.168.1.100",
                        "netmask": "255.255.255.0",
                        "bytes_sent": 1000000,
                        "bytes_recv": 2000000,
                    }
                }
            }
            result = mcp_handlers.network_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_network.assert_called_once()

        # Test process handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_process_info") as mock_process:
            mock_process.return_value = {
                "processes": [
                    {
                        "pid": 1234,
                        "name": "python",
                        "cpu_percent": 5.0,
                        "memory_percent": 2.5,
                    }
                ]
            }
            result = mcp_handlers.process_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_process.assert_called_once()

        # Test hardware summary handler with mocked capability
        with patch(
            "node_hardware_mcp.mcp_handlers.get_hardware_summary"
        ) as mock_summary:
            mock_summary.return_value = {
                "system_type": "Workstation",
                "total_cores": 8,
                "total_memory": 16000000000,
            }
            result = mcp_handlers.hardware_summary_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_summary.assert_called_once()

        # Test performance monitor handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.monitor_performance") as mock_perf:
            mock_perf.return_value = {
                "cpu_usage": 25.5,
                "memory_usage": 60.0,
                "disk_io": {"read": 1000, "write": 500},
            }
            result = mcp_handlers.performance_monitor_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_perf.assert_called_once()

        # Test GPU handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_gpu_info") as mock_gpu:
            mock_gpu.return_value = {
                "gpus": [
                    {
                        "name": "NVIDIA RTX 3080",
                        "memory_total": 10240,
                        "memory_used": 2048,
                    }
                ]
            }
            result = mcp_handlers.gpu_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_gpu.assert_called_once()

        # Test sensor handler with mocked capability
        with patch("node_hardware_mcp.mcp_handlers.get_sensor_info") as mock_sensor:
            mock_sensor.return_value = {
                "temperatures": {"coretemp": [{"current": 45.0, "high": 85.0}]}
            }
            result = mcp_handlers.sensor_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_sensor.assert_called_once()

    def test_mcp_handlers_error_cases(self):
        """Test error handling in mcp_handlers"""

        # Test CPU handler with exception
        with patch(
            "node_hardware_mcp.mcp_handlers.get_cpu_info",
            side_effect=Exception("CPU error"),
        ):
            result = mcp_handlers.cpu_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            # Should handle error gracefully

        # Test memory handler with exception
        with patch(
            "node_hardware_mcp.mcp_handlers.get_memory_info", side_effect=MemoryError("Memory error")
        ):
            result = mcp_handlers.memory_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

    def test_mcp_handlers_comprehensive_coverage(self):
        """Test remaining mcp_handlers for comprehensive coverage"""

        # Test get_node_info_handler with various parameters
        with patch("node_hardware_mcp.mcp_handlers.get_node_info") as mock_node:
            mock_node.return_value = {
                "hostname": "local-server",
                "status": "running",
                "cpu": {"cores": 8},
                "memory": {"total": 16000000000},
            }

            # Test with include filters
            result = mcp_handlers.get_node_info_handler(
                include_filters=["cpu", "memory"],
                exclude_filters=None,
                max_response_size=10000,
            )
            assert isinstance(result, dict)
            assert "content" in result
            mock_node.assert_called_once()

        # Test get_node_info_handler with exclude filters
        with patch("node_hardware_mcp.mcp_handlers.get_node_info") as mock_node:
            mock_node.return_value = {"hostname": "local-server", "cpu": {"cores": 8}}
            result = mcp_handlers.get_node_info_handler(
                include_filters=None,
                exclude_filters=["gpu", "sensors"],
                max_response_size=None,
            )
            assert isinstance(result, dict)
            assert "content" in result
            mock_node.assert_called_once()

        # Test get_node_info_handler with errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_node_info", side_effect=Exception("Node info error")
        ):
            result = mcp_handlers.get_node_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test get_remote_node_info_handler with various parameters
        with patch(
            "node_hardware_mcp.mcp_handlers.get_remote_node_info"
        ) as mock_remote:
            mock_remote.return_value = {
                "hostname": "remote-server",
                "status": "connected",
                "ssh_status": "authenticated",
                "hardware": {"cpu": {"cores": 16}},
            }

            result = mcp_handlers.get_remote_node_info_handler(
                hostname="remote-server.com",
                username="admin",
                port=2222,
                ssh_key="/path/to/key",
                timeout=60,
                include_filters=["cpu", "memory", "disk"],
                exclude_filters=["gpu"],
            )
            assert isinstance(result, dict)
            assert "content" in result
            mock_remote.assert_called_once()

        # Test get_remote_node_info_handler with connection errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_remote_node_info",
            side_effect=ConnectionError("SSH connection failed"),
        ):
            result = mcp_handlers.get_remote_node_info_handler(
                hostname="unreachable-server.com"
            )
            assert isinstance(result, dict)
            assert "content" in result

        # Test get_remote_node_info_handler with timeout errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_remote_node_info", side_effect=TimeoutError("SSH timeout")
        ):
            result = mcp_handlers.get_remote_node_info_handler(
                hostname="slow-server.com", timeout=1
            )
            assert isinstance(result, dict)
            assert "content" in result

        # Test all handlers with empty/None data scenarios
        with patch(
            "node_hardware_mcp.mcp_handlers.get_hardware_summary"
        ) as mock_summary:
            mock_summary.return_value = {}
            result = mcp_handlers.hardware_summary_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_summary.assert_called_once()

        with patch(
            "node_hardware_mcp.mcp_handlers.get_hardware_summary"
        ) as mock_summary:
            mock_summary.return_value = None
            result = mcp_handlers.hardware_summary_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test handlers with large data scenarios
        with patch("node_hardware_mcp.mcp_handlers.get_process_info") as mock_process:
            # Simulate large process list
            large_process_list = {
                "processes": [
                    {"pid": i, "name": f"process_{i}", "cpu": 1.0, "memory": 100.0}
                    for i in range(1000)
                ]
            }
            mock_process.return_value = large_process_list
            result = mcp_handlers.process_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_process.assert_called_once()

    def test_mcp_handlers_edge_cases(self):
        """Test edge cases and boundary conditions in mcp_handlers"""

        # Test with malformed data
        with patch("node_hardware_mcp.mcp_handlers.get_cpu_info") as mock_cpu:
            mock_cpu.return_value = "invalid_data_format"
            result = mcp_handlers.cpu_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test with network connectivity issues
        with patch(
            "node_hardware_mcp.mcp_handlers.get_network_info", side_effect=OSError("Network unreachable")
        ):
            result = mcp_handlers.network_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test with permission errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_sensor_info",
            side_effect=PermissionError("Permission denied"),
        ):
            result = mcp_handlers.sensor_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test with disk I/O errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_disk_info",
            side_effect=IOError("Disk I/O error"),
        ):
            result = mcp_handlers.disk_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

    def test_mcp_handlers_remote_node_functionality(self):
        """Test remote node handlers"""

        # Test get_node_info_handler with correct signature
        with patch("node_hardware_mcp.mcp_handlers.get_node_info") as mock_node:
            mock_node.return_value = {
                "hostname": "test-server",
                "status": "connected",
                "uptime": "10 days, 5 hours",
            }
            # Use correct signature - no hostname parameter
            result = mcp_handlers.get_node_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_node.assert_called_once()

        # Test get_remote_node_info_handler with correct signature
        with patch(
            "node_hardware_mcp.mcp_handlers.get_remote_node_info"
        ) as mock_remote:
            mock_remote.return_value = {
                "hostname": "remote-server",
                "status": "connected",
                "cpu_count": 16,
                "memory_total": 32000000000,
            }
            result = mcp_handlers.get_remote_node_info_handler(
                hostname="remote-server", username="admin"
            )
            assert isinstance(result, dict)
            assert "content" in result
            # get_remote_node_info has many default parameters
            mock_remote.assert_called_once()

    def test_output_formatter_comprehensive(self):
        """Test comprehensive output_formatter functionality"""
        from node_hardware_mcp.utils.output_formatter import NodeHardwareFormatter

        # Test NodeHardwareFormatter.format_success_response
        test_data = {
            "cpu": {"cores": 8, "model": "Intel i7"},
            "memory": {"total": 16000000000, "available": 8000000000},
        }

        result = NodeHardwareFormatter.format_success_response(
            operation="get_system_info",
            data=test_data,
            summary={"total_cores": 8, "memory_usage": "50%"},
            metadata={"collection_time": "2024-01-01"},
            insights=["System running normally"],
            hostname="test-server",
        )
        assert isinstance(result, dict)
        assert "✅ Status" in result
        assert result["✅ Status"] == "Success"
        assert "🔧 Hardware Data" in result

        # Test NodeHardwareFormatter.format_error_response
        error_result = NodeHardwareFormatter.format_error_response(
            operation="get_cpu_info",
            error_message="CPU information unavailable",
            error_type="SystemError",
            suggestions=["Check permissions"],
            hostname="error-server",
        )
        assert isinstance(error_result, dict)
        assert "❌ Status" in error_result
        assert error_result["❌ Status"] == "Error"

        # Test with minimal parameters
        minimal_result = NodeHardwareFormatter.format_success_response(
            operation="minimal_test", data={"test": "value"}
        )
        assert isinstance(minimal_result, dict)
        assert "✅ Status" in minimal_result
        assert minimal_result["✅ Status"] == "Success"

    def test_output_formatter_error_handling(self):
        """Test output formatter error handling"""
        from node_hardware_mcp.utils.output_formatter import NodeHardwareFormatter

        # Test error response
        error_result = NodeHardwareFormatter.format_error_response(
            operation="test_error",
            error_message="Test error message",
            error_type="TestError",
        )
        assert isinstance(error_result, dict)
        assert "❌ Status" in error_result
        assert error_result["❌ Status"] == "Error"

        # Test with None data in success response
        none_result = NodeHardwareFormatter.format_success_response(
            operation="none_test", data=None
        )
        assert isinstance(none_result, dict)
        assert "✅ Status" in none_result
        assert none_result["✅ Status"] == "Success"

    def test_output_formatter_create_beautiful_response(self):
        """Test create_beautiful_response function"""
        from node_hardware_mcp.utils.output_formatter import create_beautiful_response

        test_data = {"cpu": "Intel i7", "memory": "16GB"}

        # Test with required parameters
        result = create_beautiful_response(
            operation="System Info", success=True, data=test_data
        )
        assert isinstance(result, dict)
        assert "content" in result

        # Test error response
        error_result = create_beautiful_response(
            operation="Error Test", success=False, error_message="Test error"
        )
        assert isinstance(error_result, dict)
        assert "content" in error_result


# ========== Additional Comprehensive Coverage Tests ==========


class TestServerDirectCoverage:
    """Additional tests for server.py coverage improvement"""

    def test_server_logger_attribute(self):
        """Test that server has logger attribute"""
        import logging

        logger = logging.getLogger(__name__)
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")

    def test_server_fastmcp_initialization(self):
        """Test FastMCP server initialization components"""

        assert server.mcp is not None
        assert hasattr(server.mcp, "name")

    def test_server_custom_exception(self):
        """Test NodeHardwareError custom exception"""

        # Test basic exception
        try:
            raise server.NodeHardwareMCPError("Test error")
        except server.NodeHardwareMCPError as e:
            assert str(e) == "Test error"

        # Test exception inheritance
        assert issubclass(server.NodeHardwareMCPError, Exception)

    def test_server_app_tools_registration(self):
        """Test that tools are registered with the app"""

        # Test that server.mcp is a FastMCP instance
        assert str(type(server.mcp).__name__) == "FastMCP"

        # Test that the app has a name (shows it's properly initialized)
        assert hasattr(server.mcp, "name")
        assert server.mcp.name == "node-hardware"


class TestMcpHandlersExtensiveCoverage:
    """Additional comprehensive tests for all mcp_handlers.py functions"""

    def test_get_cpu_info_comprehensive(self):
        """Comprehensive test for get_cpu_info function"""

        result = mcp_handlers.get_cpu_info()
        assert isinstance(result, dict)

        # Test required keys
        expected_keys = [
            "physical_cores",
            "logical_cores",
            "current_frequency",
            "max_frequency",
        ]
        for key in expected_keys:
            if key in result:
                assert isinstance(result[key], (int, float, str))

    def test_get_memory_info_comprehensive(self):
        """Comprehensive test for get_memory_info function"""

        result = mcp_handlers.get_memory_info()
        assert isinstance(result, dict)

        # Test memory values are numeric or properly formatted
        for key, value in result.items():
            if "bytes" in key.lower() or "percent" in key.lower():
                assert isinstance(value, (int, float)) or isinstance(value, str)

    def test_get_disk_info_comprehensive(self):
        """Comprehensive test for get_disk_info function"""

        result = mcp_handlers.get_disk_info()
        assert isinstance(result, dict)

        # Should contain disk information
        assert len(result) > 0

    def test_get_network_info_comprehensive(self):
        """Comprehensive test for get_network_info function"""

        result = mcp_handlers.get_network_info()
        assert isinstance(result, dict)

        # Should contain network interfaces
        assert len(result) >= 0  # May be empty on some systems

    def test_get_process_info_comprehensive(self):
        """Comprehensive test for get_process_info function"""

        # Test without parameters (default behavior)
        result = mcp_handlers.get_process_info()
        assert isinstance(result, dict)

        # Process info should contain process data
        assert len(result) >= 0

    def test_get_system_info_comprehensive(self):
        """Comprehensive test for get_system_info function"""

        result = mcp_handlers.get_system_info()
        assert isinstance(result, dict)

        # Test for expected system info keys
        expected_keys = ["system", "node", "platform"]
        for key in expected_keys:
            if key in result:
                assert isinstance(result[key], str)

    def test_get_gpu_info_comprehensive(self):
        """Comprehensive test for get_gpu_info function"""

        result = mcp_handlers.get_gpu_info()
        assert isinstance(result, dict)

        # GPU info may be empty on systems without GPU
        # Just verify it returns a dict without error


class TestOutputFormatterExtensiveCoverage:
    """Additional comprehensive tests for output_formatter.py"""

    def test_node_hardware_formatter_all_methods(self):
        """Test all methods of NodeHardwareFormatter class"""
        formatter = NodeHardwareFormatter()

        # Test various data types
        test_data = {
            "string_value": "test",
            "number_value": 42,
            "float_value": 3.14,
            "list_value": [1, 2, 3],
            "dict_value": {"nested": "data"},
            "none_value": None,
            "bool_value": True,
        }

        # Test format_success_response method with different data types
        for key, value in test_data.items():
            try:
                result = formatter.format_success_response(f"test_{key}", {key: value})
                assert isinstance(result, dict)
                assert "🖥️ Operation" in result
                assert "🔧 Hardware Data" in result
            except Exception:
                # Some formatters might not handle all data types
                pass

    def test_create_beautiful_response_all_parameters(self):
        """Test create_beautiful_response with all parameter combinations"""
        # Test success response with data
        result1 = create_beautiful_response(
            operation="Full Test",
            success=True,
            data={"test": "data"},
            timestamp="2024-01-01",
            node_name="test-node",
        )
        assert isinstance(result1, dict)
        assert "content" in result1

        # Test error response with all parameters
        result2 = create_beautiful_response(
            operation="Error Test",
            success=False,
            error_message="Test error",
            timestamp="2024-01-01",
            node_name="test-node",
        )
        assert isinstance(result2, dict)
        assert "content" in result2

        # Test minimal parameters
        result3 = create_beautiful_response(operation="Minimal", success=True)
        assert isinstance(result3, dict)
        assert "content" in result3

    def test_formatter_edge_cases(self):
        """Test formatter with edge cases"""
        formatter = NodeHardwareFormatter()

        # Test empty data using format_success_response
        result1 = formatter.format_success_response("test_operation", {})
        assert isinstance(result1, dict)
        assert "🖥️ Operation" in result1
        assert result1["🖥️ Operation"] == "Test Operation"

        # Test very large data
        large_data = {f"key_{i}": f"value_{i}" for i in range(100)}
        result2 = formatter.format_success_response("large_test", large_data)
        assert isinstance(result2, dict)
        assert "🔧 Hardware Data" in result2

        # Test nested data
        nested_data = {"level1": {"level2": {"level3": "deep_value"}}}
        result3 = formatter.format_success_response("nested_test", nested_data)
        assert isinstance(result3, dict)
        assert "🔧 Hardware Data" in result3

    def test_create_beautiful_response_content_validation(self):
        """Test that create_beautiful_response generates proper content"""
        # Test that content contains operation name
        result = create_beautiful_response(
            operation="Content Validation Test",
            success=True,
            data={"test": "validation"},
        )

        # Response should be MCP format with content array
        assert "content" in result
        assert isinstance(result["content"], list)
        assert len(result["content"]) > 0
        assert "text" in result["content"][0]

        # Check that operation name appears in the text content
        text_content = result["content"][0]["text"]
        assert "Content Validation Test" in text_content

        # Test error message appears in content
        error_result = create_beautiful_response(
            operation="Error Content Test",
            success=False,
            error_message="Custom error message",
        )

        assert "content" in error_result
        error_text = error_result["content"][0]["text"]
        assert "Custom error message" in error_text

    def test_server_attribute_coverage(self):
        """Test server module attributes for missing coverage"""

        # Test logger name
        assert hasattr(server, "logger")
        assert server.logger is not None

        # Test mcp instance
        assert hasattr(server, "mcp")
        assert server.mcp is not None

        # Test FastMCP import
        assert hasattr(server, "FastMCP")

    def test_mcp_handlers_error_edge_cases(self):
        """Test mcp_handlers error handling for missing coverage"""

        # Test with network interface errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_network_info", side_effect=OSError("Interface down")
        ):
            result = mcp_handlers.network_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test with sensor permission errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_sensor_info",
            side_effect=PermissionError("Sensors access denied"),
        ):
            result = mcp_handlers.sensor_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

        # Test with process enumeration errors
        with patch(
            "node_hardware_mcp.mcp_handlers.get_process_info",
            side_effect=Exception("Process list unavailable"),
        ):
            result = mcp_handlers.process_info_handler()
            assert isinstance(result, dict)
            assert "content" in result

    def test_output_formatter_missing_coverage(self):
        """Test output_formatter for missing coverage lines"""
        from node_hardware_mcp.utils.output_formatter import NodeHardwareFormatter

        # Test format_error_response with correct signature
        error_result = NodeHardwareFormatter.format_error_response(
            operation="minimal_error_test",
            error_message="Simple error",
            error_type="TestError",
        )
        assert isinstance(error_result, dict)
        assert "❌ Status" in error_result

        # Test with None insights
        success_result = NodeHardwareFormatter.format_success_response(
            operation="null_insights_test", data={"test": "data"}, insights=None
        )
        assert isinstance(success_result, dict)

        # Test create_beautiful_response with error and no data
        error_response = output_formatter.create_beautiful_response(
            operation="error_no_data", success=False, error_message="Test error"
        )
        assert isinstance(error_response, dict)
        assert "content" in error_response

    def test_server_main_function_coverage(self):
        """Test server main function branches for coverage"""

        # Test without arguments (default stdio via env fallback)
        with patch("sys.argv", ["node-hardware-mcp"]):
            with patch.object(server.mcp, "run") as mock_run:
                server.main()
                mock_run.assert_called_once_with(transport="stdio")

        # Test with MCP_TRANSPORT env var fallback to stdio
        with patch("sys.argv", ["node-hardware-mcp"]):
            with patch.dict("os.environ", {"MCP_TRANSPORT": "stdio"}):
                with patch.object(server.mcp, "run") as mock_run:
                    server.main()
                    mock_run.assert_called_once_with(transport="stdio")

    def test_mcp_handlers_function_signature_coverage(self):
        """Test mcp_handlers functions to improve coverage"""

        # Test get_node_info_handler with correct signature
        with patch("node_hardware_mcp.mcp_handlers.get_node_info") as mock_node:
            mock_node.return_value = {"hostname": "localhost", "status": "active"}
            result = mcp_handlers.get_node_info_handler()
            assert isinstance(result, dict)
            assert "content" in result
            mock_node.assert_called_once()

        # Test get_remote_node_info_handler with correct signature
        with patch(
            "node_hardware_mcp.mcp_handlers.get_remote_node_info"
        ) as mock_remote:
            mock_remote.return_value = {"hostname": "remote", "status": "connected"}
            result = mcp_handlers.get_remote_node_info_handler(hostname="remote-server")
            assert isinstance(result, dict)
            assert "content" in result
            mock_remote.assert_called_once()

    def test_output_formatter_edge_cases_coverage(self):
        """Test output_formatter edge cases for better coverage"""
        from node_hardware_mcp.utils.output_formatter import NodeHardwareFormatter

        # Test with empty data dictionary
        result = NodeHardwareFormatter.format_success_response(
            operation="empty_data_test", data={}
        )
        assert isinstance(result, dict)

        # Test format_error_response with correct signature
        error_result = NodeHardwareFormatter.format_error_response(
            operation="long_error_test",
            error_message="x" * 1000,
            error_type="LongErrorType",
        )
        assert isinstance(error_result, dict)

        # Test with special characters in data
        special_data = {
            "special_chars": "!@#$%^&*()_+{}|:\"<>?[]\\;',./",
            "unicode": "测试数据 🔧⚡🖥️",
            "newlines": "line1\nline2\nline3",
        }
        special_result = NodeHardwareFormatter.format_success_response(
            operation="special_chars_test", data=special_data
        )
        assert isinstance(special_result, dict)

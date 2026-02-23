"""
Configuration and fixtures for Node Hardware MCP tests.
"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def mock_psutil():
    """Mock psutil module for consistent testing."""
    with (
        patch("psutil.cpu_count") as mock_cpu_count,
        patch("psutil.cpu_freq") as mock_cpu_freq,
        patch("psutil.cpu_percent") as mock_cpu_percent,
        patch("psutil.virtual_memory") as mock_virtual_memory,
        patch("psutil.swap_memory") as mock_swap_memory,
        patch("psutil.disk_usage") as mock_disk_usage,
        patch("psutil.disk_partitions") as mock_disk_partitions,
        patch("psutil.net_io_counters") as mock_net_io_counters,
        patch("psutil.net_if_addrs") as mock_net_if_addrs,
        patch("psutil.boot_time") as mock_boot_time,
        patch("psutil.users") as mock_users,
        patch("psutil.process_iter") as mock_process_iter,
        patch("psutil.sensors_temperatures") as mock_sensors_temperatures,
        patch("psutil.sensors_fans") as mock_sensors_fans,
        patch("psutil.disk_io_counters") as mock_disk_io_counters,
    ):
        # Configure CPU mocks
        mock_cpu_count.return_value = 8
        mock_cpu_freq.return_value = Mock(current=2400.0, min=800.0, max=3200.0)
        mock_cpu_percent.return_value = [25.0, 30.0, 20.0, 40.0, 35.0, 25.0, 15.0, 45.0]

        # Configure memory mocks
        mock_virtual_memory.return_value = Mock(
            total=16 * 1024 * 1024 * 1024,  # 16GB
            available=8 * 1024 * 1024 * 1024,  # 8GB
            used=8 * 1024 * 1024 * 1024,  # 8GB
            percent=50.0,
        )
        mock_swap_memory.return_value = Mock(
            total=4 * 1024 * 1024 * 1024,  # 4GB
            used=1 * 1024 * 1024 * 1024,  # 1GB
            percent=25.0,
        )

        # Configure disk mocks
        mock_disk_usage.return_value = Mock(
            total=500 * 1024 * 1024 * 1024,  # 500GB
            used=200 * 1024 * 1024 * 1024,  # 200GB
            free=300 * 1024 * 1024 * 1024,  # 300GB
        )
        mock_disk_partitions.return_value = [
            Mock(device="/dev/sda1", mountpoint="/", fstype="ext4", opts="rw,relatime"),
            Mock(
                device="/dev/sda2",
                mountpoint="/home",
                fstype="ext4",
                opts="rw,relatime",
            ),
        ]

        # Configure disk I/O mocks
        mock_disk_io_counters.return_value = Mock(
            read_count=1000,
            write_count=500,
            read_bytes=1024 * 1024 * 100,  # 100MB
            write_bytes=1024 * 1024 * 50,  # 50MB
        )

        # Configure network mocks
        mock_net_io_counters.return_value = Mock(
            bytes_sent=1024 * 1024 * 100,  # 100MB
            bytes_recv=1024 * 1024 * 200,  # 200MB
            packets_sent=10000,
            packets_recv=15000,
        )
        mock_net_if_addrs.return_value = {
            "eth0": [Mock(family=2, address="192.168.1.100", netmask="255.255.255.0")],
            "lo": [Mock(family=2, address="127.0.0.1", netmask="255.0.0.0")],
        }

        # Configure system mocks
        mock_boot_time.return_value = 1640995200  # 2022-01-01 00:00:00
        mock_users.return_value = [
            Mock(name="testuser", terminal="pts/0", host="localhost")
        ]

        # Configure process mocks
        mock_process = Mock()
        mock_process.info = {
            "pid": 1234,
            "name": "test_process",
            "cpu_percent": 5.0,
            "memory_percent": 2.5,
            "status": "running",
        }
        mock_process_iter.return_value = [mock_process]

        # Configure sensor mocks
        mock_sensors_temperatures.return_value = {
            "coretemp": [Mock(label="Core 0", current=45.0, high=100.0, critical=105.0)]
        }
        mock_sensors_fans.return_value = {"acpi": [Mock(label="CPU Fan", current=2000)]}

        yield {
            "cpu_count": mock_cpu_count,
            "cpu_freq": mock_cpu_freq,
            "cpu_percent": mock_cpu_percent,
            "virtual_memory": mock_virtual_memory,
            "swap_memory": mock_swap_memory,
            "disk_usage": mock_disk_usage,
            "disk_partitions": mock_disk_partitions,
            "disk_io_counters": mock_disk_io_counters,
            "net_io_counters": mock_net_io_counters,
            "net_if_addrs": mock_net_if_addrs,
            "boot_time": mock_boot_time,
            "users": mock_users,
            "process_iter": mock_process_iter,
            "sensors_temperatures": mock_sensors_temperatures,
            "sensors_fans": mock_sensors_fans,
        }


@pytest.fixture
def mock_platform():
    """Mock platform module for consistent testing."""
    with (
        patch("platform.system") as mock_system,
        patch("platform.release") as mock_release,
        patch("platform.version") as mock_version,
        patch("platform.machine") as mock_machine,
        patch("platform.processor") as mock_processor,
        patch("platform.node") as mock_node,
    ):
        mock_system.return_value = "Linux"
        mock_release.return_value = "5.15.0"
        mock_version.return_value = "#1 SMP Fri Nov 12 10:00:00 UTC 2021"
        mock_machine.return_value = "x86_64"
        mock_processor.return_value = "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz"
        mock_node.return_value = "test-hostname"

        yield {
            "system": mock_system,
            "release": mock_release,
            "version": mock_version,
            "machine": mock_machine,
            "processor": mock_processor,
            "node": mock_node,
        }


@pytest.fixture
def mock_subprocess():
    """Mock subprocess for command execution."""
    with (
        patch("subprocess.run") as mock_run,
        patch("subprocess.check_output") as mock_check_output,
    ):
        mock_run.return_value = Mock(returncode=0, stdout="test output", stderr="")
        mock_check_output.return_value = b"test command output"

        yield {
            "run": mock_run,
            "check_output": mock_check_output,
        }


@pytest.fixture
def mock_os():
    """Mock os module functions."""
    with patch("os.getenv") as mock_getenv, patch("os.path.exists") as mock_exists:
        mock_getenv.side_effect = lambda key, default=None: {
            "USER": "testuser",
            "HOME": "/home/testuser",
            "PATH": "/usr/bin:/bin",
        }.get(key, default)

        mock_exists.return_value = True

        yield {
            "getenv": mock_getenv,
            "exists": mock_exists,
        }


@pytest.fixture
def sample_hardware_data():
    """Sample hardware data for testing."""
    return {
        "cpu": {
            "model": "Intel Core i7-9750H",
            "cores": 8,
            "frequency": 2600.0,
            "usage": 25.5,
        },
        "memory": {
            "total": 16 * 1024 * 1024 * 1024,
            "used": 8 * 1024 * 1024 * 1024,
            "percent": 50.0,
        },
        "disk": {
            "total": 500 * 1024 * 1024 * 1024,
            "used": 200 * 1024 * 1024 * 1024,
            "percent": 40.0,
        },
    }


@pytest.fixture
def mock_ssh_client():
    """Mock SSH client for remote testing."""
    mock_client = Mock()
    mock_client.connect.return_value = None
    mock_client.exec_command.return_value = (
        Mock(),  # stdin
        Mock(read=lambda: b'{"result": "success"}'),  # stdout
        Mock(read=lambda: b""),  # stderr
    )
    mock_client.close.return_value = None

    with patch("paramiko.SSHClient", return_value=mock_client):
        yield mock_client


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset all mocks between tests."""
    yield
    # This fixture runs after each test to ensure clean state

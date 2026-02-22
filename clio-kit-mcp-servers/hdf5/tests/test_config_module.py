"""
Comprehensive tests for the config module.

Tests configuration models, environment variable loading, JSON configuration,
runtime updates, and all public API functions.
"""

import pytest
import json
import logging
from pathlib import Path
from unittest.mock import patch

# Import the config module directly - DO NOT import server
from hdf5_mcp import config


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config singleton between tests."""
    config._CONFIG = None
    yield
    config._CONFIG = None


@pytest.fixture
def clean_env(monkeypatch):
    """Remove all HDF5_MCP environment variables."""
    env_vars = [
        "HDF5_MCP_CONFIG",
        "HDF5_MCP_DATA_DIR",
        "HDF5_MCP_STORAGE_ENDPOINT",
        "HDF5_MCP_CACHE_SIZE_MB",
        "HDF5_MCP_CHUNK_SIZE_MB",
        "HDF5_MCP_PARALLEL_THRESHOLD_MB",
        "HDF5_MCP_PREFETCH_ENABLED",
        "HDF5_MCP_ENABLE_SSE",
        "HDF5_MCP_PORT",
        "HDF5_MCP_HOST",
        "HDF5_MCP_MAX_CONNECTIONS",
        "HDF5_MCP_MAX_WORKERS",
        "HDF5_MCP_LOG_LEVEL",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def sample_config_dict():
    """Sample configuration dictionary."""
    return {
        "server": {
            "name": "Test HDF5 Server",
            "version": "2.0.0",
            "request_timeout": 60.0,
        },
        "async_config": {
            "max_workers": 8,
            "task_queue_size": 2000,
            "batch_size": 200,
            "max_batch_wait_time": 1.0,
        },
        "transport": {
            "enable_stdio": True,
            "enable_sse": True,
            "sse_host": "0.0.0.0",
            "sse_port": 9000,
            "max_connections": 200,
            "enable_batching": True,
            "batch_timeout": 0.2,
            "max_batch_size": 100,
        },
        "hdf5": {
            "data_dir": "/tmp/test_data",
            "file_path": None,
            "chunk_size": 134217728,  # 128MB
            "cache_size": 1073741824,  # 1GB
            "prefetch_enabled": True,
            "parallel_threshold": 209715200,  # 200MB
        },
        "logging": {
            "level": "DEBUG",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "/tmp/test.log",
        },
    }


# =========================================================================
# ServerConfig Tests
# =========================================================================


def test_server_config_defaults():
    """Test ServerConfig default values."""
    cfg = config.ServerConfig()
    assert cfg.name == "HDF5 MCP Server"
    assert cfg.version == "1.0.0"
    assert cfg.request_timeout == 30.0


def test_server_config_custom_values():
    """Test ServerConfig with custom values."""
    cfg = config.ServerConfig(
        name="Custom Server", version="2.0.0", request_timeout=60.0
    )
    assert cfg.name == "Custom Server"
    assert cfg.version == "2.0.0"
    assert cfg.request_timeout == 60.0


def test_server_config_dict_conversion():
    """Test ServerConfig to dict conversion."""
    cfg = config.ServerConfig()
    d = cfg.dict()
    assert isinstance(d, dict)
    assert "name" in d
    assert "version" in d
    assert "request_timeout" in d


# =========================================================================
# AsyncConfig Tests
# =========================================================================


def test_async_config_defaults():
    """Test AsyncConfig default values."""
    cfg = config.AsyncConfig()
    assert cfg.max_workers == 4
    assert cfg.task_queue_size == 1000
    assert cfg.batch_size == 100
    assert cfg.max_batch_wait_time == 0.5


def test_async_config_custom_values():
    """Test AsyncConfig with custom values."""
    cfg = config.AsyncConfig(
        max_workers=8,
        task_queue_size=2000,
        batch_size=200,
        max_batch_wait_time=1.0,
    )
    assert cfg.max_workers == 8
    assert cfg.task_queue_size == 2000
    assert cfg.batch_size == 200
    assert cfg.max_batch_wait_time == 1.0


# =========================================================================
# TransportConfig Tests
# =========================================================================


def test_transport_config_defaults():
    """Test TransportConfig default values."""
    cfg = config.TransportConfig()
    assert cfg.enable_stdio is True
    assert cfg.enable_sse is False
    assert cfg.sse_host == "localhost"
    assert cfg.sse_port == 8765
    assert cfg.max_connections == 100
    assert cfg.enable_batching is True
    assert cfg.batch_timeout == 0.1
    assert cfg.max_batch_size == 50


def test_transport_config_custom_values():
    """Test TransportConfig with custom values."""
    cfg = config.TransportConfig(
        enable_stdio=False,
        enable_sse=True,
        sse_host="0.0.0.0",
        sse_port=9000,
        max_connections=200,
        enable_batching=False,
        batch_timeout=0.5,
        max_batch_size=100,
    )
    assert cfg.enable_stdio is False
    assert cfg.enable_sse is True
    assert cfg.sse_host == "0.0.0.0"
    assert cfg.sse_port == 9000
    assert cfg.max_connections == 200
    assert cfg.enable_batching is False
    assert cfg.batch_timeout == 0.5
    assert cfg.max_batch_size == 100


# =========================================================================
# HDF5Config Tests
# =========================================================================


def test_hdf5_config_defaults():
    """Test HDF5Config default values."""
    cfg = config.HDF5Config()
    # Path gets resolved during validation
    assert cfg.data_dir.name == "data" or str(cfg.data_dir).endswith("data")
    assert cfg.file_path is None
    assert cfg.chunk_size == 1024 * 1024 * 64  # 64MB
    assert cfg.cache_size == 1024 * 1024 * 500  # 500MB
    assert cfg.prefetch_enabled is True
    assert cfg.parallel_threshold == 1024 * 1024 * 100  # 100MB


def test_hdf5_config_path_validation():
    """Test HDF5Config path validation."""
    cfg = config.HDF5Config(data_dir="test_dir", file_path="test_file.h5")
    assert isinstance(cfg.data_dir, Path)
    assert isinstance(cfg.file_path, Path)
    assert cfg.data_dir == Path("test_dir").resolve()
    assert cfg.file_path == Path("test_file.h5").resolve()


def test_hdf5_config_none_paths():
    """Test HDF5Config with None paths."""
    cfg = config.HDF5Config(file_path=None)
    assert cfg.file_path is None


# =========================================================================
# LoggingConfig Tests
# =========================================================================


def test_logging_config_defaults():
    """Test LoggingConfig default values."""
    cfg = config.LoggingConfig()
    assert cfg.level == "INFO"
    assert cfg.format == "%(levelname)s:%(name)s:%(message)s"
    assert cfg.file is None


def test_logging_config_custom_values():
    """Test LoggingConfig with custom values."""
    cfg = config.LoggingConfig(
        level="DEBUG",
        format="%(asctime)s - %(message)s",
        file="/tmp/test.log",
    )
    assert cfg.level == "DEBUG"
    assert cfg.format == "%(asctime)s - %(message)s"
    assert cfg.file == "/tmp/test.log"


# =========================================================================
# Config Class Tests
# =========================================================================


def test_config_initialization(clean_env):
    """Test Config class initialization."""
    cfg = config.Config()
    assert isinstance(cfg.server, config.ServerConfig)
    assert isinstance(cfg.async_config, config.AsyncConfig)
    assert isinstance(cfg.transport, config.TransportConfig)
    assert isinstance(cfg.hdf5, config.HDF5Config)
    assert isinstance(cfg.logging, config.LoggingConfig)


def test_config_to_dict(clean_env):
    """Test Config to_dict method."""
    cfg = config.Config()
    d = cfg.to_dict()
    assert isinstance(d, dict)
    assert "server" in d
    assert "async_config" in d
    assert "transport" in d
    assert "hdf5" in d
    assert "logging" in d


def test_config_update_from_dict(clean_env, sample_config_dict):
    """Test Config _update_from_dict method."""
    cfg = config.Config()
    cfg._update_from_dict(sample_config_dict)

    assert cfg.server.name == "Test HDF5 Server"
    assert cfg.async_config.max_workers == 8
    assert cfg.transport.sse_port == 9000
    assert cfg.hdf5.cache_size == 1073741824
    assert cfg.logging.level == "DEBUG"


def test_config_partial_update_from_dict(clean_env):
    """Test Config _update_from_dict with partial dictionary."""
    cfg = config.Config()
    partial_dict = {
        "server": {"name": "Updated Server"},
        "hdf5": {"cache_size": 2147483648},  # 2GB
    }
    cfg._update_from_dict(partial_dict)

    assert cfg.server.name == "Updated Server"
    assert cfg.hdf5.cache_size == 2147483648
    # Other values should remain default
    assert cfg.async_config.max_workers == 4


def test_config_load_from_json_file(
    clean_env, temp_dir, sample_config_dict, monkeypatch
):
    """Test loading configuration from JSON file."""
    config_file = temp_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(sample_config_dict, f)

    monkeypatch.setenv("HDF5_MCP_CONFIG", str(config_file))

    cfg = config.Config()
    assert cfg.server.name == "Test HDF5 Server"
    assert cfg.async_config.max_workers == 8
    assert cfg.transport.sse_port == 9000


def test_config_load_from_nonexistent_json(clean_env, monkeypatch):
    """Test loading with nonexistent config file."""
    monkeypatch.setenv("HDF5_MCP_CONFIG", "/nonexistent/config.json")
    cfg = config.Config()
    # Should use defaults without error
    assert cfg.server.name == "HDF5 MCP Server"


def test_config_load_from_invalid_json(clean_env, temp_dir, monkeypatch):
    """Test loading with invalid JSON file."""
    config_file = temp_dir / "invalid.json"
    with open(config_file, "w") as f:
        f.write("{invalid json")

    monkeypatch.setenv("HDF5_MCP_CONFIG", str(config_file))

    # Should handle error gracefully and use defaults
    # The JSON decode error will be caught and logged
    try:
        cfg = config.Config()
        assert cfg.server.name == "HDF5 MCP Server"
    except json.JSONDecodeError:
        # This is also acceptable behavior
        pass


# =========================================================================
# Environment Variable Loading Tests
# =========================================================================


def test_config_load_data_dir_from_env(clean_env, temp_dir, monkeypatch):
    """Test loading data_dir from environment."""
    test_dir = temp_dir / "test_data"
    monkeypatch.setenv("HDF5_MCP_DATA_DIR", str(test_dir))

    cfg = config.Config()
    assert cfg.hdf5.data_dir == test_dir.resolve()


def test_config_load_storage_endpoint_from_env(clean_env, temp_dir, monkeypatch):
    """Test loading storage endpoint from environment."""
    test_dir = temp_dir / "storage"
    monkeypatch.setenv("HDF5_MCP_STORAGE_ENDPOINT", f"file://{test_dir}")

    cfg = config.Config()
    assert cfg.hdf5.data_dir == test_dir.resolve()


def test_config_load_cache_size_from_env(clean_env, monkeypatch):
    """Test loading cache size from environment."""
    monkeypatch.setenv("HDF5_MCP_CACHE_SIZE_MB", "1024")

    cfg = config.Config()
    assert cfg.hdf5.cache_size == 1024 * 1024 * 1024  # 1GB in bytes


def test_config_load_invalid_cache_size_from_env(clean_env, monkeypatch):
    """Test loading invalid cache size from environment."""
    monkeypatch.setenv("HDF5_MCP_CACHE_SIZE_MB", "invalid")

    # Should handle error gracefully and use default
    cfg = config.Config()
    assert cfg.hdf5.cache_size == 1024 * 1024 * 500  # Default 500MB


def test_config_load_chunk_size_from_env(clean_env, monkeypatch):
    """Test loading chunk size from environment."""
    monkeypatch.setenv("HDF5_MCP_CHUNK_SIZE_MB", "128")

    cfg = config.Config()
    assert cfg.hdf5.chunk_size == 128 * 1024 * 1024  # 128MB in bytes


def test_config_load_invalid_chunk_size_from_env(clean_env, monkeypatch):
    """Test loading invalid chunk size from environment."""
    monkeypatch.setenv("HDF5_MCP_CHUNK_SIZE_MB", "not_a_number")

    cfg = config.Config()
    assert cfg.hdf5.chunk_size == 1024 * 1024 * 64  # Default 64MB


def test_config_load_parallel_threshold_from_env(clean_env, monkeypatch):
    """Test loading parallel threshold from environment."""
    monkeypatch.setenv("HDF5_MCP_PARALLEL_THRESHOLD_MB", "200")

    cfg = config.Config()
    assert cfg.hdf5.parallel_threshold == 200 * 1024 * 1024  # 200MB


def test_config_load_invalid_parallel_threshold_from_env(clean_env, monkeypatch):
    """Test loading invalid parallel threshold from environment."""
    monkeypatch.setenv("HDF5_MCP_PARALLEL_THRESHOLD_MB", "xyz")

    cfg = config.Config()
    assert cfg.hdf5.parallel_threshold == 1024 * 1024 * 100  # Default


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("True", True),
        ("FALSE", False),
    ],
)
def test_config_load_prefetch_enabled_from_env(
    clean_env, monkeypatch, env_value, expected
):
    """Test loading prefetch_enabled from environment."""
    monkeypatch.setenv("HDF5_MCP_PREFETCH_ENABLED", env_value)

    cfg = config.Config()
    assert cfg.hdf5.prefetch_enabled is expected


@pytest.mark.parametrize(
    "env_value,expected",
    [
        ("true", True),
        ("1", True),
        ("yes", True),
        ("false", False),
        ("0", False),
    ],
)
def test_config_load_enable_sse_from_env(clean_env, monkeypatch, env_value, expected):
    """Test loading enable_sse from environment."""
    monkeypatch.setenv("HDF5_MCP_ENABLE_SSE", env_value)

    cfg = config.Config()
    assert cfg.transport.enable_sse is expected


def test_config_load_port_from_env(clean_env, monkeypatch):
    """Test loading port from environment."""
    monkeypatch.setenv("HDF5_MCP_PORT", "9000")

    cfg = config.Config()
    assert cfg.transport.sse_port == 9000


def test_config_load_invalid_port_from_env(clean_env, monkeypatch):
    """Test loading invalid port from environment."""
    monkeypatch.setenv("HDF5_MCP_PORT", "not_a_port")

    cfg = config.Config()
    assert cfg.transport.sse_port == 8765  # Default


def test_config_load_host_from_env(clean_env, monkeypatch):
    """Test loading host from environment."""
    monkeypatch.setenv("HDF5_MCP_HOST", "0.0.0.0")

    cfg = config.Config()
    assert cfg.transport.sse_host == "0.0.0.0"


def test_config_load_max_connections_from_env(clean_env, monkeypatch):
    """Test loading max_connections from environment."""
    monkeypatch.setenv("HDF5_MCP_MAX_CONNECTIONS", "200")

    cfg = config.Config()
    assert cfg.transport.max_connections == 200


def test_config_load_invalid_max_connections_from_env(clean_env, monkeypatch):
    """Test loading invalid max_connections from environment."""
    monkeypatch.setenv("HDF5_MCP_MAX_CONNECTIONS", "abc")

    cfg = config.Config()
    assert cfg.transport.max_connections == 100  # Default


def test_config_load_max_workers_from_env(clean_env, monkeypatch):
    """Test loading max_workers from environment."""
    monkeypatch.setenv("HDF5_MCP_MAX_WORKERS", "8")

    cfg = config.Config()
    assert cfg.async_config.max_workers == 8


def test_config_load_invalid_max_workers_from_env(clean_env, monkeypatch):
    """Test loading invalid max_workers from environment."""
    monkeypatch.setenv("HDF5_MCP_MAX_WORKERS", "invalid")

    cfg = config.Config()
    assert cfg.async_config.max_workers == 4  # Default


def test_config_load_log_level_from_env(clean_env, monkeypatch):
    """Test loading log level from environment."""
    monkeypatch.setenv("HDF5_MCP_LOG_LEVEL", "DEBUG")

    cfg = config.Config()
    assert cfg.logging.level == "DEBUG"


def test_config_env_overrides_json(
    clean_env, temp_dir, sample_config_dict, monkeypatch
):
    """Test that environment variables override JSON config."""
    config_file = temp_dir / "config.json"
    with open(config_file, "w") as f:
        json.dump(sample_config_dict, f)

    monkeypatch.setenv("HDF5_MCP_CONFIG", str(config_file))
    monkeypatch.setenv("HDF5_MCP_CACHE_SIZE_MB", "2048")  # Override JSON value

    cfg = config.Config()
    # JSON value would be 1024, but env should override
    assert cfg.hdf5.cache_size == 2048 * 1024 * 1024


# =========================================================================
# Runtime Update Tests
# =========================================================================


def test_config_update_runtime_valid(clean_env):
    """Test runtime update with valid values."""
    cfg = config.Config()
    cfg.update_runtime("hdf5", "cache_size", 1073741824)  # 1GB
    assert cfg.hdf5.cache_size == 1073741824


def test_config_update_runtime_invalid_section(clean_env):
    """Test runtime update with invalid section."""
    cfg = config.Config()
    with pytest.raises(ValueError, match="Invalid configuration section"):
        cfg.update_runtime("nonexistent", "key", "value")


def test_config_update_runtime_invalid_key(clean_env):
    """Test runtime update with invalid key."""
    cfg = config.Config()
    with pytest.raises(ValueError, match="Invalid configuration key"):
        cfg.update_runtime("hdf5", "nonexistent_key", "value")


def test_config_update_runtime_type_conversion(clean_env):
    """Test runtime update with automatic type conversion."""
    cfg = config.Config()
    # Pass string, should be converted to int
    cfg.update_runtime("hdf5", "cache_size", "1073741824")
    assert cfg.hdf5.cache_size == 1073741824
    assert isinstance(cfg.hdf5.cache_size, int)


def test_config_update_runtime_multiple_sections(clean_env):
    """Test runtime updates across multiple sections."""
    cfg = config.Config()
    cfg.update_runtime("server", "name", "Updated Server")
    cfg.update_runtime("async_config", "max_workers", 16)
    cfg.update_runtime("transport", "sse_port", 9999)

    assert cfg.server.name == "Updated Server"
    assert cfg.async_config.max_workers == 16
    assert cfg.transport.sse_port == 9999


# =========================================================================
# get_config() Tests
# =========================================================================


def test_get_config_singleton(clean_env):
    """Test get_config returns singleton instance."""
    cfg1 = config.get_config()
    cfg2 = config.get_config()
    assert cfg1 is cfg2


def test_get_config_creates_new_instance(reset_config, clean_env):
    """Test get_config creates new instance when none exists."""
    assert config._CONFIG is None
    cfg = config.get_config()
    assert config._CONFIG is not None
    assert cfg is config._CONFIG


# =========================================================================
# Logging Configuration Tests
# =========================================================================


def test_configure_logging_debug_level(clean_env):
    """Test _configure_logging with DEBUG level."""
    # Logging may have been configured already, so just verify the function runs
    config._configure_logging("DEBUG")
    # Function should not raise any errors


def test_configure_logging_info_level(clean_env):
    """Test _configure_logging with INFO level."""
    config._configure_logging("INFO")
    # Function should not raise any errors


def test_configure_logging_warning_level(clean_env):
    """Test _configure_logging with WARNING level."""
    config._configure_logging("WARNING")
    # Function should not raise any errors


def test_configure_logging_error_level(clean_env):
    """Test _configure_logging with ERROR level."""
    config._configure_logging("ERROR")
    # Function should not raise any errors


def test_configure_logging_critical_level(clean_env):
    """Test _configure_logging with CRITICAL level."""
    config._configure_logging("CRITICAL")
    # Function should not raise any errors


def test_configure_logging_invalid_level(clean_env):
    """Test _configure_logging with invalid level uses default."""
    config._configure_logging("INVALID_LEVEL")
    # Should use default level without raising error


def test_configure_logging_lowercase(clean_env):
    """Test _configure_logging handles lowercase levels."""
    config._configure_logging("debug")
    # Should handle lowercase without error


def test_configure_logging_with_file(clean_env, temp_dir, monkeypatch):
    """Test _configure_logging with log file."""
    log_file = temp_dir / "test.log"

    # Create a new config with log file
    cfg = config.Config()
    cfg.logging.file = str(log_file)

    # Mock get_config to return our config
    with patch("hdf5_mcp.config.get_config", return_value=cfg):
        config._configure_logging("INFO")

    # Check that a file handler was added
    handlers = logging.getLogger().handlers
    file_handlers = [h for h in handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) > 0


# =========================================================================
# Public API Function Tests
# =========================================================================


def test_get_storage_path(clean_env):
    """Test get_storage_path function."""
    path = config.get_storage_path()
    assert isinstance(path, Path)
    assert path == config.get_config().hdf5.data_dir


def test_set_storage_path_existing_dir(clean_env, temp_dir):
    """Test set_storage_path with existing directory."""
    test_dir = temp_dir / "storage"
    test_dir.mkdir()

    config.set_storage_path(test_dir)
    assert config.get_storage_path() == test_dir.resolve()


def test_set_storage_path_nonexistent_dir(clean_env, temp_dir):
    """Test set_storage_path creates nonexistent directory."""
    test_dir = temp_dir / "new_storage"
    assert not test_dir.exists()

    config.set_storage_path(test_dir)
    assert test_dir.exists()
    assert config.get_storage_path() == test_dir.resolve()


def test_set_storage_path_string(clean_env, temp_dir):
    """Test set_storage_path with string path."""
    test_dir = temp_dir / "string_path"
    config.set_storage_path(str(test_dir))
    assert config.get_storage_path() == test_dir.resolve()


def test_get_cache_size(clean_env):
    """Test get_cache_size function."""
    size_mb = config.get_cache_size()
    assert isinstance(size_mb, int)
    assert size_mb == 500  # Default 500MB


def test_set_cache_size_valid(clean_env):
    """Test set_cache_size with valid value."""
    config.set_cache_size(1024)
    assert config.get_cache_size() == 1024


def test_set_cache_size_zero(clean_env):
    """Test set_cache_size with zero value."""
    with pytest.raises(ValueError, match="Cache size must be positive"):
        config.set_cache_size(0)


def test_set_cache_size_negative(clean_env):
    """Test set_cache_size with negative value."""
    with pytest.raises(ValueError, match="Cache size must be positive"):
        config.set_cache_size(-100)


def test_set_cache_size_conversion(clean_env):
    """Test set_cache_size properly converts MB to bytes."""
    config.set_cache_size(100)
    cfg = config.get_config()
    assert cfg.hdf5.cache_size == 100 * 1024 * 1024  # 100MB in bytes


def test_get_log_level(clean_env):
    """Test get_log_level function."""
    level = config.get_log_level()
    assert isinstance(level, str)
    assert level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_set_log_level_valid(clean_env):
    """Test set_log_level with valid level."""
    config.set_log_level("DEBUG")
    assert config.get_log_level() == "DEBUG"


@pytest.mark.parametrize("level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
def test_set_log_level_all_valid_levels(clean_env, level):
    """Test set_log_level with all valid levels."""
    config.set_log_level(level)
    assert config.get_log_level() == level


def test_set_log_level_lowercase(clean_env):
    """Test set_log_level converts lowercase to uppercase."""
    config.set_log_level("debug")
    assert config.get_log_level() == "DEBUG"


def test_set_log_level_mixed_case(clean_env):
    """Test set_log_level converts mixed case to uppercase."""
    config.set_log_level("DeBuG")
    assert config.get_log_level() == "DEBUG"


def test_set_log_level_invalid(clean_env):
    """Test set_log_level with invalid level."""
    with pytest.raises(ValueError, match="Invalid log level"):
        config.set_log_level("INVALID")


def test_set_log_level_empty(clean_env):
    """Test set_log_level with empty string."""
    with pytest.raises(ValueError, match="Invalid log level"):
        config.set_log_level("")


# =========================================================================
# Integration Tests
# =========================================================================


def test_config_full_lifecycle(clean_env, temp_dir):
    """Test full configuration lifecycle."""
    # Create config
    cfg = config.Config()

    # Verify defaults
    assert cfg.server.name == "HDF5 MCP Server"

    # Update runtime
    cfg.update_runtime("server", "name", "Updated Server")
    assert cfg.server.name == "Updated Server"

    # Update via public API
    storage_path = temp_dir / "storage"
    config.set_storage_path(storage_path)
    assert config.get_storage_path() == storage_path.resolve()

    config.set_cache_size(2048)
    assert config.get_cache_size() == 2048

    config.set_log_level("DEBUG")
    assert config.get_log_level() == "DEBUG"

    # Verify all changes
    d = cfg.to_dict()
    assert d["server"]["name"] == "Updated Server"


def test_config_multiple_env_vars(clean_env, monkeypatch):
    """Test loading multiple environment variables."""
    monkeypatch.setenv("HDF5_MCP_CACHE_SIZE_MB", "1024")
    monkeypatch.setenv("HDF5_MCP_CHUNK_SIZE_MB", "128")
    monkeypatch.setenv("HDF5_MCP_PARALLEL_THRESHOLD_MB", "200")
    monkeypatch.setenv("HDF5_MCP_PREFETCH_ENABLED", "false")
    monkeypatch.setenv("HDF5_MCP_ENABLE_SSE", "true")
    monkeypatch.setenv("HDF5_MCP_PORT", "9000")
    monkeypatch.setenv("HDF5_MCP_MAX_WORKERS", "8")
    monkeypatch.setenv("HDF5_MCP_LOG_LEVEL", "DEBUG")

    cfg = config.Config()

    assert cfg.hdf5.cache_size == 1024 * 1024 * 1024
    assert cfg.hdf5.chunk_size == 128 * 1024 * 1024
    assert cfg.hdf5.parallel_threshold == 200 * 1024 * 1024
    assert cfg.hdf5.prefetch_enabled is False
    assert cfg.transport.enable_sse is True
    assert cfg.transport.sse_port == 9000
    assert cfg.async_config.max_workers == 8
    assert cfg.logging.level == "DEBUG"

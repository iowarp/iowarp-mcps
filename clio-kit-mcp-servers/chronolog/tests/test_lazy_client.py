"""Tests for metadata-safe lazy ChronoLog native-client loading."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastmcp.exceptions import ToolError

from chronomcp import server
from chronomcp.utils import config


def test_server_metadata_import_does_not_require_native_client() -> None:
    """FastMCP metadata remains available without the site native extension."""
    assert server.mcp.name == "chronolog"
    assert config.client is None


def test_get_client_reports_missing_native_dependency() -> None:
    """The first connection call fails explicitly when the native client is absent."""
    config.client = None
    with (
        patch.object(
            config.importlib,
            "import_module",
            side_effect=ModuleNotFoundError("py_chronolog_client"),
        ),
        pytest.raises(ToolError, match="ChronoLog native client is unavailable"),
    ):
        config.get_client()


def test_get_client_constructs_and_reuses_native_client() -> None:
    """The native client is initialized once from the configured endpoint."""
    created_client = Mock()
    client_type = Mock(return_value=created_client)
    config_type = Mock(return_value=object())
    native = SimpleNamespace(
        ClientPortalServiceConf=config_type,
        Client=client_type,
    )
    config.client = None
    try:
        with patch.object(
            config.importlib, "import_module", return_value=native
        ) as load:
            first = config.get_client()
            second = config.get_client()
        assert first is created_client
        assert second is created_client
        load.assert_called_once_with("py_chronolog_client")
        config_type.assert_called_once_with(
            config.CHRONO_PROTOCOL,
            config.CHRONO_HOST,
            config.CHRONO_PORT,
            config.CHRONO_TIMEOUT,
        )
        client_type.assert_called_once_with(config_type.return_value)
    finally:
        config.client = None

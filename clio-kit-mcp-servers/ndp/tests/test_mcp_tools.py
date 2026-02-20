"""Tests for MCP integration and basic functionality."""

from ndp_mcp import server
from ndp_mcp.server import Dataset


class TestServerBasics:
    """Test basic server functionality."""

    def test_server_name(self):
        """Test that the server has the correct name."""
        assert server.mcp.name == "ndp"

    def test_dataset_model_validation(self):
        """Test Dataset pydantic model validation."""
        dataset_data = {
            "id": "test-id",
            "name": "test_dataset",
            "title": "Test Dataset",
            "owner_org": "test_org",
            "resources": [{"id": "res-1", "name": "Resource 1"}],
        }

        dataset = Dataset(**dataset_data)
        assert dataset.id == "test-id"
        assert dataset.name == "test_dataset"
        assert dataset.title == "Test Dataset"
        assert dataset.owner_org == "test_org"
        assert len(dataset.resources) == 1

    def test_ndp_client_initialization(self):
        """Test that NDPClient is properly initialized."""
        assert server.ndp_client is not None
        assert server.ndp_client.base_url == "http://155.101.6.191:8003"
        assert server.ndp_client.max_retries == 3

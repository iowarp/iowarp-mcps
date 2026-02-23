"""Tests for NDP MCP server."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ndp_mcp.server import Dataset, NDPClient, mcp


class TestNDPClient:
    """Test the NDPClient class."""

    @pytest.fixture
    def client(self):
        """Create a test NDPClient instance."""
        return NDPClient("http://test.example.com")

    @pytest.mark.asyncio
    async def test_client_initialization(self, client):
        """Test NDPClient proper initialization."""
        assert client.base_url == "http://test.example.com"
        assert client.max_retries == 3
        assert client.retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_make_request_success(self, client):
        """Test successful HTTP request."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": True}
        mock_response.raise_for_status.return_value = None

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await client._make_request("GET", "/test")
            assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_make_request_retry_on_timeout(self, client):
        """Test retry logic on timeout."""
        with patch("httpx.AsyncClient") as mock_client:
            # First call times out, second succeeds
            mock_response = MagicMock()
            mock_response.json.return_value = {"success": True}
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.side_effect = [
                Exception("Timeout"),
                mock_response,
            ]

            with patch("asyncio.sleep", new=AsyncMock()):
                result = await client._make_request("GET", "/test")
                assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_list_organizations(self, client):
        """Test list_organizations method."""
        mock_orgs = ["org1", "org2", "org3"]

        with patch.object(client, "_make_request", new=AsyncMock(return_value=mock_orgs)):
            result = await client.list_organizations(name_filter="test", server="global")
            assert result == mock_orgs

    @pytest.mark.asyncio
    async def test_search_datasets_simple(self, client):
        """Test simple dataset search."""
        mock_datasets = [
            {
                "id": "1",
                "name": "test_dataset",
                "title": "Test Dataset",
                "resources": [],
            }
        ]

        with patch.object(client, "_make_request", new=AsyncMock(return_value=mock_datasets)):
            result = await client.search_datasets_simple(["climate"], server="global")
            assert len(result) == 1
            assert isinstance(result[0], Dataset)
            assert result[0].name == "test_dataset"

    @pytest.mark.asyncio
    async def test_search_datasets_advanced(self, client):
        """Test advanced dataset search."""
        mock_datasets = [
            {
                "id": "1",
                "name": "climate_data",
                "title": "Climate Dataset",
                "owner_org": "noaa",
                "resources": [],
            }
        ]

        with patch.object(client, "_make_request", new=AsyncMock(return_value=mock_datasets)):
            result = await client.search_datasets_advanced(
                dataset_name="climate_data", owner_org="noaa", server="global"
            )
            assert len(result) == 1
            assert isinstance(result[0], Dataset)
            assert result[0].owner_org == "noaa"


class TestServerBasics:
    """Test basic server functionality."""

    def test_server_name(self):
        """Test that the server has the correct name."""
        assert mcp.name == "ndp"

    def test_dataset_model(self):
        """Test Dataset pydantic model."""
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

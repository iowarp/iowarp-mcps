"""Tests specifically for the NDPClient class."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ndp_mcp.server import Dataset, NDPClient


class TestNDPClientEdgeCases:
    """Test edge cases and error conditions for NDPClient."""

    @pytest.fixture
    def client(self):
        """Create a test NDPClient instance."""
        return NDPClient("http://test.example.com:8003")

    def test_client_base_url_cleanup(self):
        """Test that trailing slashes are removed from base URL."""
        client = NDPClient("http://test.example.com/")
        assert client.base_url == "http://test.example.com"

        client = NDPClient("http://test.example.com///")
        assert client.base_url == "http://test.example.com"

    @pytest.mark.asyncio
    async def test_make_request_unsupported_method(self, client):
        """Test error handling for unsupported HTTP methods."""
        with pytest.raises(Exception) as exc_info:
            await client._make_request("DELETE", "/test")

        assert "Unsupported HTTP method: DELETE" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_max_retries_exceeded(self, client):
        """Test behavior when max retries is exceeded."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = Exception(
                "Connection failed"
            )

            with patch("asyncio.sleep", new=AsyncMock()):
                with pytest.raises(Exception) as exc_info:
                    await client._make_request("GET", "/test")

                assert "Request failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_http_status_error_retry(self, client):
        """Test retry behavior on HTTP 500+ errors."""
        with patch("httpx.AsyncClient") as mock_client:
            # First call returns 500 error, second call succeeds
            mock_response_error = MagicMock()
            mock_response_error.status_code = 500
            mock_response_error.text = "Internal Server Error"

            mock_response_success = MagicMock()
            mock_response_success.json.return_value = {"success": True}
            mock_response_success.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.side_effect = [
                httpx.HTTPStatusError(
                    "500 Error", request=MagicMock(), response=mock_response_error
                ),
                mock_response_success,
            ]

            with patch("asyncio.sleep", new=AsyncMock()):
                result = await client._make_request("GET", "/test")
                assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_make_request_http_status_error_no_retry(self, client):
        """Test no retry on HTTP 4xx errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response_error = MagicMock()
            mock_response_error.status_code = 404
            mock_response_error.text = "Not Found"

            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.HTTPStatusError(
                    "404 Error", request=MagicMock(), response=mock_response_error
                )
            )

            with pytest.raises(Exception) as exc_info:
                await client._make_request("GET", "/test")

            assert "HTTP 404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_timeout_all_retries(self, client):
        """Test timeout on all retry attempts."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                httpx.TimeoutException("Timeout")
            )

            with patch("asyncio.sleep", new=AsyncMock()):
                with pytest.raises(Exception) as exc_info:
                    await client._make_request("GET", "/test")

                assert "Request timed out after 3 attempts" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_post_with_json(self, client):
        """Test POST request with JSON data."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"result": "created"}
        mock_response.raise_for_status.return_value = None

        test_data = {"name": "test", "value": 123}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await client._make_request("POST", "/test", json_data=test_data)
            assert result == {"result": "created"}

            # Verify the POST was called with correct parameters
            mock_client.return_value.__aenter__.return_value.post.assert_called_once_with(
                "http://test.example.com:8003/test", params=None, json=test_data
            )

    @pytest.mark.asyncio
    async def test_list_organizations_empty_result(self, client):
        """Test list_organizations with empty result."""
        with patch.object(client, "_make_request", new=AsyncMock(return_value=[])):
            result = await client.list_organizations()
            assert result == []

    @pytest.mark.asyncio
    async def test_list_organizations_non_list_result(self, client):
        """Test list_organizations with non-list response."""
        with patch.object(
            client, "_make_request", new=AsyncMock(return_value={"error": "Invalid"})
        ):
            result = await client.list_organizations()
            assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_simple_with_keys(self, client):
        """Test simple search with both terms and keys."""
        mock_datasets = [
            {
                "id": "1",
                "name": "test_dataset",
                "title": "Test Dataset",
                "resources": [],
            }
        ]

        with patch.object(
            client, "_make_request", new=AsyncMock(return_value=mock_datasets)
        ) as mock_request:
            result = await client.search_datasets_simple(
                terms=["climate", "temperature"],
                keys=["title", "description"],
                server="global",
            )

            # Verify the request was made with correct parameters
            call_args = mock_request.call_args
            assert call_args[0] == ("GET", "/search")
            params = call_args[1]["params"]
            assert params["server"] == "global"
            # Check that terms and keys were added
            assert "terms" in params
            assert "keys" in params

            assert len(result) == 1
            assert isinstance(result[0], Dataset)

    @pytest.mark.asyncio
    async def test_search_datasets_simple_empty_result(self, client):
        """Test simple search with empty result."""
        with patch.object(client, "_make_request", new=AsyncMock(return_value=[])):
            result = await client.search_datasets_simple(["test"])
            assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_simple_non_list_result(self, client):
        """Test simple search with non-list response."""
        with patch.object(
            client, "_make_request", new=AsyncMock(return_value={"error": "Invalid"})
        ):
            result = await client.search_datasets_simple(["test"])
            assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_all_params(self, client):
        """Test advanced search with all parameters."""
        mock_datasets = [
            {
                "id": "1",
                "name": "comprehensive_dataset",
                "title": "Comprehensive Dataset",
                "owner_org": "test_org",
                "notes": "Test description",
                "resources": [
                    {
                        "id": "res-1",
                        "name": "Test Resource",
                        "description": "Resource description",
                        "format": "CSV",
                        "url": "http://example.com/data.csv",
                    }
                ],
            }
        ]

        with patch.object(
            client, "_make_request", new=AsyncMock(return_value=mock_datasets)
        ) as mock_request:
            result = await client.search_datasets_advanced(
                dataset_name="comprehensive_dataset",
                dataset_title="Comprehensive Dataset",
                owner_org="test_org",
                resource_url="http://example.com/data.csv",
                resource_name="Test Resource",
                dataset_description="Test description",
                resource_description="Resource description",
                resource_format="CSV",
                search_term="comprehensive,test",
                filter_list=["type:dataset", "format:csv"],
                timestamp="2024-01-01",
                server="local",
            )

            # Verify the request was made with correct data
            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "/search")
            json_data = call_args[1]["json_data"]

            # Check all parameters were included
            assert json_data["dataset_name"] == "comprehensive_dataset"
            assert json_data["dataset_title"] == "Comprehensive Dataset"
            assert json_data["owner_org"] == "test_org"
            assert json_data["resource_url"] == "http://example.com/data.csv"
            assert json_data["resource_name"] == "Test Resource"
            assert json_data["dataset_description"] == "Test description"
            assert json_data["resource_description"] == "Resource description"
            assert json_data["resource_format"] == "CSV"
            assert json_data["search_term"] == "comprehensive,test"
            assert json_data["filter_list"] == ["type:dataset", "format:csv"]
            assert json_data["timestamp"] == "2024-01-01"
            assert json_data["server"] == "local"

            assert len(result) == 1
            assert isinstance(result[0], Dataset)
            assert result[0].name == "comprehensive_dataset"

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_minimal_params(self, client):
        """Test advanced search with minimal parameters."""
        mock_datasets = []

        with patch.object(
            client, "_make_request", new=AsyncMock(return_value=mock_datasets)
        ) as mock_request:
            result = await client.search_datasets_advanced(server="global")

            # Verify only server was included in the request
            call_args = mock_request.call_args
            json_data = call_args[1]["json_data"]
            assert json_data == {"server": "global"}

            assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_empty_result(self, client):
        """Test advanced search with empty result."""
        with patch.object(client, "_make_request", new=AsyncMock(return_value=[])):
            result = await client.search_datasets_advanced(dataset_name="nonexistent")
            assert result == []

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_non_list_result(self, client):
        """Test advanced search with non-list response."""
        with patch.object(
            client, "_make_request", new=AsyncMock(return_value={"error": "Invalid"})
        ):
            result = await client.search_datasets_advanced(dataset_name="test")
            assert result == []


class TestDatasetModel:
    """Test the Dataset pydantic model."""

    def test_dataset_minimal_required_fields(self):
        """Test Dataset with only required fields."""
        dataset = Dataset(id="test-id", name="test_name", title="Test Title")

        assert dataset.id == "test-id"
        assert dataset.name == "test_name"
        assert dataset.title == "Test Title"
        assert dataset.owner_org is None
        assert dataset.notes is None
        assert dataset.resources == []
        assert dataset.extras is None

    def test_dataset_full_fields(self, sample_dataset_data):
        """Test Dataset with all fields populated."""
        dataset = Dataset(**sample_dataset_data)

        assert dataset.id == sample_dataset_data["id"]
        assert dataset.name == sample_dataset_data["name"]
        assert dataset.title == sample_dataset_data["title"]
        assert dataset.owner_org == sample_dataset_data["owner_org"]
        assert dataset.notes == sample_dataset_data["notes"]
        assert len(dataset.resources) == 1
        assert dataset.extras == sample_dataset_data["extras"]

    def test_dataset_model_dump(self, sample_dataset_data):
        """Test Dataset model serialization."""
        dataset = Dataset(**sample_dataset_data)
        dumped = dataset.model_dump()

        # Verify all fields are present in the dump
        for key, value in sample_dataset_data.items():
            assert dumped[key] == value

"""Comprehensive tests for MCP tool handlers to achieve >90% coverage."""

from unittest.mock import AsyncMock, patch

import pytest
from fastmcp.exceptions import ToolError

from ndp_mcp import server
from ndp_mcp.server import Dataset


@pytest.fixture
def list_organizations_fn():
    """Get the list_organizations function."""
    return server.list_organizations


@pytest.fixture
def search_datasets_fn():
    """Get the search_datasets function."""
    return server.search_datasets


@pytest.fixture
def get_dataset_details_fn():
    """Get the get_dataset_details function."""
    return server.get_dataset_details


class TestListOrganizationsTool:
    """Test the list_organizations MCP tool handler."""

    @pytest.mark.asyncio
    async def test_list_organizations_success(self, list_organizations_fn):
        """Test successful organization listing."""
        mock_orgs = ["nasa", "noaa", "usgs"]

        with patch(
            "ndp_mcp.server.ndp_client.list_organizations", new=AsyncMock(return_value=mock_orgs)
        ):
            result = await list_organizations_fn(name_filter="n", server="global")

            assert result["organizations"] == mock_orgs
            assert result["count"] == 3
            assert result["server"] == "global"
            assert result["name_filter"] == "n"
            assert result["_meta"]["tool"] == "list_organizations"
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_organizations_no_filter(self, list_organizations_fn):
        """Test organization listing without filter."""
        mock_orgs = ["nasa", "noaa", "usgs", "epa"]

        with patch(
            "ndp_mcp.server.ndp_client.list_organizations", new=AsyncMock(return_value=mock_orgs)
        ):
            result = await list_organizations_fn(server="local")

            assert result["organizations"] == mock_orgs
            assert result["count"] == 4
            assert result["server"] == "local"
            assert result["name_filter"] is None
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_organizations_empty_result(self, list_organizations_fn):
        """Test organization listing with empty result."""
        with patch("ndp_mcp.server.ndp_client.list_organizations", new=AsyncMock(return_value=[])):
            result = await list_organizations_fn(name_filter="nonexistent")

            assert result["organizations"] == []
            assert result["count"] == 0
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_organizations_exception_handling(self, list_organizations_fn):
        """Test exception handling in list_organizations tool."""
        error_msg = "Network connection failed"

        with patch(
            "ndp_mcp.server.ndp_client.list_organizations",
            new=AsyncMock(side_effect=Exception(error_msg)),
        ):
            with pytest.raises(ToolError, match=error_msg):
                await list_organizations_fn()

    @pytest.mark.asyncio
    async def test_list_organizations_connection_error(self, list_organizations_fn):
        """Test connection error handling in list_organizations."""
        with patch(
            "ndp_mcp.server.ndp_client.list_organizations",
            new=AsyncMock(side_effect=ConnectionError("Connection refused")),
        ):
            with pytest.raises(ToolError, match="Connection refused"):
                await list_organizations_fn()

    @pytest.mark.asyncio
    async def test_list_organizations_timeout_error(self, list_organizations_fn):
        """Test timeout error handling in list_organizations."""
        with patch(
            "ndp_mcp.server.ndp_client.list_organizations",
            new=AsyncMock(side_effect=TimeoutError("Request timed out")),
        ):
            with pytest.raises(ToolError, match="Request timed out"):
                await list_organizations_fn()


class TestSearchDatasetsTool:
    """Test the search_datasets MCP tool handler."""

    @pytest.mark.asyncio
    async def test_search_datasets_simple_search(self, search_datasets_fn):
        """Test simple search with terms."""
        mock_datasets = [
            Dataset(id="1", name="climate_data", title="Climate Data"),
            Dataset(id="2", name="weather_data", title="Weather Data"),
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(
                search_terms=["climate", "weather"],
                search_keys=["title", "description"],
                server="global",
            )

            assert result["count"] == 2
            assert result["server"] == "global"
            assert result["_meta"]["status"] == "success"
            assert len(result["datasets"]) == 2
            assert result["datasets"][0]["name"] == "climate_data"

    @pytest.mark.asyncio
    async def test_search_datasets_simple_without_keys(self, search_datasets_fn):
        """Test simple search without keys."""
        mock_datasets = [
            Dataset(id="1", name="test_data", title="Test Data"),
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"])

            assert result["count"] == 1
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_search(self, search_datasets_fn):
        """Test advanced search with field-specific parameters."""
        mock_datasets = [
            Dataset(id="1", name="nasa_climate", title="NASA Climate Data", owner_org="nasa"),
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(
                dataset_name="nasa_climate",
                owner_org="nasa",
                resource_format="NetCDF",
                server="global",
            )

            assert result["count"] == 1
            assert result["server"] == "global"
            assert result["search_parameters"]["dataset_name"] == "nasa_climate"
            assert result["search_parameters"]["owner_org"] == "nasa"
            assert result["search_parameters"]["resource_format"] == "NetCDF"
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_all_fields(self, search_datasets_fn):
        """Test advanced search with all available fields."""
        mock_datasets = []

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(
                dataset_name="test",
                dataset_title="Test Dataset",
                owner_org="test_org",
                resource_url="http://example.com/data",
                resource_name="Test Resource",
                dataset_description="Test description",
                resource_description="Resource desc",
                resource_format="CSV",
                search_term="test,data",
                filter_list=["type:dataset"],
                timestamp="2024-01-01",
                server="local",
            )

            assert result["count"] == 0
            assert result["server"] == "local"
            assert result["search_parameters"]["dataset_name"] == "test"
            assert result["search_parameters"]["dataset_title"] == "Test Dataset"
            assert result["search_parameters"]["owner_org"] == "test_org"
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_datasets_with_limit_int(self, search_datasets_fn):
        """Test search with integer limit parameter."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(50)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"], limit=10)

            assert result["count"] == 10
            assert "50" in str(result["total_found"])
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_search_datasets_with_limit_string(self, search_datasets_fn):
        """Test search with string limit parameter."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(30)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"], limit="5")

            assert result["count"] == 5
            assert "30" in str(result["total_found"])

    @pytest.mark.asyncio
    async def test_search_datasets_with_invalid_limit(self, search_datasets_fn):
        """Test search with invalid limit string."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(30)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"], limit="invalid")

            # Should fall back to default limit of 20
            assert result["count"] == 20

    @pytest.mark.asyncio
    async def test_search_datasets_with_zero_limit(self, search_datasets_fn):
        """Test search with zero or negative limit."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(30)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"], limit=0)

            # Should use default limit of 20
            assert result["count"] == 20

    @pytest.mark.asyncio
    async def test_search_datasets_default_limit(self, search_datasets_fn):
        """Test search with default limit (should be 20)."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(50)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"])

            # Default limit is 20
            assert result["count"] == 20
            assert "20 of 50" == result["total_found"]

    @pytest.mark.asyncio
    async def test_search_datasets_no_limiting_needed(self, search_datasets_fn):
        """Test search when results are under the limit."""
        mock_datasets = [
            Dataset(id=str(i), name=f"dataset_{i}", title=f"Dataset {i}") for i in range(5)
        ]

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(return_value=mock_datasets),
        ):
            result = await search_datasets_fn(search_terms=["test"])

            assert result["count"] == 5
            assert result["total_found"] == 5  # Not a string when not limited

    @pytest.mark.asyncio
    async def test_search_datasets_exception_handling(self, search_datasets_fn):
        """Test exception handling in search_datasets tool."""
        error_msg = "Search service unavailable"

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple",
            new=AsyncMock(side_effect=Exception(error_msg)),
        ):
            with pytest.raises(ToolError, match=error_msg):
                await search_datasets_fn(search_terms=["test"])

    @pytest.mark.asyncio
    async def test_search_datasets_advanced_exception(self, search_datasets_fn):
        """Test exception handling in advanced search."""
        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(side_effect=ValueError("Invalid parameter")),
        ):
            with pytest.raises(ToolError, match="Invalid parameter"):
                await search_datasets_fn(dataset_name="test")

    @pytest.mark.asyncio
    async def test_search_datasets_empty_result(self, search_datasets_fn):
        """Test search with empty result."""
        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_simple", new=AsyncMock(return_value=[])
        ):
            result = await search_datasets_fn(search_terms=["nonexistent"])

            assert result["count"] == 0
            assert result["total_found"] == 0
            assert result["_meta"]["status"] == "success"


class TestGetDatasetDetailsTool:
    """Test the get_dataset_details MCP tool handler."""

    @pytest.mark.asyncio
    async def test_get_dataset_details_by_id(self, get_dataset_details_fn):
        """Test getting dataset details by ID."""
        mock_dataset = Dataset(
            id="test-id-123",
            name="test_dataset",
            title="Test Dataset",
            owner_org="test_org",
            resources=[{"id": "res-1", "name": "Resource 1"}],
        )

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            result = await get_dataset_details_fn(
                dataset_identifier="test-id-123", identifier_type="id", server="global"
            )

            assert result["dataset"]["id"] == "test-id-123"
            assert result["dataset"]["name"] == "test_dataset"
            assert result["identifier_used"]["type"] == "id"
            assert result["identifier_used"]["value"] == "test-id-123"
            assert result["server"] == "global"
            assert result["resource_count"] == 1
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_dataset_details_by_name(self, get_dataset_details_fn):
        """Test getting dataset details by name."""
        mock_dataset = Dataset(
            id="123",
            name="climate_data",
            title="Climate Data",
            owner_org="nasa",
        )

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            result = await get_dataset_details_fn(
                dataset_identifier="climate_data", identifier_type="name", server="local"
            )

            assert result["dataset"]["name"] == "climate_data"
            assert result["identifier_used"]["type"] == "name"
            assert result["identifier_used"]["value"] == "climate_data"
            assert result["server"] == "local"
            assert result["_meta"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_get_dataset_details_not_found_by_id(self, get_dataset_details_fn):
        """Test dataset not found by ID."""
        mock_dataset = Dataset(id="other-id", name="other", title="Other")

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            with pytest.raises(ToolError, match="Dataset not found with id: nonexistent-id"):
                await get_dataset_details_fn(
                    dataset_identifier="nonexistent-id", identifier_type="id"
                )

    @pytest.mark.asyncio
    async def test_get_dataset_details_not_found_by_name(self, get_dataset_details_fn):
        """Test dataset not found by name."""
        mock_dataset = Dataset(id="1", name="other_dataset", title="Other")

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            with pytest.raises(ToolError, match="Dataset not found with name: nonexistent_name"):
                await get_dataset_details_fn(
                    dataset_identifier="nonexistent_name", identifier_type="name"
                )

    @pytest.mark.asyncio
    async def test_get_dataset_details_empty_search_result(self, get_dataset_details_fn):
        """Test when search returns empty results."""
        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced", new=AsyncMock(return_value=[])
        ):
            with pytest.raises(ToolError, match="Dataset not found"):
                await get_dataset_details_fn(dataset_identifier="test-id", identifier_type="id")

    @pytest.mark.asyncio
    async def test_get_dataset_details_multiple_resources(self, get_dataset_details_fn):
        """Test dataset with multiple resources."""
        mock_dataset = Dataset(
            id="test-id",
            name="multi_resource_dataset",
            title="Multi Resource Dataset",
            resources=[
                {"id": "res-1", "name": "Resource 1"},
                {"id": "res-2", "name": "Resource 2"},
                {"id": "res-3", "name": "Resource 3"},
            ],
        )

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            result = await get_dataset_details_fn(
                dataset_identifier="test-id", identifier_type="id"
            )

            assert result["resource_count"] == 3
            assert len(result["dataset"]["resources"]) == 3

    @pytest.mark.asyncio
    async def test_get_dataset_details_no_resources(self, get_dataset_details_fn):
        """Test dataset with no resources."""
        mock_dataset = Dataset(
            id="test-id",
            name="no_resource_dataset",
            title="No Resource Dataset",
        )

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            result = await get_dataset_details_fn(
                dataset_identifier="test-id", identifier_type="id"
            )

            assert result["resource_count"] == 0
            assert result["dataset"]["resources"] == []

    @pytest.mark.asyncio
    async def test_get_dataset_details_exception_handling(self, get_dataset_details_fn):
        """Test exception handling in get_dataset_details tool."""
        error_msg = "Database connection failed"

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(side_effect=Exception(error_msg)),
        ):
            with pytest.raises(ToolError, match=error_msg):
                await get_dataset_details_fn(dataset_identifier="test-id", identifier_type="id")

    @pytest.mark.asyncio
    async def test_get_dataset_details_with_extras(self, get_dataset_details_fn):
        """Test dataset with extras field populated."""
        mock_dataset = Dataset(
            id="test-id",
            name="dataset_with_extras",
            title="Dataset with Extras",
            extras={"metadata_version": "1.0", "custom_field": "value"},
        )

        with patch(
            "ndp_mcp.server.ndp_client.search_datasets_advanced",
            new=AsyncMock(return_value=[mock_dataset]),
        ):
            result = await get_dataset_details_fn(
                dataset_identifier="test-id", identifier_type="id"
            )

            assert result["dataset"]["extras"] is not None
            assert result["dataset"]["extras"]["metadata_version"] == "1.0"
            assert result["_meta"]["status"] == "success"

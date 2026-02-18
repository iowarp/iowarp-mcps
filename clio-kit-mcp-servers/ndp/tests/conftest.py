"""Test configuration and fixtures for NDP MCP server tests."""

import pytest


@pytest.fixture
def sample_dataset_data():
    """Sample dataset data for testing."""
    return {
        "id": "12345678-abcd-efgh-ijkl-1234567890ab",
        "name": "example_dataset_name",
        "title": "Example Dataset Title",
        "owner_org": "example_org_name",
        "notes": "This is an example dataset.",
        "resources": [
            {
                "id": "abcd1234-efgh5678-ijkl9012",
                "url": "http://example.com/resource",
                "name": "Example Resource Name",
                "description": "This is an example resource.",
                "format": "CSV",
            }
        ],
        "extras": {
            "key1": "value1",
            "key2": "value2",
            "mapping": {"field1": "qeadw2", "field2": "gw4aw34", "time": "gw4aw34"},
            "processing": {"data_key": "", "info_key": "key_with_info"},
        },
    }


@pytest.fixture
def sample_organizations():
    """Sample organizations list for testing."""
    return ["nasa", "noaa", "usgs", "epa", "nist"]


@pytest.fixture
def mock_api_responses():
    """Mock API responses for different endpoints."""
    return {
        "organizations": ["nasa", "noaa", "usgs"],
        "search_results": [
            {
                "id": "dataset-1",
                "name": "climate_data",
                "title": "Climate Data",
                "owner_org": "noaa",
                "resources": [],
            },
            {
                "id": "dataset-2",
                "name": "weather_data",
                "title": "Weather Data",
                "owner_org": "noaa",
                "resources": [],
            },
        ],
        "empty_results": [],
    }

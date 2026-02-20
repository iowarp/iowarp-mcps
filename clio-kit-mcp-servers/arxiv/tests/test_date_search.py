"""
Tests for ArXiv date-based search capabilities.
"""

import pytest
from unittest.mock import AsyncMock, patch

from arxiv_mcp.capabilities.date_search import search_date_range


class TestDateSearch:
    """Test date-based search functionality"""

    @pytest.mark.asyncio
    async def test_search_date_range_success(self):
        """Test successful date range search"""
        mock_papers = [
            {
                "id": "http://arxiv.org/abs/2401.12345v1",
                "title": "Test Paper 1",
                "published": "2024-01-15T10:00:00Z",
                "categories": ["cs.AI"],
            },
            {
                "id": "http://arxiv.org/abs/2401.12346v1",
                "title": "Test Paper 2",
                "published": "2024-01-16T10:00:00Z",
                "categories": ["cs.LG"],
            },
        ]

        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = mock_papers

            result = await search_date_range("2024-01-15", "2024-01-16")

            assert result["success"] is True
            assert result["papers"] == mock_papers
            assert result["start_date"] == "2024-01-15"
            assert result["end_date"] == "2024-01-16"
            assert result["category"] == "all"
            assert result["max_results"] == 20
            assert result["returned_results"] == 2
            assert "Successfully found 2 papers" in result["message"]

            # Verify the query was called with correct parameters
            mock_query.assert_called_once_with(
                {
                    "search_query": "submittedDate:[20240115 TO 20240116]",
                    "start": 0,
                    "max_results": 20,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
            )

    @pytest.mark.asyncio
    async def test_search_date_range_with_category(self):
        """Test date range search with category filter"""
        mock_papers = [
            {
                "id": "http://arxiv.org/abs/2401.12345v1",
                "title": "AI Paper",
                "published": "2024-01-15T10:00:00Z",
                "categories": ["cs.AI"],
            }
        ]

        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = mock_papers

            result = await search_date_range(
                "2024-01-15", "2024-01-16", category="cs.AI", max_results=10
            )

            assert result["success"] is True
            assert result["category"] == "cs.AI"
            assert result["max_results"] == 10

            # Verify the query includes category filter
            mock_query.assert_called_once_with(
                {
                    "search_query": "cat:cs.AI AND submittedDate:[20240115 TO 20240116]",
                    "start": 0,
                    "max_results": 10,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
            )

    @pytest.mark.asyncio
    async def test_search_date_range_no_results(self):
        """Test date range search with no results"""
        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = []

            result = await search_date_range("2024-01-15", "2024-01-16")

            assert result["success"] is True
            assert result["papers"] == []
            assert result["returned_results"] == 0
            assert "Successfully found 0 papers" in result["message"]

    @pytest.mark.asyncio
    async def test_search_date_range_custom_max_results(self):
        """Test date range search with custom max_results"""
        mock_papers = [{"id": f"paper_{i}"} for i in range(50)]

        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = mock_papers

            result = await search_date_range("2024-01-01", "2024-12-31", max_results=50)

            assert result["max_results"] == 50
            assert result["returned_results"] == 50

            mock_query.assert_called_once_with(
                {
                    "search_query": "submittedDate:[20240101 TO 20241231]",
                    "start": 0,
                    "max_results": 50,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                }
            )

    @pytest.mark.asyncio
    async def test_search_date_range_date_formatting(self):
        """Test that dates are properly formatted for ArXiv API"""
        test_cases = [
            ("2024-01-01", "2024-12-31", "submittedDate:[20240101 TO 20241231]"),
            ("2023-05-15", "2023-05-20", "submittedDate:[20230515 TO 20230520]"),
            ("2022-12-01", "2022-12-02", "submittedDate:[20221201 TO 20221202]"),
        ]

        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = []

            for start_date, end_date, expected_date_query in test_cases:
                await search_date_range(start_date, end_date)

                # Get the last call arguments
                call_args = mock_query.call_args[0][0]
                assert call_args["search_query"] == expected_date_query

    @pytest.mark.asyncio
    async def test_search_date_range_with_empty_category(self):
        """Test date range search with empty category string"""
        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = []

            result = await search_date_range("2024-01-15", "2024-01-16", category="")

            assert result["category"] == "all"

            # Verify query doesn't include category filter for empty string
            call_args = mock_query.call_args[0][0]
            assert "cat:" not in call_args["search_query"]
            assert call_args["search_query"] == "submittedDate:[20240115 TO 20240116]"

    @pytest.mark.asyncio
    async def test_search_date_range_exception_handling(self):
        """Test that exceptions from execute_arxiv_query are propagated"""
        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.side_effect = Exception("API Error")

            with pytest.raises(Exception, match="API Error"):
                await search_date_range("2024-01-15", "2024-01-16")

    @pytest.mark.asyncio
    async def test_search_date_range_complex_category(self):
        """Test date range search with complex category string"""
        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = []

            await search_date_range(
                "2024-01-15", "2024-01-16", category="cs.AI OR cs.LG"
            )

            call_args = mock_query.call_args[0][0]
            expected_query = (
                "cat:cs.AI OR cs.LG AND submittedDate:[20240115 TO 20240116]"
            )
            assert call_args["search_query"] == expected_query

    @pytest.mark.asyncio
    async def test_search_date_range_parameter_consistency(self):
        """Test that all parameters are correctly passed and returned"""
        mock_papers = [{"id": "test_paper"}]

        with patch(
            "arxiv_mcp.capabilities.date_search.execute_arxiv_query",
            new_callable=AsyncMock,
        ) as mock_query:
            mock_query.return_value = mock_papers

            result = await search_date_range(
                start_date="2024-06-01",
                end_date="2024-06-30",
                category="math.CO",
                max_results=100,
            )

            # Check that all parameters are correctly reflected in the result
            assert result["start_date"] == "2024-06-01"
            assert result["end_date"] == "2024-06-30"
            assert result["category"] == "math.CO"
            assert result["max_results"] == 100
            assert result["returned_results"] == 1
            assert result["papers"] == mock_papers

            # Check API call parameters
            call_args = mock_query.call_args[0][0]
            assert (
                call_args["search_query"]
                == "cat:math.CO AND submittedDate:[20240601 TO 20240630]"
            )
            assert call_args["max_results"] == 100
            assert call_args["sortBy"] == "submittedDate"
            assert call_args["sortOrder"] == "descending"
            assert call_args["start"] == 0

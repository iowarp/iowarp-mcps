"""
Test suite for text-based search capabilities.
"""

import pytest
import sys
import os
from unittest.mock import patch

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capabilities.text_search import (
    search_by_title,
    search_by_abstract,
    search_papers_by_author,
)


class TestTextSearch:
    """Test text-based search functionality with full coverage"""

    @pytest.mark.asyncio
    async def test_search_by_title_success(self):
        """Test successful title search with mocked ArXiv response."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = [
                {
                    "id": "2301.12345",
                    "title": "Machine Learning in Healthcare",
                    "authors": ["Dr. Smith"],
                    "summary": "Deep learning for medical diagnosis",
                    "published": "2023-01-15",
                    "categories": ["cs.AI"],
                }
            ]

            result = await search_by_title("machine learning", 3)

            assert result["success"] is True
            assert result["title_keywords"] == "machine learning"
            assert result["max_results"] == 3
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 1
            assert result["returned_results"] == 1

    @pytest.mark.asyncio
    async def test_search_by_title_error(self):
        """Test title search error handling."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.side_effect = Exception("ArXiv API error")

            with pytest.raises(Exception) as exc_info:
                await search_by_title("test query", 5)

            assert "Title search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_abstract_success(self):
        """Test successful abstract search with mocked ArXiv response."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = [
                {
                    "id": "2301.67890",
                    "title": "Neural Network Architecture",
                    "authors": ["Dr. Johnson"],
                    "summary": "Novel neural network approaches for classification",
                    "published": "2023-01-20",
                    "categories": ["cs.LG"],
                }
            ]

            result = await search_by_abstract("neural network", 2)

            assert result["success"] is True
            assert result["abstract_keywords"] == "neural network"
            assert result["max_results"] == 2
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 1
            assert result["returned_results"] == 1

    @pytest.mark.asyncio
    async def test_search_by_abstract_error(self):
        """Test abstract search error handling."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.side_effect = Exception("Query execution failed")

            with pytest.raises(Exception) as exc_info:
                await search_by_abstract("test abstract", 3)

            assert "Abstract search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_papers_by_author_success(self):
        """Test successful author search with mocked ArXiv response."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = [
                {
                    "id": "2301.11111",
                    "title": "Computer Vision Applications",
                    "authors": ["Dr. Brown"],
                    "summary": "Computer vision for autonomous systems",
                    "published": "2023-01-25",
                    "categories": ["cs.CV"],
                },
                {
                    "id": "2301.22222",
                    "title": "AI in Robotics",
                    "authors": ["Dr. Brown", "Dr. Wilson"],
                    "summary": "Artificial intelligence applications in robotics",
                    "published": "2023-01-30",
                    "categories": ["cs.AI", "cs.RO"],
                },
            ]

            result = await search_papers_by_author("Dr. Brown", 5)

            assert result["success"] is True
            assert result["author"] == "Dr. Brown"
            assert result["max_results"] == 5
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 2
            assert result["returned_results"] == 2

    @pytest.mark.asyncio
    async def test_search_papers_by_author_error(self):
        """Test author search error handling."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.side_effect = Exception("Author search error")

            with pytest.raises(Exception) as exc_info:
                await search_papers_by_author("Test Author", 4)

            assert "Author search failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_title_empty_results(self):
        """Test title search with empty results."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = []

            result = await search_by_title("nonexistent query", 5)

            assert result["success"] is True
            assert result["title_keywords"] == "nonexistent query"
            assert result["max_results"] == 5
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 0
            assert result["returned_results"] == 0

    @pytest.mark.asyncio
    async def test_search_by_abstract_empty_results(self):
        """Test abstract search with empty results."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = []

            result = await search_by_abstract("nonexistent abstract", 3)

            assert result["success"] is True
            assert result["abstract_keywords"] == "nonexistent abstract"
            assert result["max_results"] == 3
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 0
            assert result["returned_results"] == 0

    @pytest.mark.asyncio
    async def test_search_papers_by_author_empty_results(self):
        """Test author search with empty results."""

        with patch("capabilities.text_search.execute_arxiv_query") as mock_query:
            mock_query.return_value = []

            result = await search_papers_by_author("Nonexistent Author", 2)

            assert result["success"] is True
            assert result["author"] == "Nonexistent Author"
            assert result["max_results"] == 2
            assert "papers" in result
            assert isinstance(result["papers"], list)
            assert len(result["papers"]) == 0
            assert result["returned_results"] == 0

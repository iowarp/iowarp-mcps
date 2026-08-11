"""Tests for ArXiv category search capabilities.

These exercise how each search builds its query and shapes its result. They mock
``execute_arxiv_query``, the seam directly above the HTTP call, so they never
reach export.arxiv.org: a test that depends on a third-party service being fast
enough fails for reasons that have nothing to do with the change under review,
which is what happened to this file in CI (httpx.ReadTimeout on three of six).
"""

from unittest.mock import AsyncMock, patch

import pytest

from arxiv_mcp.capabilities.category_search import (
    get_recent_papers,
    search_arxiv,
    search_by_subject,
)

QUERY_SEAM = "arxiv_mcp.capabilities.category_search.execute_arxiv_query"


def _paper(paper_id: str = "2501.00001v1", title: str = "A Paper") -> dict:
    """One parsed paper in the shape execute_arxiv_query returns."""
    return {
        "id": paper_id,
        "title": title,
        "authors": ["Ada Lovelace", "Alan Turing"],
        "abstract": "An abstract.",
        "published": "2026-01-01T00:00:00Z",
        "updated": "2026-01-02T00:00:00Z",
        "categories": ["cs.AI"],
        "links": [{"href": f"http://arxiv.org/abs/{paper_id}", "type": "text/html"}],
    }


class TestCategorySearch:
    """Test category search functionality"""

    @pytest.mark.asyncio
    async def test_search_arxiv_default(self):
        """Test default ArXiv search"""
        with patch(QUERY_SEAM, new=AsyncMock(return_value=[_paper()])):
            result = await search_arxiv()

        assert result["success"] is True
        assert "papers" in result
        assert "query" in result
        assert "max_results" in result
        assert "returned_results" in result
        assert isinstance(result["papers"], list)

    @pytest.mark.asyncio
    async def test_search_arxiv_custom_query(self):
        """Test ArXiv search with custom query"""
        with patch(QUERY_SEAM, new=AsyncMock(return_value=[_paper()])) as query:
            result = await search_arxiv("cs.AI", 5)

        assert result["success"] is True
        assert result["query"] == "cs.AI"
        assert result["max_results"] == 5
        assert query.await_count == 1

    @pytest.mark.asyncio
    async def test_get_recent_papers(self):
        """Test getting recent papers"""
        papers = [_paper(f"2501.0000{n}v1") for n in range(1, 4)]
        with patch(QUERY_SEAM, new=AsyncMock(return_value=papers)):
            result = await get_recent_papers("cs.LG", 3)

        assert result["success"] is True
        assert "papers" in result
        assert len(result["papers"]) <= 3

        # Check that papers have required fields
        if result["papers"]:
            paper = result["papers"][0]
            assert "title" in paper
            assert "authors" in paper
            assert "published" in paper

    @pytest.mark.asyncio
    async def test_search_by_subject(self):
        """Test search by subject"""
        with patch(QUERY_SEAM, new=AsyncMock(return_value=[_paper()])):
            result = await search_by_subject("math.CO", 2)

        assert result["success"] is True
        assert result["subject"] == "math.CO"
        assert result["max_results"] == 2
        assert "papers" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Test handling of queries that might return no results"""
        with patch(QUERY_SEAM, new=AsyncMock(return_value=[])):
            result = await search_arxiv("nonexistent.category", 1)

        # Should still succeed even if no papers found
        assert result["success"] is True
        assert "papers" in result
        assert isinstance(result["papers"], list)
        assert result["papers"] == []

    @pytest.mark.asyncio
    async def test_paper_structure(self):
        """Test that returned papers have the expected structure"""
        with patch(QUERY_SEAM, new=AsyncMock(return_value=[_paper()])):
            result = await search_arxiv("cs.AI", 1)

        assert result["papers"], "the mocked query returned a paper"
        paper = result["papers"][0]
        required_fields = [
            "id",
            "title",
            "authors",
            "published",
            "categories",
            "links",
        ]

        for field in required_fields:
            assert field in paper, f"Missing field: {field}"

        assert isinstance(paper["authors"], list)
        assert isinstance(paper["categories"], list)
        assert isinstance(paper["links"], list)

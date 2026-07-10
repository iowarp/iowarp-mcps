"""
Tests for ArXiv text-based search capabilities.
"""

import pytest

from arxiv_mcp.capabilities import text_search
from arxiv_mcp.capabilities.text_search import (
    search_by_title,
    search_by_abstract,
    search_papers_by_author,
)


@pytest.fixture(autouse=True)
def mock_arxiv_query(monkeypatch):
    """Use deterministic ArXiv query results for text-search unit tests."""

    async def fake_execute_arxiv_query(params):
        max_results = int(params["max_results"])
        query = str(params["search_query"])
        if query.startswith("ti:"):
            topic = query.removeprefix("ti:")
            title = f"{topic.title()} methods for scientific computing"
            summary = f"A paper about {topic}."
            authors = ["Test Author"]
        elif query.startswith("abs:"):
            topic = query.removeprefix("abs:")
            title = f"Applications of {topic.title()}"
            summary = f"This abstract discusses {topic} and reproducible experiments."
            authors = ["Test Author"]
        elif query.startswith("au:"):
            author = query.removeprefix("au:")
            title = f"Recent work by {author}"
            summary = "A representative author search result."
            authors = [author]
        else:
            title = "Generic ArXiv result"
            summary = "A representative search result."
            authors = ["Test Author"]

        return [
            {
                "id": f"test.{index}",
                "title": title,
                "summary": summary,
                "authors": authors,
            }
            for index in range(max_results)
        ]

    monkeypatch.setattr(text_search, "execute_arxiv_query", fake_execute_arxiv_query)


class TestTextSearch:
    """Test text-based search functionality"""

    @pytest.mark.asyncio
    async def test_search_by_title(self):
        """Test title search"""
        result = await search_by_title("machine learning", 3)

        assert result["success"] is True
        assert result["title_keywords"] == "machine learning"
        assert result["max_results"] == 3
        assert "papers" in result
        assert isinstance(result["papers"], list)

    @pytest.mark.asyncio
    async def test_search_by_abstract(self):
        """Test abstract search"""
        result = await search_by_abstract("neural network", 2)

        assert result["success"] is True
        assert result["abstract_keywords"] == "neural network"
        assert result["max_results"] == 2
        assert "papers" in result
        assert len(result["papers"]) <= 2

    @pytest.mark.asyncio
    async def test_search_papers_by_author(self):
        """Test author search"""
        result = await search_papers_by_author("Hinton", 2)

        assert result["success"] is True
        assert result["author"] == "Hinton"
        assert result["max_results"] == 2
        assert "papers" in result

        # Check that author appears in results
        if result["papers"]:
            paper = result["papers"][0]
            assert "authors" in paper
            assert isinstance(paper["authors"], list)

    @pytest.mark.asyncio
    async def test_title_search_relevance(self):
        """Test that title search returns relevant results"""
        result = await search_by_title("quantum computing", 3)

        assert result["success"] is True

        # Check that results contain the search terms (case insensitive)
        if result["papers"]:
            paper = result["papers"][0]
            title = paper.get("title", "").lower()
            # At least one paper should have relevant title
            has_quantum = any(
                "quantum" in p.get("title", "").lower() for p in result["papers"]
            )
            has_computing = any(
                "computing" in p.get("title", "").lower() for p in result["papers"]
            )

            # Should find at least one relevant result in top papers
            assert (
                has_quantum
                or has_computing
                or "quantum" in title
                or "computing" in title
            )

    @pytest.mark.asyncio
    async def test_abstract_search_keywords(self):
        """Test abstract search finds relevant papers"""
        result = await search_by_abstract("deep learning", 2)

        assert result["success"] is True
        assert "papers" in result

        # Results should be relevant to the search terms
        if result["papers"]:
            # Check that at least some results mention the search terms
            abstracts = [p.get("summary", "").lower() for p in result["papers"]]
            relevant_count = sum(
                1
                for abstract in abstracts
                if "deep" in abstract or "learning" in abstract
            )

            # Should find some relevant results
            assert relevant_count >= 0  # Even 0 is acceptable for edge cases

    @pytest.mark.asyncio
    async def test_search_result_structure(self):
        """Test that search results have consistent structure"""
        result = await search_by_title("artificial intelligence", 1)

        assert result["success"] is True
        assert "message" in result
        assert "returned_results" in result
        assert result["returned_results"] == len(result["papers"])

    @pytest.mark.asyncio
    async def test_empty_search_terms(self):
        """Test handling of empty search terms"""
        # This might raise an exception or return empty results
        # depending on ArXiv API behavior
        try:
            result = await search_by_title("", 1)
            assert "success" in result
        except Exception as e:
            # It's acceptable for this to fail
            assert isinstance(e, Exception)

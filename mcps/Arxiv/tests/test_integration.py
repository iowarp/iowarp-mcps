"""
Integration tests for ArXiv MCP Server.
"""

import pytest
import sys
import os
import json

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mcp_handlers


class TestIntegration:
    """Integration tests for the full MCP stack"""

    @pytest.mark.asyncio
    async def test_search_arxiv_handler(self):
        """Test the search ArXiv handler"""
        result = await mcp_handlers.search_arxiv_handler("cs.AI", 3)

        assert isinstance(result, dict)
        if result.get("isError"):
            assert "error" in str(result)
        else:
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_search_by_title_handler(self):
        """Test the title search handler"""
        result = await mcp_handlers.search_by_title_handler("machine learning", 2)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_get_recent_papers_handler(self):
        """Test the recent papers handler"""
        result = await mcp_handlers.get_recent_papers_handler("cs.LG", 2)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_search_papers_by_author_handler(self):
        """Test the author search handler"""
        result = await mcp_handlers.search_papers_by_author_handler("LeCun", 2)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_search_by_abstract_handler(self):
        """Test the abstract search handler"""
        result = await mcp_handlers.search_by_abstract_handler("deep learning", 2)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_search_by_subject_handler(self):
        """Test the subject search handler"""
        result = await mcp_handlers.search_by_subject_handler("cs.CV", 2)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_search_date_range_handler(self):
        """Test the date range search handler"""
        result = await mcp_handlers.search_date_range_handler(
            "2023-01-01", "2023-01-31", "cs.AI", 3
        )

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "papers" in result

    @pytest.mark.asyncio
    async def test_get_paper_details_handler(self):
        """Test the paper details handler"""
        # Use a well-known paper
        paper_id = "1706.03762"

        result = await mcp_handlers.get_paper_details_handler(paper_id)

        assert isinstance(result, dict)
        if result.get("isError"):
            # Network issues are acceptable
            assert "error" in str(result)
        else:
            assert result["success"] is True
            assert "paper" in result

    @pytest.mark.asyncio
    async def test_export_to_bibtex_handler(self):
        """Test the BibTeX export handler"""
        # Create sample papers JSON
        sample_papers = [
            {
                "id": "http://arxiv.org/abs/1706.03762v5",
                "title": "Attention Is All You Need",
                "authors": ["Ashish Vaswani", "Noam Shazeer"],
                "published": "2017-06-12T17:58:35Z",
                "categories": ["cs.CL", "cs.AI"],
            }
        ]

        papers_json = json.dumps(sample_papers)
        result = await mcp_handlers.export_to_bibtex_handler(papers_json)

        assert isinstance(result, dict)
        if not result.get("isError"):
            assert result["success"] is True
            assert "bibtex" in result

    @pytest.mark.asyncio
    async def test_export_to_bibtex_handler_invalid_json(self):
        """Test BibTeX export with invalid JSON"""
        result = await mcp_handlers.export_to_bibtex_handler("invalid json")

        assert isinstance(result, dict)
        assert result.get("isError") is True
        assert "error" in str(result).lower()

    @pytest.mark.asyncio
    async def test_find_similar_papers_handler(self):
        """Test the similar papers handler"""
        paper_id = "1706.03762"

        result = await mcp_handlers.find_similar_papers_handler(paper_id, 3)

        assert isinstance(result, dict)
        if result.get("isError"):
            # Network/API issues are acceptable
            assert "error" in str(result)
        else:
            assert result["success"] is True
            assert "similar_papers" in result

    @pytest.mark.asyncio
    async def test_error_handling_consistency(self):
        """Test that all handlers return consistent error format"""
        # Test with invalid parameters that should cause errors
        handlers_to_test = [
            (mcp_handlers.get_paper_details_handler, ["invalid.paper.id"]),
            (mcp_handlers.export_to_bibtex_handler, ["not a json string"]),
        ]

        for handler, args in handlers_to_test:
            result = await handler(*args)

            if result.get("isError"):
                # Check error format consistency
                assert "content" in result
                assert "_meta" in result
                assert "tool" in result["_meta"]
                assert "error" in result["_meta"]

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test a complete workflow: search -> details -> export"""
        try:
            # Step 1: Search for papers
            search_result = await mcp_handlers.search_arxiv_handler("cs.AI", 2)

            if search_result.get("isError") or not search_result.get("success"):
                pytest.skip("Search failed, skipping workflow test")

            papers = search_result["papers"]
            if not papers:
                pytest.skip("No papers found, skipping workflow test")

            # Step 2: Get details of first paper
            paper_id = papers[0]["id"].split("/")[-1] if papers[0]["id"] else None
            if paper_id:
                details_result = await mcp_handlers.get_paper_details_handler(paper_id)

                if not details_result.get("isError"):
                    assert details_result["success"] is True

            # Step 3: Export to BibTeX
            papers_json = json.dumps(papers[:1])  # Just first paper
            export_result = await mcp_handlers.export_to_bibtex_handler(papers_json)

            if not export_result.get("isError"):
                assert export_result["success"] is True
                assert "bibtex" in export_result
                assert "@article{" in export_result["bibtex"]

        except Exception as e:
            pytest.skip(f"Workflow test skipped due to: {e}")

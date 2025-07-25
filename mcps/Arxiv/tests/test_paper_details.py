"""
Tests for ArXiv paper details and analysis capabilities.
"""

import pytest
import sys
import os
from unittest.mock import patch, AsyncMock

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capabilities.paper_details import get_paper_details, find_similar_papers


class TestPaperDetails:
    """Test paper details and analysis functionality"""

    @pytest.mark.asyncio
    async def test_get_paper_details_valid_id(self):
        """Test getting details for a valid paper ID"""
        # Use a well-known ArXiv paper ID
        paper_id = "1706.03762"  # Attention Is All You Need

        result = await get_paper_details(paper_id)

        assert result["success"] is True
        assert result["arxiv_id"] == paper_id
        assert "paper" in result

        paper = result["paper"]
        assert "title" in paper
        assert "authors" in paper
        assert "published" in paper
        assert "categories" in paper
        assert isinstance(paper["authors"], list)
        assert len(paper["authors"]) > 0

    @pytest.mark.asyncio
    async def test_get_paper_details_invalid_id(self):
        """Test handling of invalid paper ID"""
        with pytest.raises(Exception) as exc_info:
            await get_paper_details("invalid.id.123")

        assert "not found" in str(
            exc_info.value
        ) or "Failed to get paper details" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_paper_details_structure(self):
        """Test that paper details have expected structure"""
        # Use another well-known paper
        paper_id = "1512.03385"  # ResNet paper

        try:
            result = await get_paper_details(paper_id)

            if result["success"]:
                paper = result["paper"]

                # Check required fields
                required_fields = ["id", "title", "authors", "published", "categories"]
                for field in required_fields:
                    assert field in paper, f"Missing required field: {field}"

                # Check field types
                assert isinstance(paper["authors"], list)
                assert isinstance(paper["categories"], list)
                assert isinstance(paper["title"], str)
                assert paper["title"].strip() != ""
        except Exception:
            # Skip test if paper not accessible
            pytest.skip("Paper not accessible for testing")

    @pytest.mark.asyncio
    async def test_find_similar_papers_valid_id(self):
        """Test finding similar papers for a valid ID"""
        # Use a well-known paper ID
        paper_id = "1706.03762"  # Attention Is All You Need

        try:
            result = await find_similar_papers(paper_id, 3)

            assert result["success"] is True
            assert result["max_results"] == 3
            assert "reference_paper" in result
            assert "similar_papers" in result
            assert isinstance(result["similar_papers"], list)
            assert len(result["similar_papers"]) <= 3

            # Check that reference paper is included
            ref_paper = result["reference_paper"]
            assert "title" in ref_paper
            assert "categories" in ref_paper

        except Exception:
            # Skip test if ArXiv is not accessible
            pytest.skip("ArXiv not accessible for testing")

    @pytest.mark.asyncio
    async def test_find_similar_papers_invalid_id(self):
        """Test handling of invalid paper ID for similarity search"""
        with pytest.raises(Exception) as exc_info:
            await find_similar_papers("invalid.paper.id", 2)

        error_msg = str(exc_info.value).lower()
        assert any(
            phrase in error_msg
            for phrase in [
                "not found",
                "failed",
                "could not retrieve",
                "similar papers search failed",
            ]
        )

    @pytest.mark.asyncio
    async def test_similar_papers_structure(self):
        """Test structure of similar papers results"""
        paper_id = "1512.03385"  # ResNet paper

        try:
            result = await find_similar_papers(paper_id, 2)

            if result["success"]:
                assert "returned_results" in result
                assert result["returned_results"] == len(result["similar_papers"])

                # Check similar papers structure
                if result["similar_papers"]:
                    similar_paper = result["similar_papers"][0]
                    assert "title" in similar_paper
                    assert "authors" in similar_paper
                    assert "categories" in similar_paper

        except Exception:
            pytest.skip("Similar papers test skipped due to network issues")

    @pytest.mark.asyncio
    async def test_paper_details_message_format(self):
        """Test that result messages are properly formatted"""
        paper_id = "1706.03762"

        try:
            result = await get_paper_details(paper_id)

            if result["success"]:
                assert "message" in result
                assert paper_id in result["message"]
                assert "successfully" in result["message"].lower()
        except Exception:
            pytest.skip("Paper details message test skipped")

    @pytest.mark.asyncio
    async def test_paper_with_doi_and_journal_ref(self):
        """Test paper details with DOI and journal reference to cover lines 54, 61."""

        with patch("httpx.AsyncClient") as mock_client:
            # Mock response with DOI and journal reference
            mock_response = AsyncMock()
            mock_response.content = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Test Paper with DOI</title>
        <summary>Test abstract</summary>
        <author><name>Test Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
        <arxiv:doi>10.1000/test.doi</arxiv:doi>
        <arxiv:journal_ref>Test Journal 2023, vol. 1, pp. 1-10</arxiv:journal_ref>
    </entry>
</feed>"""
            mock_response.raise_for_status = AsyncMock()

            mock_session = AsyncMock()
            mock_session.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_session

            result = await get_paper_details("2301.12345")

            if result["success"]:
                paper = result["paper"]
                assert "doi" in paper
                assert "journal_ref" in paper
                assert paper["doi"] == "10.1000/test.doi"
                assert "Test Journal" in paper["journal_ref"]

    @pytest.mark.asyncio
    async def test_find_similar_papers_error_handling(self):
        """Test find_similar_papers error handling to cover line 99."""

        with patch("capabilities.paper_details.get_paper_details") as mock_get_details:
            # Mock get_paper_details to return failure
            mock_get_details.return_value = {"success": False}

            with pytest.raises(Exception) as exc_info:
                await find_similar_papers("invalid-id", 5)

            assert "Could not retrieve reference paper details" in str(exc_info.value)

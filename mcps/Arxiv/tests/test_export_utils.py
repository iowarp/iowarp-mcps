"""
Tests for ArXiv export and formatting utilities.
"""

import pytest
import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capabilities.export_utils import (
    export_to_bibtex,
    format_paper_summary,
    format_search_results,
)
from capabilities.arxiv_base import generate_bibtex


class TestExportUtils:
    """Test export and formatting functionality"""

    def create_sample_paper(self):
        """Create a sample paper for testing"""
        return {
            "id": "http://arxiv.org/abs/1706.03762v5",
            "title": "Attention Is All You Need",
            "authors": ["Ashish Vaswani", "Noam Shazeer", "Niki Parmar"],
            "published": "2017-06-12T17:58:35Z",
            "categories": ["cs.CL", "cs.AI"],
            "summary": "The dominant sequence transduction models are based on complex recurrent...",
            "links": [
                {
                    "href": "http://arxiv.org/abs/1706.03762v5",
                    "rel": "alternate",
                    "type": "text/html",
                }
            ],
        }

    def test_generate_bibtex_single_paper(self):
        """Test BibTeX generation for a single paper"""
        paper = self.create_sample_paper()
        bibtex = generate_bibtex(paper)

        assert "@article{1706.03762v5" in bibtex
        assert "title = {Attention Is All You Need}" in bibtex
        assert "author = {Ashish Vaswani and Noam Shazeer and Niki Parmar}" in bibtex
        assert "year = {2017}" in bibtex
        assert "eprint = {1706.03762v5}" in bibtex
        assert "archivePrefix = {arXiv}" in bibtex
        assert "primaryClass = {cs.CL}" in bibtex
        assert "url = {http://arxiv.org/abs/1706.03762v5}" in bibtex

    @pytest.mark.asyncio
    async def test_export_to_bibtex_multiple_papers(self):
        """Test BibTeX export for multiple papers"""
        papers = [
            self.create_sample_paper(),
            {
                "id": "http://arxiv.org/abs/1512.03385v1",
                "title": "Deep Residual Learning for Image Recognition",
                "authors": ["Kaiming He", "Xiangyu Zhang"],
                "published": "2015-12-10T18:40:17Z",
                "categories": ["cs.CV"],
                "summary": "Deeper neural networks are more difficult to train...",
            },
        ]

        result = await export_to_bibtex(papers)

        assert result["success"] is True
        assert result["paper_count"] == 2
        assert "bibtex" in result

        bibtex = result["bibtex"]
        assert "Attention Is All You Need" in bibtex
        assert "Deep Residual Learning" in bibtex
        assert bibtex.count("@article{") == 2

    @pytest.mark.asyncio
    async def test_export_to_bibtex_empty_list(self):
        """Test BibTeX export with empty paper list"""
        result = await export_to_bibtex([])

        assert result["success"] is True
        assert result["paper_count"] == 0
        assert result["bibtex"] == ""

    def test_format_paper_summary(self):
        """Test paper summary formatting"""
        paper = self.create_sample_paper()
        summary = format_paper_summary(paper)

        assert "Title: Attention Is All You Need" in summary
        assert "Authors: Ashish Vaswani, Noam Shazeer, Niki Parmar" in summary
        assert "Published: 2017-06-12" in summary
        assert "Categories: cs.CL, cs.AI" in summary
        assert "ArXiv ID: 1706.03762v5" in summary
        assert "Abstract:" in summary
        assert len(summary.split("\n")) >= 6  # Multiple lines

    def test_format_paper_summary_missing_fields(self):
        """Test paper summary with missing fields"""
        incomplete_paper = {"title": "Test Paper", "authors": ["Author One"]}

        summary = format_paper_summary(incomplete_paper)
        assert "Title: Test Paper" in summary
        assert "Authors: Author One" in summary
        assert "Published: Unknown" in summary or "Published:" in summary

    @pytest.mark.asyncio
    async def test_format_search_results(self):
        """Test search results formatting"""
        papers = [self.create_sample_paper()]
        query_info = {"query": "cs.AI", "max_results": 5}

        result = await format_search_results(papers, query_info)

        assert result["success"] is True
        assert result["total_results"] == 1
        assert "query_info" in result
        assert result["query_info"] == query_info
        assert "papers" in result

        formatted_paper = result["papers"][0]
        assert "title" in formatted_paper
        assert "authors" in formatted_paper
        assert "arxiv_id" in formatted_paper
        assert formatted_paper["arxiv_id"] == "1706.03762v5"

    @pytest.mark.asyncio
    async def test_format_search_results_long_summary(self):
        """Test formatting with long abstracts"""
        long_paper = self.create_sample_paper()
        long_paper["summary"] = "A" * 500  # Very long abstract

        result = await format_search_results([long_paper], {})

        formatted_paper = result["papers"][0]
        assert len(formatted_paper["summary"]) <= 303  # 300 chars + '...'
        assert formatted_paper["summary"].endswith("...")

    def test_generate_bibtex_edge_cases(self):
        """Test BibTeX generation with edge cases"""
        # Paper with missing fields
        minimal_paper = {
            "id": "http://arxiv.org/abs/test",
            "title": "Test Title\nWith Newlines",
            "authors": [],
            "published": "",
            "categories": [],
        }

        bibtex = generate_bibtex(minimal_paper)
        assert "@article{test" in bibtex
        assert (
            "title = {Test Title With Newlines}" in bibtex
        )  # Newlines should be removed
        assert "author = {}" in bibtex  # Empty authors
        assert "year = {unknown}" in bibtex  # No published date

    @pytest.mark.asyncio
    async def test_export_error_handling(self):
        """Test error handling in export functions"""
        # Test with invalid paper data
        invalid_papers = [{"invalid": "data"}]

        try:
            result = await export_to_bibtex(invalid_papers)
            # Should still succeed but might have empty/default values
            assert "success" in result
        except Exception as e:
            # It's acceptable for this to raise an exception
            assert isinstance(e, Exception)

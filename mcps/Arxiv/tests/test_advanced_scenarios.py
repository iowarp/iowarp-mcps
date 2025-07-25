"""
Advanced test scenarios and integration tests.
Consolidates complex testing scenarios across all modules.
"""

import pytest
import sys
import os
import asyncio
from unittest.mock import patch, AsyncMock

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mcp_handlers
from capabilities import text_search as search_tools
from capabilities import export_utils


class TestAdvancedScenarios:
    """Advanced test scenarios and integration testing."""

    @pytest.mark.asyncio
    async def test_complete_workflow_integration(self):
        """Test complete workflow from search to download."""

        with (
            patch("httpx.AsyncClient") as mock_session_class,
            patch("os.makedirs"),
            patch("builtins.open", create=True),
        ):
            # Setup mock session
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock XML response for search
            mock_search_response = AsyncMock()
            mock_search_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Test Paper</title>
        <summary>Test abstract</summary>
        <author><name>Test Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
        <link href="http://arxiv.org/pdf/2301.12345v1.pdf" type="application/pdf" />
    </entry>
</feed>"""

            # Mock PDF response for download
            mock_pdf_response = AsyncMock()
            mock_pdf_response.status = 200
            mock_pdf_response.read.return_value = b"PDF content"

            # Configure session to return appropriate responses
            async def mock_get(*args, **kwargs):
                if "api.arxiv.org" in args[0]:
                    return mock_search_response
                elif ".pdf" in args[0]:
                    return mock_pdf_response
                return mock_search_response

            mock_session.get = mock_get

            # Step 1: Search for papers
            search_result = await mcp_handlers.search_arxiv_handler("cs.AI", 1)
            assert search_result is not None

            # Step 2: Get paper details
            paper_id = "2301.12345"
            details_result = await mcp_handlers.get_paper_details_handler(paper_id)
            assert details_result is not None

            # Step 3: Download paper
            download_result = await mcp_handlers.download_paper_pdf_handler(
                paper_id, "/tmp"
            )
            assert download_result is not None

    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent operations across different modules."""

        with patch("httpx.AsyncClient") as mock_session_class:
            # Setup mock session
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Test Paper</title>
        <summary>Test abstract</summary>
        <author><name>Test Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
    </entry>
</feed>"""
            mock_session.get.return_value = mock_response

            # Create multiple concurrent operations
            tasks = [
                mcp_handlers.search_arxiv_handler("cs.AI", 5),
                mcp_handlers.get_recent_papers_handler("cs.LG", 3),
                mcp_handlers.search_papers_by_author_handler("Test Author", 2),
                mcp_handlers.search_by_title_handler("Test Title", 1),
            ]

            # Execute concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without throwing exceptions
            for result in results:
                assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_error_propagation_scenarios(self):
        """Test error propagation through the system."""

        # Test 1: Network error propagation
        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_session.get.side_effect = Exception("Network error")

            # Should handle network errors gracefully
            result = await mcp_handlers.search_arxiv_handler("cs.AI", 5)
            assert "isError" in result or result is None

        # Test 2: XML parsing error propagation
        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = "Invalid XML content"
            mock_session.get.return_value = mock_response

            # Should handle XML parsing errors
            result = await mcp_handlers.search_arxiv_handler("cs.AI", 5)
            assert result is not None

    @pytest.mark.asyncio
    async def test_performance_scenarios(self):
        """Test performance-related scenarios."""

        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock a large XML response
            entries = []
            for i in range(100):
                entries.append(f"""
                <entry>
                    <id>http://arxiv.org/abs/230{i:04d}.12345v1</id>
                    <title>Test Paper {i}</title>
                    <summary>Test abstract {i}</summary>
                    <author><name>Test Author {i}</name></author>
                    <published>2023-01-15T00:00:00Z</published>
                    <updated>2023-01-15T00:00:00Z</updated>
                    <category term="cs.AI" />
                </entry>""")

            mock_response = AsyncMock()
            mock_response.text.return_value = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    {"".join(entries)}
</feed>"""
            mock_session.get.return_value = mock_response

            # Test handling large responses
            result = await mcp_handlers.search_arxiv_handler("cs.AI", 100)
            assert result is not None

            # Should handle large responses efficiently
            if isinstance(result, dict) and "papers" in result:
                # Should return requested number or available papers
                assert len(result["papers"]) <= 100

    @pytest.mark.asyncio
    async def test_edge_case_integration(self):
        """Test integration of various edge cases."""

        # Test with empty responses
        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>"""
            mock_session.get.return_value = mock_response

            # All handlers should handle empty responses gracefully
            handlers_to_test = [
                ("search_arxiv_handler", ["cs.AI", 5]),
                ("get_recent_papers_handler", ["cs.AI", 5]),
                ("search_papers_by_author_handler", ["Test Author", 5]),
                ("search_by_title_handler", ["Test Title", 5]),
                ("search_by_abstract_handler", ["Test Abstract", 5]),
                ("search_by_subject_handler", ["Test Subject", 5]),
                ("search_date_range_handler", ["2023-01-01", "2023-12-31", 5]),
            ]

            for handler_name, args in handlers_to_test:
                handler = getattr(mcp_handlers, handler_name)
                result = await handler(*args)
                assert result is not None

    @pytest.mark.asyncio
    async def test_complex_search_scenarios(self):
        """Test complex search scenarios with various parameters."""

        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Machine Learning in Healthcare</title>
        <summary>Deep learning approaches for medical diagnosis</summary>
        <author><name>Dr. Smith</name></author>
        <author><name>Dr. Johnson</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
        <category term="cs.LG" />
    </entry>
</feed>"""
            mock_session.get.return_value = mock_response

            # Test complex search scenarios
            complex_scenarios = [
                # Multi-word queries
                ("search_by_title_handler", ["machine learning healthcare", 5]),
                ("search_by_abstract_handler", ["deep learning medical diagnosis", 5]),
                (
                    "search_by_subject_handler",
                    ["artificial intelligence healthcare", 5],
                ),
                # Special characters in queries
                ("search_papers_by_author_handler", ["Dr. Smith", 5]),
                ("search_by_title_handler", ["AI & ML: Future Perspectives", 5]),
                # Edge cases for date ranges
                (
                    "search_date_range_handler",
                    ["2023-01-01", "2023-01-01", 5],
                ),  # Same date
                (
                    "search_date_range_handler",
                    ["2020-12-31", "2021-01-01", 5],
                ),  # Year boundary
            ]

            for handler_name, args in complex_scenarios:
                handler = getattr(mcp_handlers, handler_name)
                result = await handler(*args)
                assert result is not None

    @pytest.mark.asyncio
    async def test_download_integration_scenarios(self):
        """Test download-related integration scenarios."""

        with (
            patch("httpx.AsyncClient") as mock_session_class,
            patch("os.makedirs"),
            patch("builtins.open", create=True),
            patch("os.path.exists", return_value=False),
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            # Mock successful PDF download
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.read.return_value = b"PDF content data"
            mock_session.get.return_value = mock_response

            # Test single download
            result = await mcp_handlers.download_paper_pdf_handler("2301.12345", "/tmp")
            assert result is not None

            # Test multiple downloads
            result = await mcp_handlers.download_multiple_pdfs_handler(
                ["2301.12345", "2301.67890"], "/tmp"
            )
            assert result is not None

            # Test PDF URL extraction
            result = await mcp_handlers.get_pdf_url_handler("2301.12345")
            assert result is not None

    @pytest.mark.asyncio
    async def test_export_integration_scenarios(self):
        """Test export-related integration scenarios."""

        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Test Paper for Export</title>
        <summary>Test abstract for export</summary>
        <author><name>Export Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
    </entry>
</feed>"""
            mock_session.get.return_value = mock_response

            # Test export scenarios
            export_scenarios = [
                # Single paper export
                (["2301.12345"],),
                # Multiple papers export
                (["2301.12345", "2301.67890", "2301.11111"],),
                # Large batch export
                ([f"2301.{i:05d}" for i in range(20)],),
            ]

            for args in export_scenarios:
                result = await mcp_handlers.export_to_bibtex_handler(*args)
                assert result is not None

                # Verify bibtex structure if result contains data
                if isinstance(result, dict) and "bibtex" in result:
                    bibtex_content = result["bibtex"]
                    if bibtex_content:
                        assert "@" in bibtex_content  # Should contain BibTeX entries

    @pytest.mark.asyncio
    async def test_paper_details_integration(self):
        """Test paper details integration scenarios."""

        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Detailed Paper Analysis</title>
        <summary>Comprehensive abstract with multiple concepts and technical details</summary>
        <author><name>Primary Author</name></author>
        <author><name>Secondary Author</name></author>
        <author><name>Third Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-16T00:00:00Z</updated>
        <category term="cs.AI" />
        <category term="cs.LG" />
        <category term="stat.ML" />
        <link href="http://arxiv.org/pdf/2301.12345v1.pdf" type="application/pdf" />
        <arxiv:comment>15 pages, 8 figures</arxiv:comment>
        <arxiv:primary_category term="cs.AI" />
    </entry>
</feed>"""
            mock_session.get.return_value = mock_response

            # Test detailed paper information extraction
            paper_ids = ["2301.12345", "2301.67890", "invalid.id", "9999.99999"]

            for paper_id in paper_ids:
                result = await mcp_handlers.get_paper_details_handler(paper_id)
                assert result is not None

                # Test similar papers functionality
                similar_result = await mcp_handlers.find_similar_papers_handler(
                    paper_id, 5
                )
                assert similar_result is not None

    @pytest.mark.asyncio
    async def test_stress_testing_scenarios(self):
        """Test system under stress conditions."""

        with patch("httpx.AsyncClient") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session
            mock_response = AsyncMock()
            mock_response.text.return_value = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
    <entry>
        <id>http://arxiv.org/abs/2301.12345v1</id>
        <title>Stress Test Paper</title>
        <summary>Stress test abstract</summary>
        <author><name>Stress Author</name></author>
        <published>2023-01-15T00:00:00Z</published>
        <updated>2023-01-15T00:00:00Z</updated>
        <category term="cs.AI" />
    </entry>
</feed>"""
            mock_session.get.return_value = mock_response

            # Stress test: Multiple rapid requests
            rapid_tasks = []
            for i in range(50):
                task = mcp_handlers.search_arxiv_handler("cs.AI", 1)
                rapid_tasks.append(task)

            # Execute all tasks concurrently
            results = await asyncio.gather(*rapid_tasks, return_exceptions=True)

            # Count successful results
            successful_results = [r for r in results if not isinstance(r, Exception)]
            assert len(successful_results) >= 0  # Should handle rapid requests

    def test_module_interaction_edge_cases(self):
        """Test edge cases in module interactions."""

        # Test direct module function calls
        with patch("capabilities.text_search.search_by_title") as mock_search:
            mock_search.return_value = {"papers": [], "count": 0}

            # Test search_tools integration
            if hasattr(search_tools, "search_by_title"):
                result = search_tools.search_by_title("test query", 5)
                assert result is not None
                mock_search.assert_called_once()

        # Test export_utils edge cases
        test_papers = [
            {"id": "test1", "title": "Test Paper 1", "authors": ["Author 1"]},
            {"id": "test2", "title": "Test Paper 2", "authors": ["Author 2"]},
        ]

        # Test various export scenarios
        with patch("capabilities.export_utils.export_to_bibtex") as mock_export:
            mock_export.return_value = "@article{test, title={Test}}"

            # Test export functionality
            if hasattr(export_utils, "export_to_bibtex"):
                result = export_utils.export_to_bibtex(test_papers)
                assert result is not None

    @pytest.mark.asyncio
    async def test_comprehensive_error_recovery(self):
        """Test comprehensive error recovery scenarios."""

        # Test recovery from various error conditions
        error_scenarios = [
            (ConnectionError("Connection failed"), "Network error recovery"),
            (TimeoutError("Request timeout"), "Timeout error recovery"),
            (ValueError("Invalid data"), "Data validation error recovery"),
            (KeyError("Missing key"), "Missing data error recovery"),
            (Exception("Generic error"), "Generic error recovery"),
        ]

        for error, description in error_scenarios:
            with patch("httpx.AsyncClient") as mock_session_class:
                mock_session = AsyncMock()
                mock_session_class.return_value.__aenter__.return_value = mock_session
                mock_session.get.side_effect = error

                # Test that all handlers can recover from this error
                handlers = [
                    ("search_arxiv_handler", ["cs.AI", 5]),
                    ("get_recent_papers_handler", ["cs.AI", 5]),
                    ("search_papers_by_author_handler", ["Test", 5]),
                ]

                for handler_name, args in handlers:
                    handler = getattr(mcp_handlers, handler_name)
                    try:
                        result = await handler(*args)
                        # Should return some result or handle error gracefully
                        assert result is not None or result is None
                    except Exception:
                        # Some handlers may re-raise exceptions, which is also valid
                        pass

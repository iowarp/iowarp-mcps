"""
Comprehensive tests for MCP handlers.
Tests all handler functions and error handling scenarios.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import mcp_handlers


class TestMCPHandlers:
    """Test class for MCP handler functions."""

    @pytest.mark.asyncio
    async def test_search_arxiv_handler_success(self):
        """Test search_arxiv_handler with successful response."""
        expected_result = {"papers": [{"id": "test"}]}

        with patch("mcp_handlers.search_arxiv", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = expected_result

            result = await mcp_handlers.search_arxiv_handler("cs.AI", 5)

            assert result == expected_result
            mock_search.assert_called_once_with("cs.AI", 5)

    @pytest.mark.asyncio
    async def test_search_arxiv_handler_error(self):
        """Test search_arxiv_handler with error handling."""
        with patch("mcp_handlers.search_arxiv", new_callable=AsyncMock) as mock_search:
            mock_search.side_effect = ValueError("Test error")

            result = await mcp_handlers.search_arxiv_handler("cs.AI", 5)

            assert result["isError"] is True
            assert "Test error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_arxiv"
            assert result["_meta"]["error"] == "ValueError"

    @pytest.mark.asyncio
    async def test_get_recent_papers_handler_success(self):
        """Test get_recent_papers_handler with successful response."""
        expected_result = {"papers": [{"id": "recent"}]}

        with patch(
            "mcp_handlers.get_recent_papers", new_callable=AsyncMock
        ) as mock_recent:
            mock_recent.return_value = expected_result

            result = await mcp_handlers.get_recent_papers_handler("cs.AI", 5)

            assert result == expected_result
            mock_recent.assert_called_once_with("cs.AI", 5)

    @pytest.mark.asyncio
    async def test_get_recent_papers_handler_error(self):
        """Test get_recent_papers_handler with error handling."""
        with patch(
            "mcp_handlers.get_recent_papers", new_callable=AsyncMock
        ) as mock_recent:
            mock_recent.side_effect = ConnectionError("Network error")

            result = await mcp_handlers.get_recent_papers_handler("cs.AI", 5)

            assert result["isError"] is True
            assert "Network error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "get_recent_papers"
            assert result["_meta"]["error"] == "ConnectionError"

    @pytest.mark.asyncio
    async def test_search_papers_by_author_handler_success(self):
        """Test search_papers_by_author_handler with successful response."""
        expected_result = {"papers": [{"author": "Test Author"}]}

        with patch(
            "mcp_handlers.search_papers_by_author", new_callable=AsyncMock
        ) as mock_author:
            mock_author.return_value = expected_result

            result = await mcp_handlers.search_papers_by_author_handler(
                "Test Author", 10
            )

            assert result == expected_result
            mock_author.assert_called_once_with("Test Author", 10)

    @pytest.mark.asyncio
    async def test_search_papers_by_author_handler_error(self):
        """Test search_papers_by_author_handler with error handling."""
        with patch(
            "mcp_handlers.search_papers_by_author", new_callable=AsyncMock
        ) as mock_author:
            mock_author.side_effect = RuntimeError("Runtime error")

            result = await mcp_handlers.search_papers_by_author_handler(
                "Test Author", 10
            )

            assert result["isError"] is True
            assert "Runtime error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_papers_by_author"
            assert result["_meta"]["error"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_search_by_title_handler_success(self):
        """Test search_by_title_handler with successful response."""
        expected_result = {"papers": [{"title": "Test Title"}]}

        with patch(
            "mcp_handlers.search_by_title", new_callable=AsyncMock
        ) as mock_title:
            mock_title.return_value = expected_result

            result = await mcp_handlers.search_by_title_handler("neural networks", 10)

            assert result == expected_result
            mock_title.assert_called_once_with("neural networks", 10)

    @pytest.mark.asyncio
    async def test_search_by_title_handler_error(self):
        """Test search_by_title_handler with error handling."""
        with patch(
            "mcp_handlers.search_by_title", new_callable=AsyncMock
        ) as mock_title:
            mock_title.side_effect = Exception("Generic error")

            result = await mcp_handlers.search_by_title_handler("neural networks", 10)

            assert result["isError"] is True
            assert "Generic error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_by_title"
            assert result["_meta"]["error"] == "Exception"

    @pytest.mark.asyncio
    async def test_search_by_abstract_handler_success(self):
        """Test search_by_abstract_handler with successful response."""
        expected_result = {"papers": [{"abstract": "machine learning"}]}

        with patch(
            "mcp_handlers.search_by_abstract", new_callable=AsyncMock
        ) as mock_abstract:
            mock_abstract.return_value = expected_result

            result = await mcp_handlers.search_by_abstract_handler(
                "machine learning", 10
            )

            assert result == expected_result
            mock_abstract.assert_called_once_with("machine learning", 10)

    @pytest.mark.asyncio
    async def test_search_by_abstract_handler_error(self):
        """Test search_by_abstract_handler with error handling."""
        with patch(
            "mcp_handlers.search_by_abstract", new_callable=AsyncMock
        ) as mock_abstract:
            mock_abstract.side_effect = KeyError("Key not found")

            result = await mcp_handlers.search_by_abstract_handler(
                "machine learning", 10
            )

            assert result["isError"] is True
            assert "Key not found" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_by_abstract"
            assert result["_meta"]["error"] == "KeyError"

    @pytest.mark.asyncio
    async def test_search_by_subject_handler_success(self):
        """Test search_by_subject_handler with successful response."""
        expected_result = {"papers": [{"subject": "Computer Science"}]}

        with patch(
            "mcp_handlers.search_by_subject", new_callable=AsyncMock
        ) as mock_subject:
            mock_subject.return_value = expected_result

            result = await mcp_handlers.search_by_subject_handler(
                "Computer Science", 10
            )

            assert result == expected_result
            mock_subject.assert_called_once_with("Computer Science", 10)

    @pytest.mark.asyncio
    async def test_search_by_subject_handler_error(self):
        """Test search_by_subject_handler with error handling."""
        with patch(
            "mcp_handlers.search_by_subject", new_callable=AsyncMock
        ) as mock_subject:
            mock_subject.side_effect = AttributeError("Attribute error")

            result = await mcp_handlers.search_by_subject_handler(
                "Computer Science", 10
            )

            assert result["isError"] is True
            assert "Attribute error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_by_subject"
            assert result["_meta"]["error"] == "AttributeError"

    @pytest.mark.asyncio
    async def test_search_date_range_handler_success(self):
        """Test search_date_range_handler with successful response."""
        expected_result = {"papers": [{"date": "2023-06-15"}]}

        with patch(
            "mcp_handlers.search_date_range", new_callable=AsyncMock
        ) as mock_date:
            mock_date.return_value = expected_result

            result = await mcp_handlers.search_date_range_handler(
                "2023-06-01", "2023-06-30", "", 10
            )

            assert result == expected_result
            mock_date.assert_called_once_with("2023-06-01", "2023-06-30", "", 10)

    @pytest.mark.asyncio
    async def test_search_date_range_handler_error(self):
        """Test search_date_range_handler with error handling."""
        with patch(
            "mcp_handlers.search_date_range", new_callable=AsyncMock
        ) as mock_date:
            mock_date.side_effect = TypeError("Type error")

            result = await mcp_handlers.search_date_range_handler(
                "2023-06-01", "2023-06-30", "", 10
            )

            assert result["isError"] is True
            assert "Type error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "search_date_range"
            assert result["_meta"]["error"] == "TypeError"

    @pytest.mark.asyncio
    async def test_get_paper_details_handler_success(self):
        """Test get_paper_details_handler with successful response."""
        expected_result = {"paper": {"id": "2023.12345", "details": True}}

        with patch(
            "mcp_handlers.get_paper_details", new_callable=AsyncMock
        ) as mock_details:
            mock_details.return_value = expected_result

            result = await mcp_handlers.get_paper_details_handler("2023.12345")

            assert result == expected_result
            mock_details.assert_called_once_with("2023.12345")

    @pytest.mark.asyncio
    async def test_get_paper_details_handler_error(self):
        """Test get_paper_details_handler with error handling."""
        with patch(
            "mcp_handlers.get_paper_details", new_callable=AsyncMock
        ) as mock_details:
            mock_details.side_effect = FileNotFoundError("Paper not found")

            result = await mcp_handlers.get_paper_details_handler("2023.12345")

            assert result["isError"] is True
            assert "Paper not found" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "get_paper_details"
            assert result["_meta"]["error"] == "FileNotFoundError"

    @pytest.mark.asyncio
    async def test_find_similar_papers_handler_success(self):
        """Test find_similar_papers_handler with successful response."""
        expected_result = {"similar_papers": [{"id": "2023.67890"}]}

        with patch(
            "mcp_handlers.find_similar_papers", new_callable=AsyncMock
        ) as mock_similar:
            mock_similar.return_value = expected_result

            result = await mcp_handlers.find_similar_papers_handler("2023.12345", 5)

            assert result == expected_result
            mock_similar.assert_called_once_with("2023.12345", 5)

    @pytest.mark.asyncio
    async def test_find_similar_papers_handler_error(self):
        """Test find_similar_papers_handler with error handling."""
        with patch(
            "mcp_handlers.find_similar_papers", new_callable=AsyncMock
        ) as mock_similar:
            mock_similar.side_effect = IndexError("Index error")

            result = await mcp_handlers.find_similar_papers_handler("2023.12345", 5)

            assert result["isError"] is True
            assert "Index error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "find_similar_papers"
            assert result["_meta"]["error"] == "IndexError"

    @pytest.mark.asyncio
    async def test_export_to_bibtex_handler_success(self):
        """Test export_to_bibtex_handler with successful response."""
        expected_result = {"bibtex": "@article{test,title={Test}}"}

        with patch(
            "mcp_handlers.export_to_bibtex", new_callable=AsyncMock
        ) as mock_export:
            mock_export.return_value = expected_result

            # Pass as JSON string as expected by the handler
            result = await mcp_handlers.export_to_bibtex_handler('["2023.12345"]')

            assert result == expected_result
            mock_export.assert_called_once_with(["2023.12345"])

    @pytest.mark.asyncio
    async def test_export_to_bibtex_handler_error(self):
        """Test export_to_bibtex_handler with error handling."""
        with patch(
            "mcp_handlers.export_to_bibtex", new_callable=AsyncMock
        ) as mock_export:
            mock_export.side_effect = PermissionError("Permission denied")

            result = await mcp_handlers.export_to_bibtex_handler('["2023.12345"]')

            assert result["isError"] is True
            assert "Permission denied" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "export_to_bibtex"
            assert result["_meta"]["error"] == "PermissionError"

    @pytest.mark.asyncio
    async def test_download_paper_pdf_handler_success(self):
        """Test download_paper_pdf_handler with successful response."""
        expected_result = {"status": "success", "file_path": "/tmp/paper.pdf"}

        with patch(
            "mcp_handlers.download_paper_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.return_value = expected_result

            result = await mcp_handlers.download_paper_pdf_handler("2023.12345", "/tmp")

            assert result == expected_result
            mock_download.assert_called_once_with("2023.12345", "/tmp")

    @pytest.mark.asyncio
    async def test_download_paper_pdf_handler_error(self):
        """Test download_paper_pdf_handler with error handling."""
        with patch(
            "mcp_handlers.download_paper_pdf", new_callable=AsyncMock
        ) as mock_download:
            mock_download.side_effect = OSError("OS error")

            result = await mcp_handlers.download_paper_pdf_handler("2023.12345", "/tmp")

            assert result["isError"] is True
            assert "OS error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "download_paper_pdf"
            assert result["_meta"]["error"] == "OSError"

    @pytest.mark.asyncio
    async def test_get_pdf_url_handler_success(self):
        """Test get_pdf_url_handler with successful response."""
        expected_result = {"pdf_url": "https://arxiv.org/pdf/2023.12345.pdf"}

        with patch("mcp_handlers.get_pdf_url", new_callable=AsyncMock) as mock_url:
            mock_url.return_value = expected_result

            result = await mcp_handlers.get_pdf_url_handler("2023.12345")

            assert result == expected_result
            mock_url.assert_called_once_with("2023.12345")

    @pytest.mark.asyncio
    async def test_get_pdf_url_handler_error(self):
        """Test get_pdf_url_handler with error handling."""
        with patch("mcp_handlers.get_pdf_url", new_callable=AsyncMock) as mock_url:
            mock_url.side_effect = ImportError("Import error")

            result = await mcp_handlers.get_pdf_url_handler("2023.12345")

            assert result["isError"] is True
            assert "Import error" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "get_pdf_url"
            assert result["_meta"]["error"] == "ImportError"

    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_handler_success(self):
        """Test download_multiple_pdfs_handler with successful response."""
        expected_result = {"status": "success", "downloaded": 2}

        with patch(
            "mcp_handlers.download_multiple_pdfs", new_callable=AsyncMock
        ) as mock_multi:
            mock_multi.return_value = expected_result

            # Pass as JSON string as expected by the handler
            result = await mcp_handlers.download_multiple_pdfs_handler(
                '["2023.12345", "2023.67890"]', "/tmp", 2
            )

            assert result == expected_result
            mock_multi.assert_called_once_with(["2023.12345", "2023.67890"], "/tmp", 2)

    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_handler_error(self):
        """Test download_multiple_pdfs_handler with error handling."""
        with patch(
            "mcp_handlers.download_multiple_pdfs", new_callable=AsyncMock
        ) as mock_multi:
            mock_multi.side_effect = NotImplementedError("Not implemented")

            result = await mcp_handlers.download_multiple_pdfs_handler(
                '["2023.12345", "2023.67890"]', "/tmp", 2
            )

            assert result["isError"] is True
            assert "Not implemented" in str(result["content"][0]["text"])
            assert result["_meta"]["tool"] == "download_multiple_pdfs"
            assert result["_meta"]["error"] == "NotImplementedError"

    @pytest.mark.asyncio
    async def test_all_handlers_error_format_consistency(self):
        """Test that all handlers return consistent error formats."""

        handlers_to_test = [
            ("search_arxiv_handler", ["cs.AI", 5]),
            ("get_recent_papers_handler", ["cs.AI", 5]),
            ("search_papers_by_author_handler", ["Test Author", 5]),
            ("search_by_title_handler", ["Test Title", 5]),
            ("search_by_abstract_handler", ["Test Abstract", 5]),
            ("search_by_subject_handler", ["Test Subject", 5]),
            ("search_date_range_handler", ["2023-01-01", "2023-12-31", 5]),
            ("get_paper_details_handler", ["test-id"]),
            ("find_similar_papers_handler", ["test-id", 5]),
            ("export_to_bibtex_handler", ['["test-id"]']),
            ("download_paper_pdf_handler", ["test-id", "/tmp"]),
            ("get_pdf_url_handler", ["test-id"]),
            ("download_multiple_pdfs_handler", ['["test-id"]', "/tmp", 1]),
        ]

        for handler_name, args in handlers_to_test:
            if hasattr(mcp_handlers, handler_name):
                handler = getattr(mcp_handlers, handler_name)

                # Mock the underlying function to raise an exception
                func_name = handler_name.replace("_handler", "")
                with patch(
                    f"mcp_handlers.{func_name}", new_callable=AsyncMock
                ) as mock_func:
                    mock_func.side_effect = RuntimeError("Test error")

                    result = await handler(*args)

                    # Verify consistent error format
                    assert result["isError"] is True
                    assert "content" in result
                    assert isinstance(result["content"], list)
                    assert len(result["content"]) > 0
                    assert "text" in result["content"][0]
                    assert "_meta" in result
                    assert "tool" in result["_meta"]
                    assert "error" in result["_meta"]
                    assert result["_meta"]["error"] == "RuntimeError"

    @pytest.mark.asyncio
    async def test_handlers_with_none_parameters(self):
        """Test handlers with None parameters."""

        handlers_to_test = [
            ("search_arxiv_handler", [None, 5]),
            ("get_recent_papers_handler", ["cs.AI", None]),
            ("search_papers_by_author_handler", [None, 5]),
            ("get_paper_details_handler", [None]),
        ]

        for handler_name, args in handlers_to_test:
            if hasattr(mcp_handlers, handler_name):
                handler = getattr(mcp_handlers, handler_name)

                # Should handle None parameters gracefully
                result = await handler(*args)
                # May return error or handle gracefully
                assert result is not None

    @pytest.mark.asyncio
    async def test_handlers_with_empty_string_parameters(self):
        """Test handlers with empty string parameters."""

        handlers_to_test = [
            ("search_arxiv_handler", ["", 5]),
            ("search_papers_by_author_handler", ["", 5]),
            ("search_by_title_handler", ["", 5]),
            ("search_by_abstract_handler", ["", 5]),
            ("search_by_subject_handler", ["", 5]),
            ("get_paper_details_handler", [""]),
            ("find_similar_papers_handler", ["", 5]),
        ]

        for handler_name, args in handlers_to_test:
            if hasattr(mcp_handlers, handler_name):
                handler = getattr(mcp_handlers, handler_name)

                # Should handle empty strings gracefully
                result = await handler(*args)
                assert result is not None

    @pytest.mark.asyncio
    async def test_handlers_with_extreme_parameters(self):
        """Test handlers with extreme parameter values."""

        # Test with very large max_results
        large_result = await mcp_handlers.search_arxiv_handler("cs.AI", 10000)
        assert large_result is not None

        # Test with zero max_results
        zero_result = await mcp_handlers.search_arxiv_handler("cs.AI", 0)
        assert zero_result is not None

        # Test with negative max_results
        negative_result = await mcp_handlers.search_arxiv_handler("cs.AI", -1)
        assert negative_result is not None

        # Test with very long strings
        long_query = "A" * 10000
        long_result = await mcp_handlers.search_by_title_handler(long_query, 5)
        assert long_result is not None

    @pytest.mark.asyncio
    async def test_concurrent_handler_execution(self):
        """Test concurrent execution of multiple handlers."""

        # Create tasks for concurrent execution
        tasks = [
            mcp_handlers.search_arxiv_handler("cs.AI", 3),
            mcp_handlers.get_recent_papers_handler("cs.LG", 2),
            mcp_handlers.search_papers_by_author_handler("Test Author", 1),
            mcp_handlers.search_by_title_handler("Test Title", 1),
            mcp_handlers.search_by_abstract_handler("Test Abstract", 1),
        ]

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All tasks should complete
        assert len(results) == len(tasks)

        # None should be exceptions (though they may be error responses)
        for result in results:
            assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_json_parameter_parsing(self):
        """Test JSON parameter parsing in handlers."""

        # Test export_to_bibtex_handler with various JSON formats
        json_test_cases = [
            '["2301.12345"]',
            '["2301.12345", "2301.67890"]',
            "[]",
            '["single-id"]',
        ]

        for json_str in json_test_cases:
            result = await mcp_handlers.export_to_bibtex_handler(json_str)
            assert result is not None

        # Test download_multiple_pdfs_handler
        for json_str in json_test_cases:
            result = await mcp_handlers.download_multiple_pdfs_handler(
                json_str, "/tmp", 1
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_invalid_json_parameter_handling(self):
        """Test handling of invalid JSON parameters."""

        invalid_json_cases = [
            "invalid json",
            "{not a list}",
            "[unclosed",
            "",
            None,
        ]

        for invalid_json in invalid_json_cases:
            # export_to_bibtex_handler should handle invalid JSON
            result = await mcp_handlers.export_to_bibtex_handler(invalid_json)
            # Should return error or handle gracefully
            assert result is not None

            # download_multiple_pdfs_handler should handle invalid JSON
            result = await mcp_handlers.download_multiple_pdfs_handler(
                invalid_json, "/tmp", 1
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_date_range_edge_cases(self):
        """Test date range handler with edge cases."""

        date_edge_cases = [
            ("2023-01-01", "2023-01-01", 5),  # Same start/end date
            ("2023-12-31", "2023-01-01", 5),  # End before start
            ("invalid-date", "2023-12-31", 5),  # Invalid start date
            ("2023-01-01", "invalid-date", 5),  # Invalid end date
            ("", "", 5),  # Empty dates
            ("2023-02-29", "2023-02-28", 5),  # Invalid leap year date
        ]

        for start_date, end_date, max_results in date_edge_cases:
            result = await mcp_handlers.search_date_range_handler(
                start_date, end_date, max_results
            )
            assert result is not None

    @pytest.mark.asyncio
    async def test_paper_id_validation(self):
        """Test paper ID validation across handlers."""

        invalid_paper_ids = [
            "",
            None,
            "invalid.format",
            "toolong.paperid.format.test",
            "special@characters",
            "12345",  # Missing prefix
            "cs/0123456",  # Old format
        ]

        paper_id_handlers = [
            "get_paper_details_handler",
            "find_similar_papers_handler",
            "download_paper_pdf_handler",
            "get_pdf_url_handler",
        ]

        for paper_id in invalid_paper_ids:
            for handler_name in paper_id_handlers:
                if hasattr(mcp_handlers, handler_name):
                    handler = getattr(mcp_handlers, handler_name)

                    if handler_name == "download_paper_pdf_handler":
                        result = await handler(paper_id, "/tmp")
                    elif handler_name == "find_similar_papers_handler":
                        result = await handler(paper_id, 5)
                    else:
                        result = await handler(paper_id)

                    # Should handle invalid IDs gracefully
                    assert result is not None

    @pytest.mark.asyncio
    async def test_handler_performance_characteristics(self):
        """Test performance characteristics of handlers."""

        import time

        # Test response time for basic operations
        start_time = time.time()
        result = await mcp_handlers.search_arxiv_handler("cs.AI", 1)
        end_time = time.time()

        # Should complete reasonably quickly (allowing for network mocking)
        assert (end_time - start_time) < 30  # 30 second timeout
        assert result is not None

    @pytest.mark.asyncio
    async def test_exception_type_coverage(self):
        """Test coverage of different exception types."""

        exception_types = [
            (ValueError, "Value error"),
            (TypeError, "Type error"),
            (RuntimeError, "Runtime error"),
            (ConnectionError, "Connection error"),
            (TimeoutError, "Timeout error"),
            (KeyError, "Key error"),
            (IndexError, "Index error"),
            (AttributeError, "Attribute error"),
            (ImportError, "Import error"),
            (NotImplementedError, "Not implemented"),
        ]

        for exception_type, message in exception_types:
            # Test with search_arxiv_handler as representative
            with patch(
                "mcp_handlers.search_arxiv", new_callable=AsyncMock
            ) as mock_search:
                mock_search.side_effect = exception_type(message)

                result = await mcp_handlers.search_arxiv_handler("cs.AI", 5)

                assert result["isError"] is True
                assert message in str(result["content"][0]["text"])
                assert result["_meta"]["error"] == exception_type.__name__

    @pytest.mark.asyncio
    async def test_handler_metadata_consistency(self):
        """Test that handler metadata is consistent."""

        handlers_and_tools = [
            ("search_arxiv_handler", "search_arxiv"),
            ("get_recent_papers_handler", "get_recent_papers"),
            ("search_papers_by_author_handler", "search_papers_by_author"),
            ("search_by_title_handler", "search_by_title"),
            ("search_by_abstract_handler", "search_by_abstract"),
            ("search_by_subject_handler", "search_by_subject"),
            ("search_date_range_handler", "search_date_range"),
            ("get_paper_details_handler", "get_paper_details"),
            ("find_similar_papers_handler", "find_similar_papers"),
            ("export_to_bibtex_handler", "export_to_bibtex"),
            ("download_paper_pdf_handler", "download_paper_pdf"),
            ("get_pdf_url_handler", "get_pdf_url"),
            ("download_multiple_pdfs_handler", "download_multiple_pdfs"),
        ]

        for handler_name, expected_tool_name in handlers_and_tools:
            if hasattr(mcp_handlers, handler_name):
                handler = getattr(mcp_handlers, handler_name)

                # Force an error to check metadata
                func_name = handler_name.replace("_handler", "")
                with patch(
                    f"mcp_handlers.{func_name}", new_callable=AsyncMock
                ) as mock_func:
                    mock_func.side_effect = ValueError("Test error")

                    # Call with appropriate parameters
                    if handler_name == "search_date_range_handler":
                        result = await handler("2023-01-01", "2023-12-31", 5)
                    elif handler_name in [
                        "export_to_bibtex_handler",
                        "download_multiple_pdfs_handler",
                    ]:
                        if handler_name == "download_multiple_pdfs_handler":
                            result = await handler('["test"]', "/tmp", 1)
                        else:
                            result = await handler('["test"]')
                    elif handler_name in ["download_paper_pdf_handler"]:
                        result = await handler("test", "/tmp")
                    elif handler_name in ["find_similar_papers_handler"]:
                        result = await handler("test", 5)
                    elif (
                        "search" in handler_name
                        and handler_name != "search_date_range_handler"
                    ):
                        result = await handler("test", 5)
                    else:
                        result = await handler("test")

                    # Check metadata
                    assert result["_meta"]["tool"] == expected_tool_name

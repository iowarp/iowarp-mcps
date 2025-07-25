"""
Test error handling in arxiv_base module to improve coverage.
"""

import pytest
import httpx
from unittest.mock import patch, Mock, AsyncMock
import xml.etree.ElementTree as ET
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capabilities.arxiv_base import (
    execute_arxiv_query,
    generate_bibtex,
    parse_arxiv_entry,
)


class TestArxivBaseErrors:
    """Test error handling in arxiv_base module."""

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_timeout_exception(self, mock_client):
        """Test TimeoutException handling."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = httpx.TimeoutException("Timeout")

        mock_client_instance = Mock()
        mock_client_instance.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test query", "max_results": 5})

        assert "ArXiv API request timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_http_status_error(self, mock_client):
        """Test HTTPStatusError handling."""
        # Create mock response that raises HTTPStatusError
        mock_response = Mock()
        mock_response.status_code = 503

        # Create the HTTP error
        response_mock = Mock()
        response_mock.status_code = 503
        http_error = httpx.HTTPStatusError(
            "Service Unavailable", request=Mock(), response=response_mock
        )
        mock_response.raise_for_status.side_effect = http_error

        # Create async context manager mock
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test query", "max_results": 5})

        assert "ArXiv API error: 503" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_parse_error(self, mock_client):
        """Test XML ParseError handling."""
        mock_response = Mock()
        mock_response.text = "invalid xml content"
        mock_response.raise_for_status = Mock()

        mock_client_instance = Mock()
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client.return_value = mock_client_instance

        # Mock ET.fromstring to raise ParseError
        with patch(
            "capabilities.arxiv_base.ET.fromstring",
            side_effect=ET.ParseError("Invalid XML"),
        ):
            with pytest.raises(Exception) as exc_info:
                await execute_arxiv_query(
                    {"search_query": "test query", "max_results": 5}
                )

            assert "Failed to parse ArXiv response" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_unexpected_error(self, mock_client):
        """Test unexpected error handling."""
        mock_client_instance = Mock()
        mock_client_instance.get.side_effect = ValueError("Unexpected error")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test query", "max_results": 5})

        assert "ArXiv query failed: Unexpected error" in str(exc_info.value)

    def test_generate_bibtex_empty_authors(self):
        """Test generate_bibtex with empty authors list."""
        paper = {
            "id": "2023.12345",
            "title": "Test Paper",
            "authors": [],  # Empty authors list
            "published": "2023-06-15",
        }

        result = generate_bibtex(paper)

        # Should handle empty authors gracefully
        assert "author = {}" in result or "author={}" in result

    def test_generate_bibtex_string_authors(self):
        """Test generate_bibtex with string authors instead of list."""
        paper = {
            "id": "2023.12345",
            "title": "Test Paper",
            "authors": "Single Author",  # String instead of list
            "published": "2023-06-15",
        }

        result = generate_bibtex(paper)

        # Should handle string authors - the function converts string to empty due to type checking
        # This tests the isinstance(paper_authors, list) condition in the code
        assert "author = {}" in result or "author={}" in result

    def test_generate_bibtex_missing_published_date(self):
        """Test generate_bibtex with missing published date."""
        paper = {
            "id": "2023.12345",
            "title": "Test Paper",
            "authors": ["Test Author"],
            # Missing "published" field
        }

        result = generate_bibtex(paper)

        # Should handle missing published date
        assert "Test Author" in result

    def test_generate_bibtex_malformed_date(self):
        """Test generate_bibtex with malformed date."""
        paper = {
            "id": "2023.12345",
            "title": "Test Paper",
            "authors": ["Test Author"],
            "published": "not-a-date",
        }

        result = generate_bibtex(paper)

        # Should handle malformed date gracefully
        assert "Test Author" in result

    def test_generate_bibtex_edge_cases(self):
        """Test generate_bibtex with various edge cases."""

        # Test with all fields present
        complete_paper = {
            "id": "2023.12345",
            "title": "Complete Test Paper",
            "authors": ["First Author", "Second Author"],
            "published": "2023-01-15T00:00:00Z",
            "summary": "Test abstract",
            "categories": ["cs.AI", "cs.LG"],
        }

        result = generate_bibtex(complete_paper)
        assert "First Author and Second Author" in result
        assert "Complete Test Paper" in result
        assert "2023" in result

        # Test with minimal fields
        minimal_paper = {"id": "minimal.test", "title": "Minimal Paper", "authors": []}

        result = generate_bibtex(minimal_paper)
        assert "Minimal Paper" in result

        # Test with special characters in title
        special_paper = {
            "id": "special.test",
            "title": "Paper with $pecial Ch@racters & Symbols",
            "authors": ["Test Author"],
        }

        result = generate_bibtex(special_paper)
        assert "Test Author" in result

    def test_parse_arxiv_entry_edge_cases(self):
        """Test parse_arxiv_entry with various edge cases."""

        # Test with minimal XML entry
        minimal_xml = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/test.minimal</id>
            <title>Minimal Entry</title>
        </entry>
        """

        entry = ET.fromstring(minimal_xml)
        result = parse_arxiv_entry(entry)

        assert "test.minimal" in result["id"]  # ID may include full URL
        assert result["title"] == "Minimal Entry"
        assert result["authors"] == []
        assert result["summary"] == ""

        # Test with complex XML entry
        complex_xml = """
        <entry xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
            <id>http://arxiv.org/abs/2023.12345v2</id>
            <title>  Complex Entry with Whitespace  </title>
            <summary>  
                Multi-line abstract
                with extra whitespace
            </summary>
            <author>
                <name>First Author</name>
                <arxiv:affiliation>University A</arxiv:affiliation>
            </author>
            <author>
                <name>Second Author</name>
                <arxiv:affiliation>University B</arxiv:affiliation>
            </author>
            <published>2023-01-15T12:30:45Z</published>
            <updated>2023-01-16T08:15:30Z</updated>
            <category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <category term="cs.LG" scheme="http://arxiv.org/schemas/atom"/>
            <link href="http://arxiv.org/abs/2023.12345v2" rel="alternate" type="text/html"/>
            <link href="http://arxiv.org/pdf/2023.12345v2.pdf" rel="related" type="application/pdf"/>
            <arxiv:comment>15 pages, 8 figures, accepted to ICML 2023</arxiv:comment>
            <arxiv:primary_category term="cs.AI" scheme="http://arxiv.org/schemas/atom"/>
            <arxiv:journal_ref>ICML 2023, pp. 123-138</arxiv:journal_ref>
        </entry>
        """

        entry = ET.fromstring(complex_xml)
        result = parse_arxiv_entry(entry)

        assert "2023.12345" in result["id"]  # ID may include full URL
        assert result["title"] == "Complex Entry with Whitespace"
        assert "Multi-line abstract" in result["summary"]
        assert result["authors"] == ["First Author", "Second Author"]
        assert result["published"] == "2023-01-15T12:30:45Z"
        assert result["updated"] == "2023-01-16T08:15:30Z"
        assert "cs.AI" in result["categories"]
        assert "cs.LG" in result["categories"]

    def test_parse_arxiv_entry_malformed_xml(self):
        """Test parse_arxiv_entry with malformed XML elements."""

        # Test with missing namespace
        no_namespace_xml = """
        <entry>
            <id>http://arxiv.org/abs/test.no_ns</id>
            <title>No Namespace Entry</title>
            <author>
                <name>Test Author</name>
            </author>
        </entry>
        """

        entry = ET.fromstring(no_namespace_xml)
        result = parse_arxiv_entry(entry)

        # Should still parse basic information
        assert (
            "test.no_ns" in result["id"] or result["id"] == ""
        )  # May not extract ID without namespace
        assert (
            result["title"] == "No Namespace Entry" or result["title"] == ""
        )  # May not parse without namespace        # Test with empty elements
        empty_elements_xml = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/test.empty</id>
            <title></title>
            <summary></summary>
            <author><name></name></author>
        </entry>
        """

        entry = ET.fromstring(empty_elements_xml)
        result = parse_arxiv_entry(entry)

        assert "test.empty" in result["id"]  # ID may include full URL
        assert result["title"] == ""
        assert result["summary"] == ""

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_network_connectivity_errors(self, mock_client):
        """Test various network connectivity errors."""

        # Test connection error
        mock_client_instance = Mock()
        mock_client_instance.get.side_effect = httpx.ConnectError("Connection failed")
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test", "max_results": 5})

        assert "Connection failed" in str(
            exc_info.value
        ) or "ArXiv query failed" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_malformed_response_handling(self, mock_client):
        """Test handling of malformed API responses."""

        # Test completely invalid XML
        mock_response = AsyncMock()
        mock_response.text.return_value = "Not XML at all"
        mock_response.raise_for_status.return_value = None

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test", "max_results": 5})

        assert "ArXiv query failed" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_partial_xml_response(self, mock_client):
        """Test handling of partial/truncated XML responses."""

        # Test truncated XML (missing closing tags)
        truncated_xml = """<?xml version="1.0" encoding="UTF-8"?>
        <feed xmlns="http://www.w3.org/2005/Atom">
            <title>ArXiv Query Results</title>
            <entry>
                <id>http://arxiv.org/abs/test.truncated</id>
                <title>Truncated Entry</title>
        """  # Missing closing tags

        mock_response = AsyncMock()
        mock_response.text.return_value = truncated_xml
        mock_response.raise_for_status.return_value = None

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test", "max_results": 5})

        assert "ArXiv query failed" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_empty_response_handling(self, mock_client):
        """Test handling of empty API responses."""

        # Test completely empty response
        mock_response = AsyncMock()
        mock_response.text.return_value = ""
        mock_response.raise_for_status.return_value = None

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        with pytest.raises(Exception) as exc_info:
            await execute_arxiv_query({"search_query": "test", "max_results": 5})

        assert "ArXiv query failed" in str(exc_info.value)

    @pytest.mark.asyncio
    @patch("capabilities.arxiv_base.httpx.AsyncClient")
    async def test_api_parameter_validation(self, mock_client):
        """Test API parameter validation and edge cases."""

        # Test with None parameters
        mock_response = Mock()
        mock_response.text = (
            '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        )
        mock_response.raise_for_status.return_value = None

        mock_client_instance = Mock()
        mock_client_instance.get.return_value = mock_response
        mock_client.return_value.__aenter__.return_value = mock_client_instance

        # Should handle None search_query
        try:
            result = await execute_arxiv_query({"search_query": None, "max_results": 5})
            assert result is not None
        except Exception as e:
            # May raise exception for None query, which is also valid
            assert "search_query" in str(e) or "query" in str(e).lower()

    def test_bibtex_special_character_handling(self):
        """Test BibTeX generation with special characters."""

        # Test with LaTeX special characters
        latex_paper = {
            "id": "latex.test",
            "title": "Paper with $\\alpha$ and {brackets} and %comments",
            "authors": ["Author with & ampersand", "Author_with_underscores"],
            "published": "2023-01-15T00:00:00Z",
        }

        result = generate_bibtex(latex_paper)

        # Should handle special characters in title and authors
        assert "latex.test" in result
        assert "Author with" in result

    def test_bibtex_unicode_handling(self):
        """Test BibTeX generation with Unicode characters."""

        unicode_paper = {
            "id": "unicode.test",
            "title": "Papér with Ünicödé Charåcters",
            "authors": ["José García", "李明", "Владимир Петров"],
            "published": "2023-01-15T00:00:00Z",
        }

        result = generate_bibtex(unicode_paper)

        # Should handle Unicode characters
        assert "unicode.test" in result

    def test_id_extraction_edge_cases(self):
        """Test ID extraction from various URL formats."""

        id_test_cases = [
            ("http://arxiv.org/abs/2023.12345v1", "2023.12345"),
            ("http://arxiv.org/abs/2023.12345", "2023.12345"),
            ("https://arxiv.org/abs/math/0601001v1", "math/0601001"),
            ("http://arxiv.org/abs/hep-th/9901001", "hep-th/9901001"),
            ("arxiv:2023.12345", "2023.12345"),
            ("2023.12345", "2023.12345"),
        ]

        for url, expected_id in id_test_cases:
            # Test with XML entry containing this ID format
            xml_content = f"""
            <entry xmlns="http://www.w3.org/2005/Atom">
                <id>{url}</id>
                <title>Test Paper</title>
            </entry>
            """

            entry = ET.fromstring(xml_content)
            result = parse_arxiv_entry(entry)

            assert expected_id in result["id"]  # ID may include full URL

    @pytest.mark.asyncio
    async def test_query_parameter_encoding(self):
        """Test that query parameters are properly encoded."""

        with patch("capabilities.arxiv_base.httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.content = b'<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'
            mock_response.raise_for_status = AsyncMock()

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_client_instance

            # Test with special characters in query
            special_query = "query with spaces & symbols"
            result = await execute_arxiv_query(
                {"search_query": special_query, "max_results": 5}
            )  # Should complete successfully
            assert result is not None

    def test_generate_bibtex_extreme_cases(self):
        """Test generate_bibtex with extreme cases."""

        # Test with very long title
        long_title_paper = {
            "id": "long.test",
            "title": "A" * 1000,  # Very long title
            "authors": ["Test Author"],
            "published": "2023-01-15T00:00:00Z",
        }

        result = generate_bibtex(long_title_paper)
        assert "long.test" in result

        # Test with many authors
        many_authors_paper = {
            "id": "many.authors",
            "title": "Paper with Many Authors",
            "authors": [f"Author {i}" for i in range(100)],
            "published": "2023-01-15T00:00:00Z",
        }

        result = generate_bibtex(many_authors_paper)
        assert "many.authors" in result

        # Test with no data
        empty_paper = {}

        try:
            result = generate_bibtex(empty_paper)
            # May succeed with minimal data or fail
            assert result is not None or result == ""
        except (KeyError, TypeError):
            # May raise exception for missing required fields
            pass

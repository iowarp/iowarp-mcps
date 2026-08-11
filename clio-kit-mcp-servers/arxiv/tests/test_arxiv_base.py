"""
Tests for ArXiv base utilities.
"""

import pytest
import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, MagicMock, patch

from arxiv_mcp.capabilities.arxiv_base import (
    parse_arxiv_entry,
    execute_arxiv_query,
    generate_bibtex,
)


class TestParseArxivEntry:
    """Test ArXiv entry parsing functionality"""

    def test_parse_complete_entry(self):
        """Test parsing a complete ArXiv entry"""
        xml_content = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2401.12345v1</id>
            <title>Test Paper Title</title>
            <summary>This is a test paper abstract</summary>
            <published>2024-01-15T10:00:00Z</published>
            <updated>2024-01-16T11:00:00Z</updated>
            <author>
                <name>John Doe</name>
            </author>
            <author>
                <name>Jane Smith</name>
            </author>
            <category term="cs.AI" />
            <category term="cs.LG" />
            <link href="http://arxiv.org/abs/2401.12345v1" rel="alternate" type="text/html" />
            <link href="http://arxiv.org/pdf/2401.12345v1.pdf" rel="related" type="application/pdf" />
        </entry>
        """
        entry = ET.fromstring(xml_content)
        result = parse_arxiv_entry(entry)

        assert result["id"] == "http://arxiv.org/abs/2401.12345v1"
        assert result["title"] == "Test Paper Title"
        assert result["summary"] == "This is a test paper abstract"
        assert result["published"] == "2024-01-15T10:00:00Z"
        assert result["updated"] == "2024-01-16T11:00:00Z"
        assert result["authors"] == ["John Doe", "Jane Smith"]
        assert result["categories"] == ["cs.AI", "cs.LG"]
        assert len(result["links"]) == 2
        assert result["links"][0]["href"] == "http://arxiv.org/abs/2401.12345v1"
        assert result["links"][0]["rel"] == "alternate"
        assert result["links"][0]["type"] == "text/html"

    def test_parse_minimal_entry(self):
        """Test parsing an entry with minimal information"""
        xml_content = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2401.12345v1</id>
            <title>   Title with whitespace   </title>
        </entry>
        """
        entry = ET.fromstring(xml_content)
        result = parse_arxiv_entry(entry)

        assert result["id"] == "http://arxiv.org/abs/2401.12345v1"
        assert result["title"] == "Title with whitespace"  # Should be stripped
        assert result["summary"] == ""
        assert result["published"] == ""
        assert result["updated"] == ""
        assert result["authors"] == []
        assert result["categories"] == []
        assert result["links"] == []

    def test_parse_entry_with_missing_elements(self):
        """Test parsing an entry with None/missing elements"""
        xml_content = """
        <entry xmlns="http://www.w3.org/2005/Atom">
        </entry>
        """
        entry = ET.fromstring(xml_content)
        result = parse_arxiv_entry(entry)

        assert result["id"] == ""
        assert result["title"] == ""
        assert result["summary"] == ""
        assert result["published"] == ""
        assert result["updated"] == ""
        assert result["authors"] == []
        assert result["categories"] == []
        assert result["links"] == []

    def test_parse_entry_with_empty_author_names(self):
        """Test parsing entry with empty author names"""
        xml_content = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2401.12345v1</id>
            <author>
                <name>Valid Author</name>
            </author>
            <author>
                <name></name>
            </author>
            <author>
            </author>
        </entry>
        """
        entry = ET.fromstring(xml_content)
        result = parse_arxiv_entry(entry)

        assert result["authors"] == [
            "Valid Author"
        ]  # Only valid author should be included

    def test_parse_entry_with_links_missing_attributes(self):
        """Test parsing entry with links that have missing attributes"""
        xml_content = """
        <entry xmlns="http://www.w3.org/2005/Atom">
            <id>http://arxiv.org/abs/2401.12345v1</id>
            <link href="http://arxiv.org/abs/2401.12345v1" />
            <link rel="alternate" type="text/html" />
        </entry>
        """
        entry = ET.fromstring(xml_content)
        result = parse_arxiv_entry(entry)

        assert len(result["links"]) == 2
        assert result["links"][0] == {
            "href": "http://arxiv.org/abs/2401.12345v1",
            "rel": "",
            "type": "",
        }
        assert result["links"][1] == {
            "href": "",
            "rel": "alternate",
            "type": "text/html",
        }


class TestExecuteArxivQuery:
    """Test ArXiv query execution functionality"""

    @pytest.mark.asyncio
    async def test_successful_query(self):
        """Test successful ArXiv API query"""
        mock_response_content = """
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/2401.12345v1</id>
                <title>Test Paper</title>
                <summary>Test summary</summary>
                <published>2024-01-15T10:00:00Z</published>
                <author>
                    <name>Test Author</name>
                </author>
                <category term="cs.AI" />
            </entry>
        </feed>
        """

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = mock_response_content.encode()
            mock_response.raise_for_status.return_value = None

            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            params = {"search_query": "machine learning", "max_results": 10}
            result = await execute_arxiv_query(params)

            assert len(result) == 1
            assert result[0]["id"] == "http://arxiv.org/abs/2401.12345v1"
            assert result[0]["title"] == "Test Paper"
            assert result[0]["authors"] == ["Test Author"]
            mock_client.get.assert_called_once_with(
                "https://export.arxiv.org/api/query", params=params
            )

    @pytest.mark.asyncio
    async def test_timeout_exception(self):
        """Test handling of timeout exceptions"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = Exception("httpx.TimeoutException")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with patch("httpx.TimeoutException", Exception):
                with pytest.raises(Exception, match="ArXiv API request timed out"):
                    await execute_arxiv_query({"search_query": "test"})

    @pytest.mark.asyncio
    async def test_http_status_error(self):
        """Test handling of HTTP status errors"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 400

            # Create a proper HTTPStatusError mock
            from httpx import HTTPStatusError, Request

            mock_error = HTTPStatusError(
                "Bad Request", request=MagicMock(spec=Request), response=mock_response
            )
            mock_client.get.side_effect = mock_error
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with pytest.raises(Exception, match="ArXiv API error: 400"):
                await execute_arxiv_query({"search_query": "test"})

    @pytest.mark.asyncio
    async def test_xml_parse_error(self):
        """Test handling of XML parsing errors"""
        invalid_xml = b"<invalid>xml content"

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = invalid_xml
            mock_response.raise_for_status.return_value = None

            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with pytest.raises(Exception, match="Failed to parse ArXiv response"):
                await execute_arxiv_query({"search_query": "test"})

    @pytest.mark.asyncio
    async def test_unexpected_error(self):
        """Test handling of unexpected errors"""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = ValueError("Unexpected error")
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with pytest.raises(Exception, match="ArXiv query failed: Unexpected error"):
                await execute_arxiv_query({"search_query": "test"})

    @pytest.mark.asyncio
    async def test_empty_response(self):
        """Test handling of empty ArXiv response"""
        empty_response_content = """
        <feed xmlns="http://www.w3.org/2005/Atom">
        </feed>
        """

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.content = empty_response_content.encode()
            mock_response.raise_for_status.return_value = None

            mock_client.get.return_value = mock_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await execute_arxiv_query({"search_query": "test"})
            assert result == []


class TestGenerateBibtex:
    """Test BibTeX generation functionality"""

    def test_generate_complete_bibtex(self):
        """Test BibTeX generation with complete paper information"""
        paper = {
            "id": "http://arxiv.org/abs/2401.12345v1",
            "title": "Machine Learning in Scientific Computing",
            "authors": ["John Doe", "Jane Smith", "Bob Johnson"],
            "published": "2024-01-15T10:00:00Z",
            "categories": ["cs.AI", "cs.LG"],
        }

        result = generate_bibtex(paper)

        assert "2401.12345v1" in result
        assert "Machine Learning in Scientific Computing" in result
        assert "John Doe and Jane Smith and Bob Johnson" in result
        assert "2024" in result
        assert "cs.AI" in result
        assert "http://arxiv.org/abs/2401.12345v1" in result
        assert "@article{2401.12345v1," in result

    def test_generate_bibtex_with_multiline_title(self):
        """Test BibTeX generation with multiline title"""
        paper = {
            "id": "http://arxiv.org/abs/2401.12345v1",
            "title": "A Very Long Title\nThat Spans Multiple\nLines",
            "authors": ["John Doe"],
            "published": "2024-01-15T10:00:00Z",
            "categories": ["cs.AI"],
        }

        result = generate_bibtex(paper)

        # Title should have newlines replaced with spaces
        assert "A Very Long Title That Spans Multiple Lines" in result
        assert "\n" not in result.split("title = {")[1].split("}")[0]

    def test_generate_bibtex_minimal_info(self):
        """Test BibTeX generation with minimal information"""
        paper = {
            "id": "http://arxiv.org/abs/2401.12345v1",
        }

        result = generate_bibtex(paper)

        assert "2401.12345v1" in result
        assert "title = {}" in result
        assert "author = {}" in result
        assert "year = {unknown}" in result
        assert "primaryClass = {}" in result

    def test_generate_bibtex_empty_fields(self):
        """Test BibTeX generation with empty fields"""
        paper = {
            "id": "",
            "title": "",
            "authors": [],
            "published": "",
            "categories": [],
        }

        result = generate_bibtex(paper)

        assert "unknown" in result  # For both id and year
        assert "title = {}" in result
        assert "author = {}" in result
        assert "year = {unknown}" in result
        assert "primaryClass = {}" in result

    def test_generate_bibtex_non_string_authors(self):
        """Test BibTeX generation with invalid author types"""
        paper = {
            "id": "http://arxiv.org/abs/2401.12345v1",
            "title": "Test Paper",
            "authors": ["John Doe", 123, None],  # Mixed types
            "published": "2024-01-15T10:00:00Z",
            "categories": ["cs.AI"],
        }

        result = generate_bibtex(paper)

        # Should handle gracefully with empty authors
        assert "author = {}" in result

    def test_generate_bibtex_non_string_fields(self):
        """Test BibTeX generation with non-string field types"""
        paper = {
            "id": 12345,  # Non-string ID
            "title": None,  # None title
            "authors": "not a list",  # Non-list authors
            "published": 2024,  # Non-string published
            "categories": "not a list",  # Non-list categories
        }

        result = generate_bibtex(paper)

        assert "unknown" in result  # For id processing
        assert "title = {}" in result
        assert "author = {}" in result
        assert "year = {unknown}" in result
        assert "primaryClass = {}" in result

    def test_generate_bibtex_complex_arxiv_id(self):
        """Test BibTeX generation with complex ArXiv ID formats"""
        test_cases = [
            ("http://arxiv.org/abs/2401.12345v1", "2401.12345v1"),
            (
                "https://arxiv.org/abs/cs/0601001v2",
                "0601001v2",
            ),  # Only the last part after /
            (
                "http://arxiv.org/abs/math.NT/0601001",
                "0601001",
            ),  # Only the last part after /
            ("simple_id", "simple_id"),
            ("", "unknown"),
        ]

        for paper_id, expected_id in test_cases:
            paper = {"id": paper_id}
            result = generate_bibtex(paper)
            assert (
                f"@article{{{expected_id}," in result or "@article{unknown," in result
            )


class TestRateLimitRetry:
    """execute_arxiv_query retries a 429 with bounded backoff (real ArXiv
    rate-limit behavior, not a test-only accommodation -- see arxiv_base.py's
    _get_with_rate_limit_retry). asyncio.sleep is patched to a no-op so these
    stay instant; the retry COUNT and terminal behavior are what's verified.
    """

    @staticmethod
    def _feed_response() -> MagicMock:
        content = """
        <feed xmlns="http://www.w3.org/2005/Atom">
            <entry>
                <id>http://arxiv.org/abs/2401.12345v1</id>
                <title>Test Paper</title>
            </entry>
        </feed>
        """
        response = MagicMock()
        response.status_code = 200
        response.content = content.encode()
        response.raise_for_status.return_value = None
        return response

    @staticmethod
    def _rate_limited_response() -> MagicMock:
        response = MagicMock()
        response.status_code = 429
        response.url = "https://export.arxiv.org/api/query"
        response.request = MagicMock()
        response.headers = {}
        return response

    @pytest.mark.asyncio
    @patch("arxiv_mcp.capabilities.arxiv_base.asyncio.sleep", new_callable=AsyncMock)
    async def test_retries_once_on_429_then_succeeds(self, mock_sleep):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [
                self._rate_limited_response(),
                self._feed_response(),
            ]
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            result = await execute_arxiv_query(
                {"search_query": "test", "max_results": 1}
            )

            assert len(result) == 1
            assert mock_client.get.call_count == 2
            mock_sleep.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("arxiv_mcp.capabilities.arxiv_base.asyncio.sleep", new_callable=AsyncMock)
    async def test_exhausts_retries_and_raises_429(self, mock_sleep):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [
                self._rate_limited_response() for _ in range(4)
            ]
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with pytest.raises(Exception, match="ArXiv API error: 429"):
                await execute_arxiv_query({"search_query": "test", "max_results": 1})

            assert mock_client.get.call_count == 4
            assert mock_sleep.await_count == 3

    @pytest.mark.asyncio
    @patch("arxiv_mcp.capabilities.arxiv_base.asyncio.sleep", new_callable=AsyncMock)
    async def test_honors_retry_after_header(self, mock_sleep):
        rate_limited = self._rate_limited_response()
        rate_limited.headers = {"Retry-After": "2.5"}
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [rate_limited, self._feed_response()]
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            await execute_arxiv_query({"search_query": "test", "max_results": 1})

            mock_sleep.assert_awaited_once_with(2.5)

    @pytest.mark.asyncio
    @patch("arxiv_mcp.capabilities.arxiv_base.asyncio.sleep", new_callable=AsyncMock)
    async def test_non_429_status_is_not_retried(self, mock_sleep):
        """A non-429 error fails immediately -- only 429 is treated as transient."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            error_response = MagicMock()
            error_response.status_code = 500

            from httpx import HTTPStatusError, Request

            error_response.raise_for_status.side_effect = HTTPStatusError(
                "Server Error",
                request=MagicMock(spec=Request),
                response=error_response,
            )
            mock_client.get.return_value = error_response
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = None

            with pytest.raises(Exception, match="ArXiv API error: 500"):
                await execute_arxiv_query({"search_query": "test", "max_results": 1})

            assert mock_client.get.call_count == 1
            mock_sleep.assert_not_awaited()

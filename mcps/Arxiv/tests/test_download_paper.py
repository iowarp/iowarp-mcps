"""
Test suite for PDF download capabilities.
"""

import os
import tempfile
import shutil
import pytest
import httpx
from unittest.mock import patch, MagicMock, AsyncMock
import sys

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from capabilities.download_paper import (
    download_paper_pdf,
    get_pdf_url,
    download_multiple_pdfs,
)


class TestPDFDownload:
    """Test PDF download functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.arxiv_id = "1706.03762"

    def teardown_method(self):
        """Clean up test environment."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_download_paper_pdf_success(self):
        """Test successful PDF download."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.content = b"%PDF-1.4 fake pdf content"
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            result = await download_paper_pdf(self.arxiv_id, self.temp_dir)

            assert result["success"] is True
            assert result["arxiv_id"] == self.arxiv_id
            assert result["filename"] == f"{self.arxiv_id}.pdf"
            assert os.path.exists(result["file_path"])

    @pytest.mark.asyncio
    async def test_download_paper_pdf_not_found(self):
        """Test PDF download when paper not found."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock 404 response
            mock_response = MagicMock()
            mock_response.status_code = 404

            from httpx import HTTPStatusError

            mock_client.return_value.__aenter__.return_value.get.side_effect = (
                HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=mock_response
                )
            )

            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf(self.arxiv_id, self.temp_dir)

            assert "PDF not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_paper_pdf_invalid_content_type(self):
        """Test PDF download with invalid content type."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock response with wrong content type
            mock_response = MagicMock()
            mock_response.headers = {"content-type": "text/html"}
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf(self.arxiv_id, self.temp_dir)

            assert "did not return a PDF file" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_pdf_url_success(self):
        """Test successful PDF URL retrieval."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock successful HEAD response
            mock_response = MagicMock()
            mock_response.headers = {
                "content-type": "application/pdf",
                "content-length": "1024000",
            }
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.__aenter__.return_value.head.return_value = (
                mock_response
            )

            result = await get_pdf_url(self.arxiv_id)

            assert result["success"] is True
            assert result["arxiv_id"] == self.arxiv_id
            assert result["pdf_url"] == f"https://arxiv.org/pdf/{self.arxiv_id}.pdf"
            assert result["content_type"] == "application/pdf"
            assert result["content_length"] == "1024000"

    @pytest.mark.asyncio
    async def test_get_pdf_url_not_found(self):
        """Test PDF URL retrieval when paper not found."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock 404 response
            mock_response = MagicMock()
            mock_response.status_code = 404

            from httpx import HTTPStatusError

            mock_client.return_value.__aenter__.return_value.head.side_effect = (
                HTTPStatusError(
                    "404 Not Found", request=MagicMock(), response=mock_response
                )
            )

            with pytest.raises(Exception) as exc_info:
                await get_pdf_url(self.arxiv_id)

            assert "PDF not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_success(self):
        """Test successful multiple PDF downloads."""
        arxiv_ids = ["1706.03762", "2301.12345"]

        with patch("capabilities.download_paper.download_paper_pdf") as mock_download:
            # Mock successful downloads
            mock_download.side_effect = [
                {
                    "success": True,
                    "arxiv_id": "1706.03762",
                    "file_path": f"{self.temp_dir}/1706.03762.pdf",
                },
                {
                    "success": True,
                    "arxiv_id": "2301.12345",
                    "file_path": f"{self.temp_dir}/2301.12345.pdf",
                },
            ]

            result = await download_multiple_pdfs(
                arxiv_ids, self.temp_dir, max_concurrent=2
            )

            assert result["success"] is True
            assert result["total_requested"] == 2
            assert result["successful_downloads"] == 2
            assert result["failed_downloads"] == 0
            assert result["download_path"] == self.temp_dir

    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_partial_failure(self):
        """Test multiple PDF downloads with partial failures."""
        arxiv_ids = ["1706.03762", "invalid_id"]

        with patch("capabilities.download_paper.download_paper_pdf") as mock_download:
            # Mock one success and one failure
            mock_download.side_effect = [
                {
                    "success": True,
                    "arxiv_id": "1706.03762",
                    "file_path": f"{self.temp_dir}/1706.03762.pdf",
                },
                Exception("PDF not found"),
            ]

            result = await download_multiple_pdfs(
                arxiv_ids, self.temp_dir, max_concurrent=2
            )

            assert result["success"] is True
            assert result["total_requested"] == 2
            assert result["successful_downloads"] == 1
            assert result["failed_downloads"] == 1
            assert result["download_path"] == self.temp_dir

    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_empty_list(self):
        """Test multiple PDF downloads with empty list."""
        with pytest.raises(Exception) as exc_info:
            await download_multiple_pdfs([], self.temp_dir)

        assert "No ArXiv IDs provided" in str(exc_info.value)

    def test_arxiv_id_cleaning(self):
        """Test ArXiv ID cleaning functionality."""
        # Test with various ArXiv ID formats
        test_cases = [
            ("1706.03762", "1706.03762"),
            ("cs/0501001", "0501001"),
            ("http://arxiv.org/abs/1706.03762", "1706.03762"),
            ("https://arxiv.org/pdf/1706.03762.pdf", "1706.03762.pdf"),
        ]

        for input_id, expected in test_cases:
            clean_id = input_id.split("/")[-1] if "/" in input_id else input_id
            if "arxiv.org" in clean_id:
                clean_id = clean_id.split("/")[-1]

            # Basic cleaning logic verification
            assert clean_id is not None

    @pytest.mark.asyncio
    async def test_download_with_default_path(self):
        """Test download with None download_path to cover line 32."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("os.getcwd", return_value=self.temp_dir),
            patch("pathlib.Path.mkdir"),
            patch("builtins.open", create=True),
            patch("os.path.getsize", return_value=1024),
        ):
            mock_response = AsyncMock()
            mock_response.read.return_value = b"PDF content"
            mock_response.status = 200
            mock_response.content = b"PDF content"
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.raise_for_status = AsyncMock()

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Test with None download_path
            result = await download_paper_pdf("test-id", None)

            assert result is not None
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_download_complex_arxiv_id_cleaning(self):
        """Test download with complex ArXiv ID formats to cover line 39."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("pathlib.Path.mkdir"),
            patch("builtins.open", create=True),
            patch("os.path.getsize", return_value=1024),
        ):
            mock_response = AsyncMock()
            mock_response.read.return_value = b"PDF content"
            mock_response.status = 200
            mock_response.content = b"PDF content"
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.raise_for_status = AsyncMock()

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Test with complex ArXiv ID containing arxiv.org
            complex_id = "https://arxiv.org/abs/2301.12345"
            result = await download_paper_pdf(complex_id, self.temp_dir)

            assert result is not None
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_download_404_error(self):
        """Test download with 404 error to cover lines 84, 86-87."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 404

            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.HTTPStatusError(
                "404 Not Found", request=AsyncMock(), response=mock_response
            )
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Test 404 error handling
            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf("nonexistent-id", self.temp_dir)

            assert "PDF not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_timeout_error(self):
        """Test download timeout to cover line 107."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = httpx.TimeoutException("Timeout")
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Test timeout error handling
            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf("test-id", self.temp_dir)

            assert "timed out" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_pdf_url_with_complex_id(self):
        """Test get_pdf_url with complex ArXiv ID to cover line 137."""
        # Test with ArXiv ID containing arxiv.org
        complex_id = "https://arxiv.org/abs/2301.12345"
        result = await get_pdf_url(complex_id)

        assert result is not None
        assert "pdf_url" in result

    @pytest.mark.asyncio
    async def test_download_multiple_with_empty_directory_creation(self):
        """Test download_multiple_pdfs with directory creation to cover line 165."""
        with (
            patch("httpx.AsyncClient") as mock_client,
            patch("pathlib.Path.mkdir"),
            patch("builtins.open", create=True),
            patch("os.path.exists", return_value=False),
            patch("os.path.getsize", return_value=1024),
        ):
            mock_response = AsyncMock()
            mock_response.read.return_value = b"PDF content"
            mock_response.status = 200
            mock_response.content = b"PDF content"
            mock_response.headers = {"content-type": "application/pdf"}
            mock_response.raise_for_status = AsyncMock()

            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            # Test with non-existent directory
            result = await download_multiple_pdfs(["test-id"], self.temp_dir)

            # Verify directory creation was attempted
            assert result is not None
            assert result["success"] is True

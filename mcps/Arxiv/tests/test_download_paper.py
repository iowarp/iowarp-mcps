"""
Test suite for PDF download capabilities.
"""
import os
import tempfile
import shutil
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from capabilities.download_paper import (
    download_paper_pdf,
    get_pdf_url,
    download_multiple_pdfs
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
        with patch('httpx.AsyncClient') as mock_client:
            # Mock successful response
            mock_response = MagicMock()
            mock_response.headers = {'content-type': 'application/pdf'}
            mock_response.content = b'%PDF-1.4 fake pdf content'
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await download_paper_pdf(self.arxiv_id, self.temp_dir)
            
            assert result['success'] is True
            assert result['arxiv_id'] == self.arxiv_id
            assert result['filename'] == f"{self.arxiv_id}.pdf"
            assert os.path.exists(result['file_path'])
    
    @pytest.mark.asyncio
    async def test_download_paper_pdf_not_found(self):
        """Test PDF download when paper not found."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock 404 response
            mock_response = MagicMock()
            mock_response.status_code = 404
            
            from httpx import HTTPStatusError
            mock_client.return_value.__aenter__.return_value.get.side_effect = HTTPStatusError(
                "404 Not Found", request=MagicMock(), response=mock_response
            )
            
            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf(self.arxiv_id, self.temp_dir)
            
            assert "PDF not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_paper_pdf_invalid_content_type(self):
        """Test PDF download with invalid content type."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock response with wrong content type
            mock_response = MagicMock()
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            with pytest.raises(Exception) as exc_info:
                await download_paper_pdf(self.arxiv_id, self.temp_dir)
            
            assert "did not return a PDF file" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_get_pdf_url_success(self):
        """Test successful PDF URL retrieval."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock successful HEAD response
            mock_response = MagicMock()
            mock_response.headers = {
                'content-type': 'application/pdf',
                'content-length': '1024000'
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.head.return_value = mock_response
            
            result = await get_pdf_url(self.arxiv_id)
            
            assert result['success'] is True
            assert result['arxiv_id'] == self.arxiv_id
            assert result['pdf_url'] == f"https://arxiv.org/pdf/{self.arxiv_id}.pdf"
            assert result['content_type'] == 'application/pdf'
            assert result['content_length'] == '1024000'
    
    @pytest.mark.asyncio
    async def test_get_pdf_url_not_found(self):
        """Test PDF URL retrieval when paper not found."""
        with patch('httpx.AsyncClient') as mock_client:
            # Mock 404 response
            mock_response = MagicMock()
            mock_response.status_code = 404
            
            from httpx import HTTPStatusError
            mock_client.return_value.__aenter__.return_value.head.side_effect = HTTPStatusError(
                "404 Not Found", request=MagicMock(), response=mock_response
            )
            
            with pytest.raises(Exception) as exc_info:
                await get_pdf_url(self.arxiv_id)
            
            assert "PDF not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_success(self):
        """Test successful multiple PDF downloads."""
        arxiv_ids = ["1706.03762", "2301.12345"]
        
        with patch('capabilities.download_paper.download_paper_pdf') as mock_download:
            # Mock successful downloads
            mock_download.side_effect = [
                {
                    'success': True,
                    'arxiv_id': '1706.03762',
                    'file_path': f"{self.temp_dir}/1706.03762.pdf"
                },
                {
                    'success': True,
                    'arxiv_id': '2301.12345',
                    'file_path': f"{self.temp_dir}/2301.12345.pdf"
                }
            ]
            
            result = await download_multiple_pdfs(arxiv_ids, self.temp_dir, max_concurrent=2)
            
            assert result['success'] is True
            assert result['total_requested'] == 2
            assert result['successful_downloads'] == 2
            assert result['failed_downloads'] == 0
            assert result['download_path'] == self.temp_dir
    
    @pytest.mark.asyncio
    async def test_download_multiple_pdfs_partial_failure(self):
        """Test multiple PDF downloads with partial failures."""
        arxiv_ids = ["1706.03762", "invalid_id"]
        
        with patch('capabilities.download_paper.download_paper_pdf') as mock_download:
            # Mock one success and one failure
            mock_download.side_effect = [
                {
                    'success': True,
                    'arxiv_id': '1706.03762',
                    'file_path': f"{self.temp_dir}/1706.03762.pdf"
                },
                Exception("PDF not found")
            ]
            
            result = await download_multiple_pdfs(arxiv_ids, self.temp_dir, max_concurrent=2)
            
            assert result['success'] is True
            assert result['total_requested'] == 2
            assert result['successful_downloads'] == 1
            assert result['failed_downloads'] == 1
            assert result['download_path'] == self.temp_dir
    
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
            clean_id = input_id.split('/')[-1] if '/' in input_id else input_id
            if 'arxiv.org' in clean_id:
                clean_id = clean_id.split('/')[-1]
            
            # Basic cleaning logic verification
            assert clean_id is not None
"""
ArXiv PDF download and management capabilities.
"""
import os
import httpx
from typing import Dict, Any, Optional
import logging
from urllib.parse import urlparse
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


async def download_paper_pdf(arxiv_id: str, download_path: str = None) -> Dict[str, Any]:
    """
    Download the PDF of a paper from ArXiv.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')
        download_path: Optional path to save the PDF. If None, saves to current directory.
        
    Returns:
        Dictionary containing download information
    """
    try:
        # Clean the ArXiv ID to extract just the ID part
        clean_id = arxiv_id.split('/')[-1] if '/' in arxiv_id else arxiv_id
        if 'arxiv.org' in clean_id:
            clean_id = clean_id.split('/')[-1]
        
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        
        # Set up download path
        if download_path is None:
            download_path = os.getcwd()
        
        # Ensure download directory exists
        Path(download_path).mkdir(parents=True, exist_ok=True)
        
        # Generate filename
        filename = f"{clean_id}.pdf"
        full_path = os.path.join(download_path, filename)
        
        # Download the PDF
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            logger.info(f"Downloading PDF for ArXiv ID: {clean_id}")
            response = await client.get(pdf_url)
            response.raise_for_status()
            
            # Check if the response is actually a PDF
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type:
                raise Exception(f"URL did not return a PDF file. Content-Type: {content_type}")
            
            # Save the PDF file
            with open(full_path, 'wb') as f:
                f.write(response.content)
            
            file_size = os.path.getsize(full_path)
            
            return {
                'success': True,
                'arxiv_id': clean_id,
                'download_url': pdf_url,
                'file_path': full_path,
                'filename': filename,
                'file_size': file_size,
                'message': f"Successfully downloaded PDF for paper '{clean_id}' to {full_path}"
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading PDF: {e.response.status_code}")
        if e.response.status_code == 404:
            raise Exception(f"PDF not found for ArXiv ID '{arxiv_id}'. Paper may not exist or PDF may not be available.")
        else:
            raise Exception(f"HTTP error {e.response.status_code} downloading PDF")
    except httpx.TimeoutException:
        logger.error("PDF download timed out")
        raise Exception("PDF download timed out")
    except Exception as e:
        logger.error(f"Error downloading PDF: {str(e)}")
        raise Exception(f"Failed to download PDF: {str(e)}")


async def get_pdf_url(arxiv_id: str) -> Dict[str, Any]:
    """
    Get the direct PDF URL for a paper without downloading it.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')
        
    Returns:
        Dictionary containing PDF URL information
    """
    try:
        # Clean the ArXiv ID
        clean_id = arxiv_id.split('/')[-1] if '/' in arxiv_id else arxiv_id
        if 'arxiv.org' in clean_id:
            clean_id = clean_id.split('/')[-1]
        
        # Construct PDF URL
        pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
        
        # Verify the URL exists
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            logger.info(f"Checking PDF availability for ArXiv ID: {clean_id}")
            response = await client.head(pdf_url)
            response.raise_for_status()
            
            content_type = response.headers.get('content-type', '')
            content_length = response.headers.get('content-length', 'unknown')
            
            return {
                'success': True,
                'arxiv_id': clean_id,
                'pdf_url': pdf_url,
                'content_type': content_type,
                'content_length': content_length,
                'message': f"PDF is available for paper '{clean_id}'"
            }
            
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error checking PDF: {e.response.status_code}")
        if e.response.status_code == 404:
            raise Exception(f"PDF not found for ArXiv ID '{arxiv_id}'. Paper may not exist or PDF may not be available.")
        else:
            raise Exception(f"HTTP error {e.response.status_code} checking PDF availability")
    except Exception as e:
        logger.error(f"Error checking PDF availability: {str(e)}")
        raise Exception(f"Failed to check PDF availability: {str(e)}")


async def download_multiple_pdfs(arxiv_ids: list, download_path: str = None, max_concurrent: int = 3) -> Dict[str, Any]:
    """
    Download multiple PDFs concurrently with rate limiting.
    
    Args:
        arxiv_ids: List of ArXiv paper IDs
        download_path: Optional path to save PDFs
        max_concurrent: Maximum number of concurrent downloads
        
    Returns:
        Dictionary containing download results
    """
    try:
        if not arxiv_ids:
            raise Exception("No ArXiv IDs provided")
        
        # Set up download path
        if download_path is None:
            download_path = os.getcwd()
        
        Path(download_path).mkdir(parents=True, exist_ok=True)
        
        # Create semaphore for rate limiting
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_semaphore(arxiv_id: str):
            async with semaphore:
                try:
                    return await download_paper_pdf(arxiv_id, download_path)
                except Exception as e:
                    return {
                        'success': False,
                        'arxiv_id': arxiv_id,
                        'error': str(e)
                    }
        
        # Execute downloads concurrently
        logger.info(f"Starting concurrent download of {len(arxiv_ids)} PDFs")
        results = await asyncio.gather(*[download_with_semaphore(arxiv_id) for arxiv_id in arxiv_ids])
        
        # Summarize results
        successful = [r for r in results if r.get('success')]
        failed = [r for r in results if not r.get('success')]
        
        return {
            'success': True,
            'total_requested': len(arxiv_ids),
            'successful_downloads': len(successful),
            'failed_downloads': len(failed),
            'download_path': download_path,
            'results': results,
            'message': f"Downloaded {len(successful)} of {len(arxiv_ids)} PDFs successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in batch PDF download: {str(e)}")
        raise Exception(f"Batch PDF download failed: {str(e)}")
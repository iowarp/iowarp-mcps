"""
MCP handlers for ArXiv research paper search and retrieval.
These handlers wrap the ArXiv capabilities for MCP protocol compliance.
"""

import json
from typing import Dict, Any, Optional
from capabilities.category_search import (
    search_arxiv,
    get_recent_papers,
    search_by_subject,
)
from capabilities.text_search import (
    search_by_title,
    search_by_abstract,
    search_papers_by_author,
)
from capabilities.date_search import search_date_range
from capabilities.paper_details import get_paper_details, find_similar_papers
from capabilities.export_utils import export_to_bibtex
from capabilities.download_paper import (
    download_paper_pdf,
    get_pdf_url,
    download_multiple_pdfs,
)


async def search_arxiv_handler(
    query: str = "cs.AI", max_results: int = 5
) -> Dict[str, Any]:
    """
    Handler wrapping the ArXiv search capability for MCP.
    Returns search results or an error payload on failure.

    Args:
        query: Search query or category
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_arxiv(query, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_arxiv", "error": type(e).__name__},
            "isError": True,
        }


async def get_recent_papers_handler(
    category: str = "cs.AI", max_results: int = 5
) -> Dict[str, Any]:
    """
    Handler wrapping the recent papers capability for MCP.
    Returns recent papers or an error payload on failure.

    Args:
        category: ArXiv category
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await get_recent_papers(category, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "get_recent_papers", "error": type(e).__name__},
            "isError": True,
        }


async def search_papers_by_author_handler(
    author: str, max_results: int = 10
) -> Dict[str, Any]:
    """
    Handler wrapping the author search capability for MCP.
    Returns author's papers or an error payload on failure.

    Args:
        author: Author name to search for
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_papers_by_author(author, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_papers_by_author", "error": type(e).__name__},
            "isError": True,
        }


async def search_by_title_handler(
    title_keywords: str, max_results: int = 10
) -> Dict[str, Any]:
    """
    Handler wrapping the title search capability for MCP.
    Returns papers matching title keywords or an error payload on failure.

    Args:
        title_keywords: Keywords to search in paper titles
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_by_title(title_keywords, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_by_title", "error": type(e).__name__},
            "isError": True,
        }


async def search_by_abstract_handler(
    abstract_keywords: str, max_results: int = 10
) -> Dict[str, Any]:
    """
    Handler wrapping the abstract search capability for MCP.
    Returns papers matching abstract keywords or an error payload on failure.

    Args:
        abstract_keywords: Keywords to search in paper abstracts
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_by_abstract(abstract_keywords, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_by_abstract", "error": type(e).__name__},
            "isError": True,
        }


async def search_by_subject_handler(
    subject: str, max_results: int = 10
) -> Dict[str, Any]:
    """
    Handler wrapping the subject search capability for MCP.
    Returns papers from specified subject or an error payload on failure.

    Args:
        subject: ArXiv subject classification
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_by_subject(subject, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_by_subject", "error": type(e).__name__},
            "isError": True,
        }


async def search_date_range_handler(
    start_date: str, end_date: str, category: str = "", max_results: int = 20
) -> Dict[str, Any]:
    """
    Handler wrapping the date range search capability for MCP.
    Returns papers from specified date range or an error payload on failure.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        category: Optional category filter
        max_results: Maximum number of results to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await search_date_range(start_date, end_date, category, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "search_date_range", "error": type(e).__name__},
            "isError": True,
        }


async def get_paper_details_handler(arxiv_id: str) -> Dict[str, Any]:
    """
    Handler wrapping the paper details capability for MCP.
    Returns detailed paper information or an error payload on failure.

    Args:
        arxiv_id: ArXiv paper ID

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await get_paper_details(arxiv_id)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "get_paper_details", "error": type(e).__name__},
            "isError": True,
        }


async def export_to_bibtex_handler(papers_json: str) -> Dict[str, Any]:
    """
    Handler wrapping the BibTeX export capability for MCP.
    Returns BibTeX citations or an error payload on failure.

    Args:
        papers_json: JSON string containing list of papers

    Returns:
        MCP-compliant response dictionary
    """
    try:
        # Parse the JSON string to get the papers list
        papers = json.loads(papers_json)
        if not isinstance(papers, list):
            raise ValueError("Expected a list of papers")

        result = await export_to_bibtex(papers)
        return result
    except json.JSONDecodeError as e:
        return {
            "content": [
                {"text": json.dumps({"error": f"Invalid JSON format: {str(e)}"})}
            ],
            "_meta": {"tool": "export_to_bibtex", "error": "JSONDecodeError"},
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "export_to_bibtex", "error": type(e).__name__},
            "isError": True,
        }


async def find_similar_papers_handler(
    reference_paper_id: str, max_results: int = 10
) -> Dict[str, Any]:
    """
    Handler wrapping the similar papers capability for MCP.
    Returns similar papers or an error payload on failure.

    Args:
        reference_paper_id: ArXiv ID of the reference paper
        max_results: Maximum number of similar papers to return

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await find_similar_papers(reference_paper_id, max_results)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "find_similar_papers", "error": type(e).__name__},
            "isError": True,
        }


async def download_paper_pdf_handler(
    arxiv_id: str, download_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handler wrapping the PDF download capability for MCP.
    Downloads the PDF of a paper and returns download information.

    Args:
        arxiv_id: ArXiv paper ID
        download_path: Optional path to save the PDF

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await download_paper_pdf(arxiv_id, download_path)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "download_paper_pdf", "error": type(e).__name__},
            "isError": True,
        }


async def get_pdf_url_handler(arxiv_id: str) -> Dict[str, Any]:
    """
    Handler wrapping the PDF URL retrieval capability for MCP.
    Gets the direct PDF URL without downloading.

    Args:
        arxiv_id: ArXiv paper ID

    Returns:
        MCP-compliant response dictionary
    """
    try:
        result = await get_pdf_url(arxiv_id)
        return result
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "get_pdf_url", "error": type(e).__name__},
            "isError": True,
        }


async def download_multiple_pdfs_handler(
    arxiv_ids_json: str, download_path: Optional[str] = None, max_concurrent: int = 3
) -> Dict[str, Any]:
    """
    Handler wrapping the multiple PDF download capability for MCP.
    Downloads multiple PDFs concurrently with rate limiting.

    Args:
        arxiv_ids_json: JSON string containing list of ArXiv IDs
        download_path: Optional path to save PDFs
        max_concurrent: Maximum number of concurrent downloads

    Returns:
        MCP-compliant response dictionary
    """
    try:
        # Parse the JSON string to get the ArXiv IDs list
        arxiv_ids = json.loads(arxiv_ids_json)
        if not isinstance(arxiv_ids, list):
            raise ValueError("Expected a list of ArXiv IDs")

        result = await download_multiple_pdfs(arxiv_ids, download_path, max_concurrent)
        return result
    except json.JSONDecodeError as e:
        return {
            "content": [
                {"text": json.dumps({"error": f"Invalid JSON format: {str(e)}"})}
            ],
            "_meta": {"tool": "download_multiple_pdfs", "error": "JSONDecodeError"},
            "isError": True,
        }
    except Exception as e:
        return {
            "content": [{"text": json.dumps({"error": str(e)})}],
            "_meta": {"tool": "download_multiple_pdfs", "error": type(e).__name__},
            "isError": True,
        }

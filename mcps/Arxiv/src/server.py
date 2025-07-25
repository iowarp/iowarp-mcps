#!/usr/bin/env python3
"""
ArXiv MCP Server implementation using Model Context Protocol.
Provides access to ArXiv research papers through search and retrieval tools.
"""

import os
import sys
import json
from fastmcp import FastMCP
from dotenv import load_dotenv
import logging
from typing import Optional
import mcp_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add current directory to path for relative imports
sys.path.insert(0, os.path.dirname(__file__))

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP("ArxivMCP")


@mcp.tool(
    name="search_arxiv",
    description="Search ArXiv for research papers by category or topic.",
)
async def search_arxiv_tool(query: str = "cs.AI", max_results: int = 5) -> dict:
    """
    Search ArXiv for research papers by category or topic with comprehensive filtering and ranking capabilities.

    Args:
        query (str, optional): Search query or category (default: "cs.AI")
        max_results (int, optional): Maximum number of results to return (default: 5)

    Returns:
        Dictionary with search results including paper metadata, abstracts, and ArXiv identifiers.
    """
    logger.info(f"Searching ArXiv for query: {query}")
    return await mcp_handlers.search_arxiv_handler(query, max_results)


@mcp.tool(
    name="get_recent_papers",
    description="Get recent papers from a specific ArXiv category.",
)
async def get_recent_papers_tool(category: str = "cs.AI", max_results: int = 5) -> dict:
    """
    Get recent papers from a specific ArXiv category with chronological ordering and metadata extraction.

    Args:
        category (str, optional): ArXiv category (default: "cs.AI")
        max_results (int, optional): Maximum number of results to return (default: 5)

    Returns:
        Dictionary with recent papers including publication dates, authors, and paper summaries.
    """
    logger.info(f"Getting recent papers from category: {category}")
    return await mcp_handlers.get_recent_papers_handler(category, max_results)


@mcp.tool(
    name="search_papers_by_author", description="Search ArXiv papers by author name."
)
async def search_papers_by_author_tool(author: str, max_results: int = 10) -> dict:
    """
    Search ArXiv papers by author name with comprehensive author matching and publication history.

    Args:
        author (str): Author name to search for
        max_results (int, optional): Maximum number of results to return (default: 10)

    Returns:
        Dictionary with author's papers including co-authors, publication timeline, and research areas.
    """
    logger.info(f"Searching papers by author: {author}")
    return await mcp_handlers.search_papers_by_author_handler(author, max_results)


@mcp.tool(name="search_by_title", description="Search ArXiv papers by title keywords.")
async def search_by_title_tool(title_keywords: str, max_results: int = 10) -> dict:
    """
    Search ArXiv papers by title keywords with intelligent keyword matching and relevance scoring.

    Args:
        title_keywords (str): Keywords to search in paper titles
        max_results (int, optional): Maximum number of results to return (default: 10)

    Returns:
        Dictionary with search results ranked by title relevance and keyword matching.
    """
    logger.info(f"Searching papers by title: {title_keywords}")
    return await mcp_handlers.search_by_title_handler(title_keywords, max_results)


@mcp.tool(
    name="search_by_abstract", description="Search ArXiv papers by abstract keywords."
)
async def search_by_abstract_tool(
    abstract_keywords: str, max_results: int = 10
) -> dict:
    """
    Search ArXiv papers by abstract keywords with semantic content analysis and relevance ranking.

    Args:
        abstract_keywords (str): Keywords to search in paper abstracts
        max_results (int, optional): Maximum number of results to return (default: 10)

    Returns:
        Dictionary with papers matching abstract content with relevance scores and keyword highlights.
    """
    logger.info(f"Searching papers by abstract: {abstract_keywords}")
    return await mcp_handlers.search_by_abstract_handler(abstract_keywords, max_results)


@mcp.tool(
    name="search_by_subject",
    description="Search ArXiv papers by subject classification.",
)
async def search_by_subject_tool(subject: str, max_results: int = 10) -> dict:
    """
    Search ArXiv papers by subject classification with comprehensive category-based filtering.

    Args:
        subject (str): ArXiv subject classification (e.g., 'cs.AI', 'physics.astro-ph')
        max_results (int, optional): Maximum number of results to return (default: 10)

    Returns:
        Dictionary with papers from specified subject areas with classification metadata.
    """
    logger.info(f"Searching papers by subject: {subject}")
    return await mcp_handlers.search_by_subject_handler(subject, max_results)


@mcp.tool(
    name="search_date_range",
    description="Search ArXiv papers within a specific date range.",
)
async def search_date_range_tool(
    start_date: str, end_date: str, category: str = "", max_results: int = 20
) -> dict:
    """
    Search ArXiv papers within a specific date range with optional category filtering and chronological organization.

    Args:
        start_date (str): Start date in YYYY-MM-DD format
        end_date (str): End date in YYYY-MM-DD format
        category (str, optional): Optional category filter (e.g., 'cs.AI')
        max_results (int, optional): Maximum number of results to return (default: 20)

    Returns:
        Dictionary with papers published within date range with temporal metadata and category information.
    """
    logger.info(f"Searching papers by date range: {start_date} to {end_date}")
    return await mcp_handlers.search_date_range_handler(
        start_date, end_date, category, max_results
    )


@mcp.tool(
    name="get_paper_details",
    description="Get detailed information about a specific ArXiv paper by ID.",
)
async def get_paper_details_tool(arxiv_id: str) -> dict:
    """
    Get detailed information about a specific ArXiv paper by ID with comprehensive metadata extraction.

    Args:
        arxiv_id (str): ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')

    Returns:
        Dictionary with detailed paper information including full abstract, authors, categories, and publication data.
    """
    logger.info(f"Getting paper details for: {arxiv_id}")
    return await mcp_handlers.get_paper_details_handler(arxiv_id)


@mcp.tool(
    name="export_to_bibtex",
    description="Export search results to BibTeX format for citation management.",
)
async def export_to_bibtex_tool(papers_json: str) -> dict:
    """
    Export search results to BibTeX format for citation management and bibliography generation.

    Args:
        papers_json (str): JSON string containing list of papers to export

    Returns:
        Dictionary with BibTeX citations properly formatted for academic reference management.
    """
    logger.info("Exporting papers to BibTeX format")
    return await mcp_handlers.export_to_bibtex_handler(papers_json)


@mcp.tool(
    name="find_similar_papers",
    description="Find papers similar to a reference paper based on categories and keywords.",
)
async def find_similar_papers_tool(
    reference_paper_id: str, max_results: int = 10
) -> dict:
    """
    Find papers similar to a reference paper based on categories, keywords, and content analysis.

    Args:
        reference_paper_id (str): ArXiv ID of the reference paper
        max_results (int, optional): Maximum number of similar papers to return (default: 10)

    Returns:
        Dictionary with similar papers ranked by relevance with similarity scores and matching criteria.
    """
    logger.info(f"Finding papers similar to: {reference_paper_id}")
    return await mcp_handlers.find_similar_papers_handler(
        reference_paper_id, max_results
    )


@mcp.tool(
    name="download_paper_pdf", description="Download the PDF of a paper from ArXiv."
)
async def download_paper_pdf_tool(
    arxiv_id: str, download_path: Optional[str] = None
) -> dict:
    """
    Download the PDF of a paper from ArXiv with automatic file management and error handling.

    Args:
        arxiv_id (str): ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')
        download_path (str, optional): Optional path to save the PDF

    Returns:
        Dictionary with download information.
    """
    logger.info(f"Downloading PDF for paper: {arxiv_id}")
    return await mcp_handlers.download_paper_pdf_handler(arxiv_id, download_path)


@mcp.tool(
    name="get_pdf_url",
    description="Get the direct PDF URL for a paper without downloading.",
)
async def get_pdf_url_tool(arxiv_id: str) -> dict:
    """
    Get PDF URL for an ArXiv paper.

    Args:
        arxiv_id: ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')

    Returns:
        Dictionary with PDF URL information
    """
    logger.info(f"Getting PDF URL for paper: {arxiv_id}")
    return await mcp_handlers.get_pdf_url_handler(arxiv_id)


@mcp.tool(
    name="download_multiple_pdfs",
    description="Download multiple PDFs concurrently with rate limiting.",
)
async def download_multiple_pdfs_tool(
    arxiv_ids_json: str, download_path: str | None = None, max_concurrent: int = 3
) -> dict:
    """
    Download multiple PDFs concurrently.

    Args:
        arxiv_ids_json: JSON string containing list of ArXiv IDs
        download_path: Optional path to save PDFs
        max_concurrent: Maximum number of concurrent downloads

    Returns:
        Dictionary with download results
    """
    logger.info(f"Downloading multiple PDFs with max_concurrent: {max_concurrent}")
    return await mcp_handlers.download_multiple_pdfs_handler(
        arxiv_ids_json, download_path, max_concurrent
    )


def main():
    """
    Main entry point for the ArXiv MCP server.
    Supports both stdio and SSE transports based on environment variables.
    """
    try:
        logger.info("Starting ArXiv MCP Server")

        # Determine which transport to use
        transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
        if transport == "sse":
            # SSE transport for web-based clients
            host = os.getenv("MCP_SSE_HOST", "0.0.0.0")
            port = int(os.getenv("MCP_SSE_PORT", "8000"))
            logger.info(f"Starting SSE transport on {host}:{port}")
            print(
                json.dumps({"message": f"Starting SSE on {host}:{port}"}),
                file=sys.stderr,
            )
            mcp.run(transport="sse", host=host, port=port)
        else:
            # Default stdio transport
            logger.info("Starting stdio transport")
            print(json.dumps({"message": "Starting stdio transport"}), file=sys.stderr)
            mcp.run(transport="stdio")

    except Exception as e:
        logger.error(f"Server error: {e}")
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

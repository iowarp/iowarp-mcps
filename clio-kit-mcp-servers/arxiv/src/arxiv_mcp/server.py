#!/usr/bin/env python3
"""
ArXiv MCP Server implementation using Model Context Protocol.
Provides access to ArXiv research papers through search and retrieval tools.
"""

import os
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.prompts import Message
from dotenv import load_dotenv
import logging
from typing import Optional
from . import mcp_handlers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MCP server
mcp: FastMCP = FastMCP(
    "arxiv",
    instructions=(
        "Searches and retrieves academic papers from arXiv. "
        "Search by keyword, author, title, or subject. Fetch paper details and abstracts."
    ),
    list_page_size=10,
)

_READONLY_ANNOTATIONS = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
}


@mcp.tool(
    name="search_arxiv",
    title="search(papers)",
    description="Search ArXiv for papers by category or topic.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_arxiv_tool(query: str = "cs.AI", max_results: int = 5) -> dict:
    """Search ArXiv for research papers by category or topic."""
    logger.info(f"Searching ArXiv for query: {query}")
    try:
        return await mcp_handlers.search_arxiv_handler(query, max_results)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_recent_papers",
    title="recent(papers)",
    description="Get recent papers from a specific ArXiv category.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "papers"},
)
async def get_recent_papers_tool(category: str = "cs.AI", max_results: int = 5) -> dict:
    """Get recent papers from a specific ArXiv category."""
    logger.info(f"Getting recent papers from category: {category}")
    try:
        return await mcp_handlers.get_recent_papers_handler(category, max_results)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_papers_by_author",
    title="search(author)",
    description="Search ArXiv papers by author name.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_papers_by_author_tool(author: str, max_results: int = 10) -> dict:
    """Search ArXiv papers by author name."""
    logger.info(f"Searching papers by author: {author}")
    try:
        return await mcp_handlers.search_papers_by_author_handler(author, max_results)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_by_title",
    title="search(title)",
    description="Search ArXiv papers by title keywords.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_by_title_tool(title_keywords: str, max_results: int = 10) -> dict:
    """Search ArXiv papers by title keywords."""
    logger.info(f"Searching papers by title: {title_keywords}")
    try:
        return await mcp_handlers.search_by_title_handler(title_keywords, max_results)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_by_abstract",
    title="search(abstract)",
    description="Search ArXiv papers by abstract keywords.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_by_abstract_tool(
    abstract_keywords: str, max_results: int = 10
) -> dict:
    """Search ArXiv papers by abstract keywords."""
    logger.info(f"Searching papers by abstract: {abstract_keywords}")
    try:
        return await mcp_handlers.search_by_abstract_handler(
            abstract_keywords, max_results
        )
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_by_subject",
    title="search(subject)",
    description="Search ArXiv papers by subject classification.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_by_subject_tool(subject: str, max_results: int = 10) -> dict:
    """Search ArXiv papers by subject classification."""
    logger.info(f"Searching papers by subject: {subject}")
    try:
        return await mcp_handlers.search_by_subject_handler(subject, max_results)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="search_date_range",
    title="search(range)",
    description="Search ArXiv papers within a specific date range.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def search_date_range_tool(
    start_date: str, end_date: str, category: str = "", max_results: int = 20
) -> dict:
    """Search ArXiv papers within a date range, optionally filtered by category."""
    logger.info(f"Searching papers by date range: {start_date} to {end_date}")
    try:
        return await mcp_handlers.search_date_range_handler(
            start_date, end_date, category, max_results
        )
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_paper_details",
    title="get(paper)",
    description="Get detailed information about a specific ArXiv paper by ID.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "papers"},
)
async def get_paper_details_tool(arxiv_id: str) -> dict:
    """Get detailed information about a specific ArXiv paper by ID."""
    logger.info(f"Getting paper details for: {arxiv_id}")
    try:
        return await mcp_handlers.get_paper_details_handler(arxiv_id)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="export_to_bibtex",
    title="export(bibtex)",
    description="Export search results to BibTeX format for citation management.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "export"},
)
async def export_to_bibtex_tool(papers_json: str) -> dict:
    """Export search results to BibTeX format."""
    logger.info("Exporting papers to BibTeX format")
    try:
        return await mcp_handlers.export_to_bibtex_handler(papers_json)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="find_similar_papers",
    title="find(similar)",
    description="Find papers similar to a reference paper based on categories and keywords.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "search"},
)
async def find_similar_papers_tool(
    reference_paper_id: str, max_results: int = 10
) -> dict:
    """Find papers similar to a reference paper."""
    logger.info(f"Finding papers similar to: {reference_paper_id}")
    try:
        return await mcp_handlers.find_similar_papers_handler(
            reference_paper_id, max_results
        )
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="download_paper_pdf",
    title="download(pdf)",
    description="Download the PDF of a paper from ArXiv.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "download"},
)
async def download_paper_pdf_tool(
    arxiv_id: str, download_path: Optional[str] = None
) -> dict:
    """Download the PDF of a paper from ArXiv."""
    logger.info(f"Downloading PDF for paper: {arxiv_id}")
    try:
        return await mcp_handlers.download_paper_pdf_handler(arxiv_id, download_path)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="get_pdf_url",
    title="get(pdfurl)",
    description="Get the direct PDF URL for a paper without downloading.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "papers"},
)
async def get_pdf_url_tool(arxiv_id: str) -> dict:
    """Get the direct PDF URL for an ArXiv paper."""
    logger.info(f"Getting PDF URL for paper: {arxiv_id}")
    try:
        return await mcp_handlers.get_pdf_url_handler(arxiv_id)
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.tool(
    name="download_multiple_pdfs",
    title="download(many)",
    description="Download multiple PDFs concurrently with rate limiting.",
    annotations=_READONLY_ANNOTATIONS,
    tags={"arxiv", "download"},
)
async def download_multiple_pdfs_tool(
    arxiv_ids_json: str, download_path: str | None = None, max_concurrent: int = 3
) -> dict:
    """Download multiple PDFs concurrently."""
    logger.info(f"Downloading multiple PDFs with max_concurrent: {max_concurrent}")
    try:
        return await mcp_handlers.download_multiple_pdfs_handler(
            arxiv_ids_json, download_path, max_concurrent
        )
    except Exception as e:
        raise ToolError(str(e)) from e


@mcp.resource("arxiv://categories")
def arxiv_categories() -> dict:
    """Common arXiv subject categories and their descriptions."""
    return {
        "categories": {
            "cs.AI": "Artificial Intelligence",
            "cs.LG": "Machine Learning",
            "cs.CL": "Computation and Language",
            "physics.comp-ph": "Computational Physics",
            "math.NA": "Numerical Analysis",
            "stat.ML": "Machine Learning (Statistics)",
        }
    }


@mcp.prompt()
def literature_search(topic: str) -> list[Message]:
    """Guided workflow for conducting an arXiv literature search."""
    return [
        Message(
            f"I need to find recent papers on '{topic}'. "
            "Search arXiv, show the top 5 results with titles, authors, and abstracts, "
            "and highlight the most cited or recent paper."
        ),
    ]


def main() -> None:
    """Main entry point for the ArXiv MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="ArXiv MCP Server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    transport = args.transport or os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "http":
        mcp.run(transport="http", host=args.host, port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

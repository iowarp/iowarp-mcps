"""
ArXiv export and formatting utilities.
"""

from typing import Dict, Any, List
import logging
from .arxiv_base import generate_bibtex

logger = logging.getLogger(__name__)


async def export_to_bibtex(papers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Export a list of papers to BibTeX format.

    Args:
        papers: List of paper dictionaries

    Returns:
        Dictionary containing BibTeX citations
    """
    try:
        bibtex_entries = []
        for paper in papers:
            bibtex = generate_bibtex(paper)
            bibtex_entries.append(bibtex)

        combined_bibtex = "\n\n".join(bibtex_entries)

        return {
            "success": True,
            "bibtex": combined_bibtex,
            "paper_count": len(papers),
            "message": f"Successfully generated BibTeX for {len(papers)} papers",
        }

    except Exception as e:
        logger.error(f"Error generating BibTeX: {str(e)}")
        raise Exception(f"BibTeX generation failed: {str(e)}")


def format_paper_summary(paper: Dict[str, Any]) -> str:
    """
    Format a paper into a human-readable summary.

    Args:
        paper: Paper dictionary from ArXiv API

    Returns:
        Formatted string summary
    """
    title = paper.get("title", "Unknown Title")
    authors = ", ".join(paper.get("authors", []))
    published = paper.get("published", "")
    categories = ", ".join(paper.get("categories", []))
    arxiv_id = paper.get("id", "").split("/")[-1] if paper.get("id") else ""

    summary = f"""
Title: {title}
Authors: {authors}
Published: {published.split("T")[0] if published else "Unknown"}
Categories: {categories}
ArXiv ID: {arxiv_id}
Abstract: {paper.get("summary", "")[:200]}...
"""
    return summary.strip()


async def format_search_results(
    papers: List[Dict[str, Any]], query_info: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format search results into a structured response.

    Args:
        papers: List of paper dictionaries
        query_info: Information about the search query

    Returns:
        Formatted search results
    """
    try:
        formatted_papers = []
        for paper in papers:
            formatted_paper = {
                "title": paper.get("title", ""),
                "authors": paper.get("authors", []),
                "published": paper.get("published", ""),
                "categories": paper.get("categories", []),
                "arxiv_id": paper.get("id", "").split("/")[-1]
                if paper.get("id")
                else "",
                "summary": paper.get("summary", "")[:300] + "..."
                if len(paper.get("summary", "")) > 300
                else paper.get("summary", ""),
                "links": paper.get("links", []),
            }
            formatted_papers.append(formatted_paper)

        return {
            "success": True,
            "query_info": query_info,
            "papers": formatted_papers,
            "total_results": len(formatted_papers),
            "message": f"Successfully formatted {len(formatted_papers)} papers",
        }

    except Exception as e:
        logger.error(f"Error formatting search results: {str(e)}")
        raise Exception(f"Results formatting failed: {str(e)}")

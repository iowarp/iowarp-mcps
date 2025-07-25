"""
ArXiv category and subject search capabilities.
"""
from typing import Dict, Any
import logging
from .arxiv_base import execute_arxiv_query

logger = logging.getLogger(__name__)


async def search_arxiv(query: str = "astro-ph", max_results: int = 3) -> Dict[str, Any]:
    """
    Search ArXiv for research papers.
    
    Args:
        query: Search query (default: "astro-ph")
        max_results: Maximum number of results to return (default: 3)
        
    Returns:
        Dictionary containing search results and metadata
    """
    # Construct search URL
    params = {
        'search_query': f'cat:{query}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    papers = await execute_arxiv_query(params)
    
    return {
        'success': True,
        'papers': papers,
        'query': query,
        'max_results': max_results,
        'returned_results': len(papers),
        'message': f"Successfully fetched {len(papers)} papers for query '{query}'"
    }


async def get_recent_papers(category: str = "cs.AI", max_results: int = 5) -> Dict[str, Any]:
    """
    Get recent papers from a specific ArXiv category.
    
    Args:
        category: ArXiv category (default: "cs.AI")
        max_results: Maximum number of results to return (default: 5)
        
    Returns:
        Dictionary containing recent papers and metadata
    """
    return await search_arxiv(query=category, max_results=max_results)


async def search_by_subject(subject: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search ArXiv papers by subject classification.
    
    Args:
        subject: ArXiv subject classification (e.g., 'cs.AI', 'physics.astro-ph')
        max_results: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary containing search results and metadata
    """
    # Construct subject search URL
    params = {
        'search_query': f'cat:{subject}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    papers = await execute_arxiv_query(params)
    
    return {
        'success': True,
        'papers': papers,
        'subject': subject,
        'max_results': max_results,
        'returned_results': len(papers),
        'message': f"Successfully found {len(papers)} papers in subject '{subject}'"
    }
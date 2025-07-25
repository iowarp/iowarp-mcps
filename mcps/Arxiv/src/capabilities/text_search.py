"""
ArXiv text-based search capabilities (title, abstract, author).
"""
from typing import Dict, Any
import logging
from .arxiv_base import execute_arxiv_query

logger = logging.getLogger(__name__)


async def search_by_title(title_keywords: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search ArXiv papers by title keywords.
    
    Args:
        title_keywords: Keywords to search in paper titles
        max_results: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary containing search results and metadata
    """
    # Construct title search URL
    params = {
        'search_query': f'ti:{title_keywords}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }
    
    papers = await execute_arxiv_query(params)
    
    return {
        'success': True,
        'papers': papers,
        'title_keywords': title_keywords,
        'max_results': max_results,
        'returned_results': len(papers),
        'message': f"Successfully found {len(papers)} papers with title keywords '{title_keywords}'"
    }


async def search_by_abstract(abstract_keywords: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search ArXiv papers by abstract keywords.
    
    Args:
        abstract_keywords: Keywords to search in paper abstracts
        max_results: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary containing search results and metadata
    """
    # Construct abstract search URL
    params = {
        'search_query': f'abs:{abstract_keywords}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'relevance',
        'sortOrder': 'descending'
    }
    
    papers = await execute_arxiv_query(params)
    
    return {
        'success': True,
        'papers': papers,
        'abstract_keywords': abstract_keywords,
        'max_results': max_results,
        'returned_results': len(papers),
        'message': f"Successfully found {len(papers)} papers with abstract keywords '{abstract_keywords}'"
    }


async def search_papers_by_author(author: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Search ArXiv papers by author name.
    
    Args:
        author: Author name to search for
        max_results: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary containing search results and metadata
    """
    # Construct author search URL
    params = {
        'search_query': f'au:{author}',
        'start': 0,
        'max_results': max_results,
        'sortBy': 'submittedDate',
        'sortOrder': 'descending'
    }
    
    papers = await execute_arxiv_query(params)
    
    return {
        'success': True,
        'papers': papers,
        'author': author,
        'max_results': max_results,
        'returned_results': len(papers),
        'message': f"Successfully fetched {len(papers)} papers by author '{author}'"
    }
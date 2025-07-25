"""
ArXiv paper details and analysis capabilities.
"""
from typing import Dict, Any
import logging
from .arxiv_base import execute_arxiv_query, parse_arxiv_entry
import xml.etree.ElementTree as ET
import httpx

logger = logging.getLogger(__name__)


async def get_paper_details(arxiv_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a specific ArXiv paper by ID.
    
    Args:
        arxiv_id: ArXiv paper ID (e.g., '2301.12345' or 'cs/0501001')
        
    Returns:
        Dictionary containing detailed paper information
    """
    base_url = "https://export.arxiv.org/api/query"
    
    # Construct paper details query
    params = {
        'id_list': arxiv_id,
        'max_results': 1
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Getting paper details for ArXiv ID: {arxiv_id}")
            response = await client.get(base_url, params=params)
            response.raise_for_status()
            
        # Parse XML response
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        # Extract paper details
        entries = root.findall('atom:entry', ns)
        if not entries:
            raise Exception(f"Paper with ID '{arxiv_id}' not found")
        
        paper = parse_arxiv_entry(entries[0])
        
        # Add additional details
        entry = entries[0]
        
        # Extract DOI if available
        doi_elem = entry.find('.//arxiv:doi', {'arxiv': 'http://arxiv.org/schemas/atom'})
        if doi_elem is not None:
            paper['doi'] = doi_elem.text
        
        # Extract journal reference if available
        journal_elem = entry.find('.//arxiv:journal_ref', {'arxiv': 'http://arxiv.org/schemas/atom'})
        if journal_elem is not None:
            paper['journal_ref'] = journal_elem.text
        
        # Extract comments if available
        comment_elem = entry.find('.//arxiv:comment', {'arxiv': 'http://arxiv.org/schemas/atom'})
        if comment_elem is not None:
            paper['comment'] = comment_elem.text
        
        return {
            'success': True,
            'paper': paper,
            'arxiv_id': arxiv_id,
            'message': f"Successfully retrieved details for paper '{arxiv_id}'"
        }
        
    except Exception as e:
        logger.error(f"Error getting paper details: {str(e)}")
        raise Exception(f"Failed to get paper details: {str(e)}")


async def find_similar_papers(reference_paper_id: str, max_results: int = 10) -> Dict[str, Any]:
    """
    Find papers similar to a reference paper based on categories and keywords.
    
    Args:
        reference_paper_id: ArXiv ID of the reference paper
        max_results: Maximum number of similar papers to return (default: 10)
        
    Returns:
        Dictionary containing similar papers
    """
    try:
        # First, get details of the reference paper
        reference_details = await get_paper_details(reference_paper_id)
        if not reference_details.get('success'):
            raise Exception("Could not retrieve reference paper details")
        
        reference_paper = reference_details['paper']
        
        # Extract categories and title keywords for similarity search
        categories = reference_paper.get('categories', [])
        title = reference_paper.get('title', '')
        
        # Use the primary category for searching similar papers
        primary_category = categories[0] if categories else 'cs.AI'
        
        # Extract key words from title (simple approach)
        title_words = [word.lower() for word in title.split() if len(word) > 3]
        key_terms = ' '.join(title_words[:3])  # Use first 3 significant words
        
        # Search for papers in the same category with similar keywords
        params = {
            'search_query': f'cat:{primary_category} AND ti:{key_terms}',
            'start': 0,
            'max_results': max_results + 5,  # Get a few extra to filter out the reference paper
            'sortBy': 'relevance',
            'sortOrder': 'descending'
        }
        
        papers = await execute_arxiv_query(params)
        
        # Filter out the reference paper
        similar_papers = []
        for paper in papers:
            if reference_paper_id not in paper.get('id', ''):
                similar_papers.append(paper)
                if len(similar_papers) >= max_results:
                    break
        
        return {
            'success': True,
            'reference_paper': reference_paper,
            'similar_papers': similar_papers,
            'max_results': max_results,
            'returned_results': len(similar_papers),
            'message': f"Found {len(similar_papers)} papers similar to '{reference_paper_id}'"
        }
        
    except Exception as e:
        logger.error(f"Error finding similar papers: {str(e)}")
        raise Exception(f"Similar papers search failed: {str(e)}")
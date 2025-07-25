"""
Tests for ArXiv category search capabilities.
"""
import pytest
import asyncio
import sys
import os

# Add src to path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from capabilities.category_search import search_arxiv, get_recent_papers, search_by_subject


class TestCategorySearch:
    """Test category search functionality"""
    
    @pytest.mark.asyncio
    async def test_search_arxiv_default(self):
        """Test default ArXiv search"""
        result = await search_arxiv()
        
        assert result['success'] is True
        assert 'papers' in result
        assert 'query' in result
        assert 'max_results' in result
        assert 'returned_results' in result
        assert isinstance(result['papers'], list)
    
    @pytest.mark.asyncio
    async def test_search_arxiv_custom_query(self):
        """Test ArXiv search with custom query"""
        result = await search_arxiv("cs.AI", 5)
        
        assert result['success'] is True
        assert result['query'] == "cs.AI"
        assert result['max_results'] == 5
        assert len(result['papers']) <= 5
        assert isinstance(result['papers'], list)
    
    @pytest.mark.asyncio
    async def test_get_recent_papers(self):
        """Test getting recent papers"""
        result = await get_recent_papers("cs.LG", 3)
        
        assert result['success'] is True
        assert 'papers' in result
        assert len(result['papers']) <= 3
        
        # Check that papers have required fields
        if result['papers']:
            paper = result['papers'][0]
            assert 'title' in paper
            assert 'authors' in paper
            assert 'published' in paper
    
    @pytest.mark.asyncio
    async def test_search_by_subject(self):
        """Test search by subject"""
        result = await search_by_subject("math.CO", 2)
        
        assert result['success'] is True
        assert result['subject'] == "math.CO"
        assert result['max_results'] == 2
        assert 'papers' in result
    
    @pytest.mark.asyncio
    async def test_empty_results(self):
        """Test handling of queries that might return no results"""
        result = await search_arxiv("nonexistent.category", 1)
        
        # Should still succeed even if no papers found
        assert result['success'] is True
        assert 'papers' in result
        assert isinstance(result['papers'], list)
    
    @pytest.mark.asyncio
    async def test_paper_structure(self):
        """Test that returned papers have the expected structure"""
        result = await search_arxiv("cs.AI", 1)
        
        if result['papers']:
            paper = result['papers'][0]
            required_fields = ['id', 'title', 'authors', 'published', 'categories', 'links']
            
            for field in required_fields:
                assert field in paper, f"Missing field: {field}"
            
            assert isinstance(paper['authors'], list)
            assert isinstance(paper['categories'], list)
            assert isinstance(paper['links'], list)
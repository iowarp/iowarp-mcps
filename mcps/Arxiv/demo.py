#!/usr/bin/env python3
"""
Simple demonstration of ArXiv MCP Server capabilities.
"""

import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src", "arxiv_mcp"))


async def demonstrate_capabilities():
    """Demonstrate various ArXiv capabilities"""
    print("ArXiv MCP Server - Capability Demonstration")
    print("=" * 60)

    # Import capabilities directly
    try:
        from capabilities.category_search import search_arxiv
        from capabilities.text_search import search_by_title

        print("\nSample Category Search (cs.AI, 3 results):")
        results = await search_arxiv("cs.AI", 3)
        if results.get("success"):
            for i, paper in enumerate(results["papers"][:2], 1):  # Show first 2
                print(f"   {i}. {paper.get('title', 'No title')[:80]}...")
                print(f"      Authors: {', '.join(paper.get('authors', [])[:2])}")
                print(f"      Published: {paper.get('published', '')[:10]}")
                print()

        print("Sample Title Search ('machine learning', 2 results):")
        title_results = await search_by_title("machine learning", 2)
        if title_results.get("success"):
            for i, paper in enumerate(title_results["papers"][:2], 1):
                print(f"   {i}. {paper.get('title', 'No title')[:80]}...")
                print(f"      Categories: {', '.join(paper.get('categories', [])[:3])}")
                print()

        print("ArXiv MCP Tools Available:")
        tools = [
            "search_arxiv - Search papers by category (e.g., 'cs.AI', 'physics.astro-ph')",
            "get_recent_papers - Get recent papers from a specific category",
            "search_papers_by_author - Search papers by author name",
            "search_by_title - Search papers by title keywords",
            "search_by_abstract - Search papers by abstract keywords",
            "search_by_subject - Search papers by subject classification",
            "search_date_range - Search papers within a specific date range",
            "get_paper_details - Get detailed information about a specific paper",
            "export_to_bibtex - Export search results to BibTeX format",
            "find_similar_papers - Find papers similar to a reference paper",
        ]

        for i, tool in enumerate(tools, 1):
            print(f"   {i:2d}. {tool}")

        print("\nExample ArXiv Categories:")
        categories = [
            "cs.AI - Artificial Intelligence",
            "cs.LG - Machine Learning",
            "cs.CV - Computer Vision",
            "physics.astro-ph - Astrophysics",
            "math.CO - Combinatorics",
            "q-bio.QM - Quantitative Methods",
        ]

        for category in categories:
            print(f"   • {category}")

        print("\nArXiv MCP Server is ready to use!")
        print("   Start the server with: uv run python src/arxiv_mcp/server.py")
        print("   Or use the script: uv run arxiv-mcp")
        print("   The server uses MCP protocol via stdio transport by default")

    except ImportError as e:
        print(f"Import error: {e}")
        print("   Make sure all dependencies are installed with: uv sync")
    except Exception as e:
        print(f"Error: {e}")

    print("\n" + "=" * 60)


def main():
    """Main entry point"""
    asyncio.run(demonstrate_capabilities())


if __name__ == "__main__":
    main()

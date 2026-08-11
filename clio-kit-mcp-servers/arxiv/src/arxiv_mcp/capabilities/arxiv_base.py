"""
Base utilities for ArXiv search capabilities.
"""

import asyncio
import httpx
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Union, cast
import logging

logger = logging.getLogger(__name__)

# ArXiv's public API rate-limits aggressively under concurrent load (HTTP 429).
# A well-behaved client retries a 429 with backoff rather than failing the
# caller's request outright -- this is standard practice for this API, not a
# test-only accommodation. Bounded (a few seconds worst case) so a genuinely
# sustained block still surfaces as a real failure instead of hanging.
_RATE_LIMIT_MAX_ATTEMPTS = 4
_RATE_LIMIT_BACKOFF_SECONDS = 1.0


def parse_arxiv_entry(
    entry: ET.Element,
) -> Dict[str, Union[str, List[str], List[Dict[str, str]]]]:
    """
    Parse a single ArXiv entry from XML response.

    Args:
        entry: XML element representing an ArXiv paper entry

    Returns:
        Dictionary containing paper information
    """
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    paper: Dict[str, Union[str, List[str], List[Dict[str, str]]]] = {}

    # Extract basic information
    id_elem = entry.find("atom:id", ns)
    paper["id"] = id_elem.text if id_elem is not None and id_elem.text else ""
    title_elem = entry.find("atom:title", ns)
    paper["title"] = (
        title_elem.text.strip() if title_elem is not None and title_elem.text else ""
    )
    summary_elem = entry.find("atom:summary", ns)
    paper["summary"] = (
        summary_elem.text.strip()
        if summary_elem is not None and summary_elem.text
        else ""
    )
    published_elem = entry.find("atom:published", ns)
    paper["published"] = (
        published_elem.text
        if published_elem is not None and published_elem.text
        else ""
    )
    updated_elem = entry.find("atom:updated", ns)
    paper["updated"] = (
        updated_elem.text if updated_elem is not None and updated_elem.text else ""
    )

    # Extract authors
    authors = []
    for author in entry.findall("atom:author", ns):
        name_elem = author.find("atom:name", ns)
        if name_elem is not None and name_elem.text:
            authors.append(name_elem.text)
    paper["authors"] = authors

    # Extract categories
    categories = []
    for category in entry.findall("atom:category", ns):
        term = category.get("term")
        if term:
            categories.append(term)
    paper["categories"] = categories

    # Extract links
    links = []
    for link in entry.findall("atom:link", ns):
        link_data = {
            "href": link.get("href", ""),
            "rel": link.get("rel", ""),
            "type": link.get("type", ""),
        }
        links.append(link_data)
    paper["links"] = links

    return paper


async def execute_arxiv_query(
    params: Dict[str, Any],
) -> List[Dict[str, Union[str, List[str], List[Dict[str, str]]]]]:
    """
    Execute an ArXiv API query and return parsed papers.

    Args:
        params: Query parameters for ArXiv API

    Returns:
        List of parsed paper dictionaries
    """
    base_url = "https://export.arxiv.org/api/query"

    try:
        response = await _get_with_rate_limit_retry(base_url, params)

        # Parse XML response
        root = ET.fromstring(response.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        # Extract papers
        papers = []
        entries = root.findall("atom:entry", ns)

        for entry in entries:
            paper = parse_arxiv_entry(entry)
            papers.append(paper)

        return papers

    except httpx.TimeoutException:
        logger.error("ArXiv API request timed out")
        raise Exception("ArXiv API request timed out")
    except httpx.HTTPStatusError as e:
        logger.error(f"ArXiv API returned error status: {e.response.status_code}")
        raise Exception(f"ArXiv API error: {e.response.status_code}")
    except ET.ParseError:
        logger.error("Failed to parse ArXiv XML response")
        raise Exception("Failed to parse ArXiv response")
    except Exception as e:
        logger.error(f"Unexpected error in ArXiv query: {str(e)}")
        raise Exception(f"ArXiv query failed: {str(e)}")


async def _get_with_rate_limit_retry(
    base_url: str, params: Dict[str, Any]
) -> httpx.Response:
    """Issue the ArXiv API GET, retrying a 429 response with bounded backoff.

    Every other outcome (success, timeout, a non-429 HTTP error, a connection
    error) is returned or raised on the first attempt unchanged -- only a 429
    is treated as transient and retried, honoring ``Retry-After`` when the API
    sends one.
    """
    last_error: httpx.HTTPStatusError | None = None
    for attempt in range(_RATE_LIMIT_MAX_ATTEMPTS):
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Executing ArXiv query with params: {params}")
            response = await client.get(base_url, params=params)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            last_error = httpx.HTTPStatusError(
                f"Client error '429 Too Many Requests' for url '{response.url}'",
                request=response.request,
                response=response,
            )
        if attempt + 1 >= _RATE_LIMIT_MAX_ATTEMPTS:
            break
        retry_after = _parse_retry_after(response.headers.get("Retry-After"))
        delay = (
            retry_after
            if retry_after is not None
            else (_RATE_LIMIT_BACKOFF_SECONDS * (2**attempt))
        )
        logger.warning(
            f"ArXiv API rate-limited (429); retrying in {delay:.1f}s "
            f"(attempt {attempt + 1}/{_RATE_LIMIT_MAX_ATTEMPTS})"
        )
        await asyncio.sleep(delay)
    assert last_error is not None
    raise last_error


def _parse_retry_after(value: str | None) -> float | None:
    """Parse a numeric ``Retry-After`` header value in seconds, if present."""
    if value is None:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None


def generate_bibtex(
    paper: Dict[str, Union[str, List[str], List[Dict[str, str]]]],
) -> str:
    """
    Generate BibTeX citation for a paper.

    Args:
        paper: Paper dictionary from ArXiv API

    Returns:
        BibTeX formatted string
    """
    # Extract ArXiv ID from the paper ID URL
    paper_id = paper.get("id", "")
    arxiv_id = (
        paper_id.split("/")[-1] if isinstance(paper_id, str) and paper_id else "unknown"
    )

    # Clean title and remove newlines
    paper_title = paper.get("title", "")
    title = (
        paper_title.replace("\n", " ").strip() if isinstance(paper_title, str) else ""
    )

    # Format authors
    paper_authors = paper.get("authors", [])
    if isinstance(paper_authors, list) and all(
        isinstance(author, str) for author in paper_authors
    ):
        authors = " and ".join(cast(List[str], paper_authors))
    else:
        authors = ""

    # Extract year from published date
    paper_published = paper.get("published", "")
    year = (
        paper_published.split("-")[0]
        if isinstance(paper_published, str) and paper_published
        else "unknown"
    )

    # Generate BibTeX entry
    bibtex = f"""@article{{{arxiv_id},
    title = {{{title}}},
    author = {{{authors}}},
    year = {{{year}}},
    eprint = {{{arxiv_id}}},
    archivePrefix = {{arXiv}},
    primaryClass = {{{paper.get("categories", [""])[0] if isinstance(paper.get("categories"), list) and paper.get("categories") else ""}}},
    url = {{http://arxiv.org/abs/{arxiv_id}}}
}}"""

    return bibtex

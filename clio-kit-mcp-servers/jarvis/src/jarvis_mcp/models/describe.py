"""The ``jarvis_describe`` discriminated result union."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import Field

from ._base import _ClosedDocument
from .packages import JarvisPackageDescriptionDocument, JarvisPackageSummaryDocument

PACKAGE_SEARCH_SCHEMA = "jarvis.package-search.v1"
PACKAGE_SEARCH_CURSOR_SCHEMA = "clio-kit.jarvis-package-search-cursor.v1"


class JarvisDescribePackagesResult(_ClosedDocument):
    """Exhaustive legacy package inventory result."""

    target: Literal["packages"]
    packages: list[JarvisPackageDescriptionDocument]


class JarvisDescribePackageSearchResult(_ClosedDocument):
    """Bounded package search page."""

    schema_version: Literal["jarvis.package-search.v1"]
    target: Literal["package_search"]
    query: str
    inventory_revision: str
    packages: list[JarvisPackageSummaryDocument]
    total_matches: int
    returned_count: int
    next_cursor: str | None


class JarvisDescribePackageResult(_ClosedDocument):
    """Exact package description result."""

    target: Literal["package"]
    package: JarvisPackageDescriptionDocument


class JarvisDescribePipelineResult(_ClosedDocument):
    """Stored pipeline snapshot result."""

    target: Literal["pipeline"]
    pipeline: dict[str, Any]


class JarvisDescribeStepResult(_ClosedDocument):
    """Stored pipeline step and package configuration result."""

    target: Literal["step"]
    step: dict[str, Any]
    config: dict[str, Any]


JarvisDescribeResult = Annotated[
    JarvisDescribePackagesResult
    | JarvisDescribePackageSearchResult
    | JarvisDescribePackageResult
    | JarvisDescribePipelineResult
    | JarvisDescribeStepResult,
    Field(discriminator="target"),
]

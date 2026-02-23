"""Retry/backoff wrappers for connector operations."""

from __future__ import annotations

from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clio_agentic_search.core.connectors import IndexReport, NamespaceConnector
from clio_agentic_search.jobs import CancellationToken

# Retry policies -------------------------------------------------------

CONNECT_MAX_ATTEMPTS = 3
CONNECT_WAIT_MIN = 0.5
CONNECT_WAIT_MAX = 4.0

INDEX_MAX_ATTEMPTS = 2
INDEX_WAIT_MIN = 1.0
INDEX_WAIT_MAX = 8.0


def connect_with_retry(connector: NamespaceConnector) -> None:
    """Call connector.connect() with exponential backoff."""

    @retry(
        retry=retry_if_exception_type((OSError, RuntimeError)),
        stop=stop_after_attempt(CONNECT_MAX_ATTEMPTS),
        wait=wait_exponential(min=CONNECT_WAIT_MIN, max=CONNECT_WAIT_MAX),
        reraise=True,
    )
    def _inner() -> None:
        connector.connect()

    _inner()


def index_with_retry(
    connector: NamespaceConnector,
    *,
    full_rebuild: bool = False,
    cancellation_token: CancellationToken | None = None,
) -> IndexReport:
    """Call connector.index() with exponential backoff and cancellation."""

    @retry(
        retry=retry_if_exception_type((OSError, RuntimeError)),
        stop=stop_after_attempt(INDEX_MAX_ATTEMPTS),
        wait=wait_exponential(min=INDEX_WAIT_MIN, max=INDEX_WAIT_MAX),
        reraise=True,
    )
    def _inner() -> IndexReport:
        if cancellation_token is not None:
            cancellation_token.check()
        return connector.index(full_rebuild=full_rebuild)

    return _inner()


__all__ = [
    "RetryError",
    "connect_with_retry",
    "index_with_retry",
]

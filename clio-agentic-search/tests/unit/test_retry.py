"""Tests for retry/backoff wrappers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from clio_agentic_search.core.connectors import IndexReport
from clio_agentic_search.jobs import CancellationToken, JobCancelledError
from clio_agentic_search.retry import connect_with_retry, index_with_retry


def _make_report() -> IndexReport:
    return IndexReport(
        scanned_files=1, indexed_files=1, skipped_files=0, removed_files=0, elapsed_seconds=0.1
    )


class TestConnectWithRetry:
    def test_success_first_try(self) -> None:
        connector = MagicMock()
        connector.connect.return_value = None
        connect_with_retry(connector)
        connector.connect.assert_called_once()

    def test_retries_on_oserror(self) -> None:
        connector = MagicMock()
        connector.connect.side_effect = [OSError("fail"), None]
        connect_with_retry(connector)
        assert connector.connect.call_count == 2

    def test_gives_up_after_max_attempts(self) -> None:
        connector = MagicMock()
        connector.connect.side_effect = OSError("persistent")
        with pytest.raises(OSError, match="persistent"):
            connect_with_retry(connector)
        assert connector.connect.call_count == 3


class TestIndexWithRetry:
    def test_success_first_try(self) -> None:
        connector = MagicMock()
        connector.index.return_value = _make_report()
        result = index_with_retry(connector, full_rebuild=False)
        assert result.indexed_files == 1

    def test_retries_on_runtime_error(self) -> None:
        connector = MagicMock()
        connector.index.side_effect = [RuntimeError("transient"), _make_report()]
        result = index_with_retry(connector, full_rebuild=False)
        assert result.indexed_files == 1
        assert connector.index.call_count == 2

    def test_respects_cancellation_token(self) -> None:
        connector = MagicMock()
        token = CancellationToken()
        token.cancel()
        with pytest.raises(JobCancelledError):
            index_with_retry(connector, cancellation_token=token)
        connector.index.assert_not_called()

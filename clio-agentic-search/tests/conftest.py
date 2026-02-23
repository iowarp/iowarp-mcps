from __future__ import annotations

from collections.abc import Iterator

import pytest

from clio_agentic_search.api.app import reset_app_state


@pytest.fixture(autouse=True)
def _isolated_app_state() -> Iterator[None]:
    reset_app_state()
    yield
    reset_app_state()

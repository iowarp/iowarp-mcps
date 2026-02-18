"""Tests for Chronolog start session capabilities."""

import pytest
import time
import random

try:
    from chronomcp.capabilities.start_handler import start_chronolog

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from .test_utils import are_chronolog_processes_running

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


class TestStartHandler:
    """Test ChronoLog session start functionality"""

    @pytest.mark.asyncio
    async def test_start_chronolog_basic(self):
        """Test basic ChronoLog session start"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"
        result = await start_chronolog(chronicle_name, story_name)
        assert isinstance(result, str)
        assert "ChronoLog session started" in result, (
            f"Expected session to start, got: {result}"
        )

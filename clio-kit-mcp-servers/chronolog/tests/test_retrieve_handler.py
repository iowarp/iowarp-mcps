"""Tests for Chronolog retrieve interaction capabilities."""

import pytest
import time
import random

try:
    from chronomcp.capabilities.retrieve_handler import retrieve_interaction
    from chronomcp.capabilities.record_handler import record_interaction
    from chronomcp.capabilities.start_handler import start_chronolog
    from chronomcp.capabilities.stop_handler import stop_chronolog

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from .test_utils import are_chronolog_processes_running

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


class TestRetrieveHandler:
    """Test retrieve interaction functionality"""

    @pytest.mark.asyncio
    async def test_retrieve_empty_interaction(self):
        """Test basic retrieve functionality"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"
        result = await retrieve_interaction(chronicle_name, story_name)
        assert isinstance(result, str)
        assert result == "No records found."

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="TBD - Verify ChronoMCP integrity")
    async def test_retrieve_after_record(self):
        """Test retrieving interaction after recording one"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"

        # Start a new session
        start_result = await start_chronolog(chronicle_name, story_name)
        assert isinstance(start_result, str)
        assert "ChronoLog session started" in start_result

        # Record an interaction
        record_result = await record_interaction("Test question", "Test answer")
        assert isinstance(record_result, str)
        assert "Interaction recorded to ChronoLog" in record_result

        # Retrieve the recorded interaction
        retrieve_result = await retrieve_interaction(chronicle_name, story_name)
        assert isinstance(retrieve_result, str)
        assert "No records found." not in retrieve_result

        # Stop the session
        stop_result = await stop_chronolog()
        assert isinstance(stop_result, str)

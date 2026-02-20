"""Integration tests for Chronolog MCP Server."""

import pytest
import time
import random

try:
    from chronomcp.capabilities import (
        record_handler,
        retrieve_handler,
        start_handler,
        stop_handler,
    )

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from .test_utils import are_chronolog_processes_running

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


class TestIntegration:
    """Integration tests for the full Chronolog MCP stack"""

    @pytest.mark.asyncio
    async def test_basic_workflow(self):
        """Test basic workflow: start -> record -> retrieve -> stop"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"

        # Start session
        start_result = await start_handler.start_chronolog(chronicle_name, story_name)
        assert isinstance(start_result, str)
        assert "ChronoLog session started" in start_result

        # Record interaction
        record_result = await record_handler.record_interaction("Hello", "Hi there!")
        assert isinstance(record_result, str)
        assert record_result == "Interaction recorded to ChronoLog"

        # Retrieve interactions
        retrieve_result = await retrieve_handler.retrieve_interaction(
            chronicle_name, story_name
        )
        assert isinstance(retrieve_result, str)
        assert "Not records found." not in retrieve_result

        # Stop session
        stop_result = await stop_handler.stop_chronolog()
        assert isinstance(stop_result, str)
        assert "ChronoLog session stopped" in stop_result

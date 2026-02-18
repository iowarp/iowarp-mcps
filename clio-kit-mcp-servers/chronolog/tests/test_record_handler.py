"""Tests for Chronolog record interaction capabilities."""

import pytest
import time
import random

try:
    from fastmcp.exceptions import ToolError

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


class TestRecordHandler:
    """Test record interaction functionality"""

    @pytest.mark.asyncio
    async def test_record_without_session_raises(self):
        """Test that recording without an active session raises ToolError"""
        with pytest.raises(ToolError, match="No active ChronoLog session"):
            await record_interaction("test", "test")

    @pytest.mark.asyncio
    async def test_record_interaction_basic(self):
        """Test basic record interaction"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"

        # Start session
        start_result = await start_chronolog(chronicle_name, story_name)
        assert isinstance(start_result, str)
        assert "ChronoLog session started" in start_result, (
            f"Expected session to start, got: {start_result}"
        )

        # Record interaction
        result = await record_interaction(
            "test user message", "test assistant response"
        )
        assert isinstance(result, str)
        assert "Interaction recorded to ChronoLog" in result, (
            f"Expected interaction to be recorded, got: {result}"
        )

        # Stop session
        stop_result = await stop_chronolog()
        assert isinstance(stop_result, str)
        assert "ChronoLog session stopped" in stop_result, (
            f"Expected session to stop, got: {stop_result}"
        )

"""Tests for Chronolog stop session capabilities."""

import pytest

try:
    from fastmcp.exceptions import ToolError

    from chronomcp.capabilities.stop_handler import stop_chronolog

    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

from .test_utils import are_chronolog_processes_running

pytestmark = pytest.mark.skipif(
    not HAS_DEPENDENCIES,
    reason="ChronoLog system dependencies not available",
)


class TestStopHandler:
    """Test ChronoLog session stop functionality"""

    @pytest.mark.asyncio
    async def test_stop_chronolog_no_session_raises(self):
        """Test that stopping without an active session raises ToolError"""
        with pytest.raises(ToolError, match="No active ChronoLog session"):
            await stop_chronolog()

    @pytest.mark.asyncio
    async def test_stop_chronolog_basic(self):
        """Test basic stop functionality with active session"""
        if not are_chronolog_processes_running():
            pytest.skip("ChronoLog processes are not running")

        from chronomcp.capabilities.start_handler import start_chronolog
        import time
        import random

        chronicle_name = (
            f"test_chronicle_{int(time.time())}_{random.randint(1000, 9999)}"
        )
        story_name = f"test_story_{int(time.time())}_{random.randint(1000, 9999)}"
        await start_chronolog(chronicle_name, story_name)

        result = await stop_chronolog()
        assert isinstance(result, str)
        assert "ChronoLog session stopped" in result

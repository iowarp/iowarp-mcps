# capabilities/start_chronolog.py

from fastmcp.exceptions import ToolError

from chronomcp.utils import config


async def start_chronolog(
    chronicle_name: str | None = None, story_name: str | None = None
) -> str:
    """Connect to ChronoLog and acquire a story handle for logging."""
    chronicle = chronicle_name or config.DEFAULT_CHRONICLE
    story = story_name or config.DEFAULT_STORY

    ret = config.client.Connect()
    if ret != 0:
        raise ToolError(f"Failed to connect to ChronoLog: {ret}")

    attrs: dict[str, str] = {}
    ret = config.client.CreateChronicle(chronicle, attrs, 1)
    if ret != 0:
        config.client.Disconnect()
        raise ToolError(f"Failed to create chronicle '{chronicle}': {ret}")

    ret, handle = config.client.AcquireStory(chronicle, story, attrs, 1)
    if ret != 0:
        config.client.ReleaseStory(chronicle, story)
        config.client.Disconnect()
        raise ToolError(f"Failed to acquire story '{story}' in chronicle '{chronicle}': {ret}")

    config._active_chronicle = chronicle
    config._active_story = story
    config._story_handle = handle

    return f"ChronoLog session started: chronicle='{chronicle}', story='{story}'"

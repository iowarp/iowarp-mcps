# capabilities/stop_chronolog.py
import utils.config as config

async def stop_chronolog() -> str:
    """
    Release the story and disconnect from ChronoLog.
    """
    if config._story_handle is None:
        return "No active ChronoLog session to stop."

    ret = config.client.ReleaseStory(config._active_chronicle, config._active_story)
    if ret != 0:
        return f"Failed to release story '{config._active_story}': {ret}"

    ret = config.client.Disconnect()
    if ret != 0:
        return f"Failed to disconnect from ChronoLog: {ret}"

    config._active_chronicle = None
    config._active_story     = None
    config._story_handle     = None

    return "ChronoLog session stopped and disconnected"

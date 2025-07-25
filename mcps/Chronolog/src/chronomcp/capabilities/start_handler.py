# capabilities/start_chronolog.py
import utils.config as config

async def start_chronolog(chronicle_name: str = None, story_name: str = None) -> str:
    chronicle = chronicle_name or config.DEFAULT_CHRONICLE
    story     = story_name     or config.DEFAULT_STORY

    ret = config.client.Connect()
    if ret != 0:
        return f"Failed to connect to ChronoLog: {ret}"

    attrs = {}
    ret = config.client.CreateChronicle(chronicle, attrs, 1)
    if ret != 0:
        config.client.Disconnect()
        return f"Failed to create chronicle '{chronicle}': {ret}"

    ret, handle = config.client.AcquireStory(chronicle, story, attrs, 1)
    if ret != 0:
        config.client.ReleaseStory(chronicle, story)
        config.client.Disconnect()
        return f"Failed to acquire story '{story}' in chronicle '{chronicle}': {ret}"

    config._active_chronicle = chronicle
    config._active_story     = story
    config._story_handle     = handle

    return f"ChronoLog session started: chronicle='{chronicle}', story='{story}'"

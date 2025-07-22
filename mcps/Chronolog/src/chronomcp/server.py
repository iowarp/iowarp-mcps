# server.py
import utils.config as config
from capabilities.start_handler    import start_chronolog as _start
from capabilities.record_handler import record_interaction as _record
from capabilities.stop_handler     import stop_chronolog  as _stop
from capabilities.retrieve_handler import retrieve_interaction as _retrieve

mcp = config.mcp

@mcp.tool()
async def start_chronolog(chronicle_name: str = None, story_name: str = None):
    """
    Connects to ChronoLog, creates a chronicle, and acquires a story handle for logging interactions.

    Args:
        chronicle_name (str, optional): Name of the chronicle to create or connect to. Defaults to config.DEFAULT_CHRONICLE.
        story_name (str, optional): Name of the story to acquire. Defaults to config.DEFAULT_STORY.

    Returns:
        str: Confirmation message with chronicle and story identifiers.
    """
    return await _start(chronicle_name, story_name)

@mcp.tool()
async def record_interaction(user_message: str, assistant_message: str):
    """
    Logs user messages and LLM responses to the active story with structured event formatting.

    Args:
        user_message (str): The user message content to record.
        assistant_message (str): The assistant (LLM) response to record.

    Returns:
        str: Confirmation of successful event logging with timestamp information.
    """
    return await _record(user_message, assistant_message)

@mcp.tool()
async def stop_chronolog():
    """
    Releases the story handle and cleanly disconnects from ChronoLog system.

    Returns:
        str: Confirmation of clean shutdown and resource cleanup.
    """
    return await _stop()

@mcp.tool()
async def retrieve_interaction(
    chronicle_name: str = None,
    story_name: str = None,
    start_time: str = None,
    end_time: str = None
):
    """
    Extracts logged records from specified chronicle and story, generates timestamped output files with filtering options.

    Args:
        chronicle_name (str, optional): Name of the chronicle to retrieve from. Defaults to config.DEFAULT_CHRONICLE.
        story_name (str, optional): Name of the story to retrieve from. Defaults to config.DEFAULT_STORY.
        start_time (str, optional): Start time for filtering records (YYYY-MM-DD HH:MM:SS or similar).
        end_time (str, optional): End time for filtering records (YYYY-MM-DD HH:MM:SS or similar).

    Returns:
        str: Generated text file with interaction history or error message if no records found.
    """
    return await _retrieve(chronicle_name, story_name, start_time, end_time)

def main():
    mcp.run()

if __name__ == "__main__":
    main()

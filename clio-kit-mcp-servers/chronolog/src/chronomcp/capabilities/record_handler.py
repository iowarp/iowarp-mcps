# capabilities/record_interaction.py

from fastmcp.exceptions import ToolError

from chronomcp.utils import config


async def record_interaction(user_message: str, assistant_message: str) -> str:
    """Log a user/assistant interaction to the active ChronoLog story."""
    if config._story_handle is None:
        raise ToolError("No active ChronoLog session. Please call start_chronolog first.")

    config._story_handle.log_event(
        f"user: {user_message}, assistant: {assistant_message}"
    )
    return "Interaction recorded to ChronoLog"

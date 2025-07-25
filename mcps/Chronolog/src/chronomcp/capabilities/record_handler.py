# capabilities/record_interaction.py
import utils.config as config

async def record_interaction(user_message: str, assistant_message: str) -> str:
    if config._story_handle is None:
        return "No active ChronoLog session. Please call start_chronolog first."

    config._story_handle.log_event(f"user: {user_message}, assistant: {assistant_message}")
    return "Interaction recorded to ChronoLog"

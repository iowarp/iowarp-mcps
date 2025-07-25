# capabilities/retrieve_interaction.py
import utils.config as config
import utils.helpers as helpers
import re
from datetime import datetime

async def retrieve_interaction(
    chronicle_name: str = None,
    story_name: str = None,
    start_time: str = None,
    end_time: str = None
) -> str:
    chronicle = chronicle_name or config.DEFAULT_CHRONICLE
    story     = story_name     or config.DEFAULT_STORY

    cmd = [
        "stdbuf", "-o0",
        config.READER_BINARY,
        "-c", config.CONFIG_FILE,
        "-C", chronicle,
        "-S", story
    ]
    if start_time:
        st_ns = helpers.parse_time_arg(start_time, is_end=False)
        cmd += ["-st", st_ns]
    if end_time:
        et_ns = helpers.parse_time_arg(end_time, is_end=True)
        cmd += ["-et", et_ns]

    out, err = helpers.run_reader(cmd)

    records = re.findall(r'record="([^"]*)"', out)
    if not records:
        return "No records found."

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    filename = f"records_{chronicle}_{story}_{ts}.txt"
    with open(filename, "w") as f:
        f.write("\n".join(records))
    return filename

# helpers.py
import subprocess, re
from datetime import datetime, date, time, timedelta

def to_nanosecond(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1e9))

def parse_time_arg(arg: str, is_end: bool) -> str:
    if arg.isdigit():
        return arg
    a = arg.strip().lower()
    now = datetime.now()

    if a == "yesterday":
        d = (now - timedelta(days=1)).date()
    elif a == "today":
        d = now.date()
    elif a == "tomorrow":
        d = (now + timedelta(days=1)).date()
    else:
        d = datetime.fromisoformat(arg).date()

    if is_end:
        dt = datetime.combine(d, time(23,59,59,999999))
    else:
        dt = datetime.combine(d, time.min)

    return to_nanosecond(dt)

def run_reader(cmd_args):
    proc = subprocess.run(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return proc.stdout, proc.stderr

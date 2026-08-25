#!/usr/bin/env python3
"""Run every skill against a real task and record exactly what happened.

For each skill this spawns an agent with only that skill's plugin loaded and
only the MCP servers its frontmatter declares, gives it a realistic request over
real fixture files, and records the full provenance: which skill fired, every
tool call with its input and output, which calls failed and why.

A failed tool call is a defect in the MCP server, not in the skill. The two are
scored separately: `skill_fired` and `tool_sequence` judge the skill; the tool
pass/fail counts judge the servers behind it.

    uv run --with claude-agent-sdk python evals/skill_eval.py [skill-name ...]

Writes evals/results/<skill>.json and prints a summary table.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import time

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    query,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
TASKS = REPO / "evals" / "skill-tasks.json"
RESULTS = REPO / "evals" / "results"
BUDGET_USD = 0.60


def skill_metadata() -> dict[str, dict[str, object]]:
    """Read every shipped skill's plugin directory and declared servers."""
    found: dict[str, dict[str, object]] = {}
    for md in sorted((REPO / "skills").rglob("SKILL.md")):
        text = md.read_text(encoding="utf-8")
        servers = re.search(r"^  servers: (.+)$", text, re.M)
        declared = [] if not servers or servers.group(1).strip() == "none" else [
            s.strip() for s in servers.group(1).split(",")
        ]
        found[md.parent.name] = {
            "plugin": str(md.parents[2]),
            "servers": declared,
        }
    return found


def mcp_config(servers: list[str]) -> dict[str, dict[str, object]]:
    """Launch each declared server through the kit's own launcher."""
    return {
        name: {
            "command": "uv",
            "args": ["run", "--project", str(REPO), "clio-kit",
                     "mcp-server", name.removeprefix("clio-")],
        }
        for name in servers
    }


async def evaluate(skill: str, meta: dict[str, object], task: dict[str, str]) -> dict:
    options = ClaudeAgentOptions(
        plugins=[{"type": "local", "path": str(meta["plugin"])}],
        mcp_servers=mcp_config(list(meta["servers"])),
        setting_sources=[],
        # No human is present in a headless run, so a question is a dead end that
        # would otherwise be scored as a tool failure.
        disallowed_tools=["Bash", "Write", "Edit", "Task", "WebSearch",
                          "AskUserQuestion"],
        permission_mode="bypassPermissions",
        cwd=str(REPO / "evals" / "fixtures"),
        max_turns=25,
        max_budget_usd=BUDGET_USD,
    )
    fired: list[str] = []
    calls: dict[str, dict] = {}
    order: list[str] = []
    answer: list[str] = []
    started = time.time()
    result_meta: dict = {}

    async for message in query(prompt=task["prompt"], options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    if block.name == "Skill":
                        name = str(block.input.get("command") or block.input.get("skill") or "")
                        if "-skills:" in name:
                            fired.append(name.split(":", 1)[1])
                    else:
                        calls[block.id] = {"tool": block.name, "input": block.input}
                        order.append(block.id)
                elif hasattr(block, "text"):
                    answer.append(block.text)
        elif isinstance(message, UserMessage):
            for block in message.content if isinstance(message.content, list) else []:
                if isinstance(block, ToolResultBlock) and block.tool_use_id in calls:
                    body = block.content
                    if isinstance(body, list):
                        body = " ".join(
                            part.get("text", "") for part in body if isinstance(part, dict)
                        )
                    text = " ".join(str(body).split())
                    low = text.lower()
                    failed = bool(block.is_error) or low.startswith("error") or any(
                        s in low for s in ('"error":', '"success":false', '"success": false',
                                           "validation error", "missing required argument",
                                           "no file currently open", "unknown strategy",
                                           "no such tool", "not found", "could not",
                                           "exceeds maximum allowed tokens")
                    )
                    calls[block.tool_use_id].update(
                        {"output": text[:400], "failed": failed}
                    )
        elif isinstance(message, ResultMessage):
            result_meta = {
                "turns": message.num_turns,
                "cost_usd": message.total_cost_usd,
                "is_error": message.is_error,
            }

    sequence = [calls[i] for i in order if i in calls]
    for call in sequence:
        call.setdefault("output", "(no result captured)")
        call.setdefault("failed", False)
    return {
        "skill": skill,
        "prompt": task["prompt"],
        "servers_attached": list(meta["servers"]),
        "skill_fired": fired,
        "expected_skill": skill,
        "tool_calls": sequence,
        "tools_total": len(sequence),
        "tools_ok": sum(1 for c in sequence if not c["failed"]),
        "tools_failed": sum(1 for c in sequence if c["failed"]),
        "answer": " ".join(answer)[:700],
        "seconds": round(time.time() - started, 1),
        **result_meta,
    }


async def main() -> int:
    tasks = {t["skill"]: t for t in json.loads(TASKS.read_text(encoding="utf-8"))}
    meta = skill_metadata()
    wanted = sys.argv[1:] or list(tasks)
    RESULTS.mkdir(parents=True, exist_ok=True)

    for skill in wanted:
        if skill not in tasks or skill not in meta:
            print(f"  skipping unknown skill {skill}")
            continue
        print(f"running {skill} ...", flush=True)
        try:
            record = await evaluate(skill, meta[skill], tasks[skill])
        except Exception as exc:  # a harness failure is data too
            record = {"skill": skill, "harness_error": f"{type(exc).__name__}: {exc}"[:300]}
        (RESULTS / f"{skill}.json").write_text(json.dumps(record, indent=2) + "\n")
        if "harness_error" in record:
            print(f"  HARNESS ERROR: {record['harness_error'][:110]}")
        else:
            hit = "fired" if skill in record["skill_fired"] else "DID NOT FIRE"
            print(f"  {hit}  tools {record['tools_ok']}/{record['tools_total']} ok"
                  f"  {record['seconds']}s  ${record.get('cost_usd') or 0:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(anyio.run(main))

#!/usr/bin/env python3
"""Check that the right skill fires for a realistic request, and no other does.

A skill's job is to be selected when it should be and to stay quiet otherwise.
That is separate from whether the MCP servers behind it work: a tool call that
fails is a server defect, and it says nothing about the skill. So this loads the
skill plugins through the Agent SDK, watches which Skill invocations occur, and
ignores MCP tool calls entirely.

Plugins are passed to the SDK directly and `setting_sources` is empty, so
nothing is installed into the operator's own configuration and their existing
plugins cannot influence the result.

    uv run --with claude-agent-sdk python evals/trigger_eval.py

Cases live in evals/trigger-cases.json. An empty `expect` is a control: the
request is outside the kit entirely and nothing should fire.
"""

from __future__ import annotations

import json
import pathlib
import sys

import anyio
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ToolUseBlock,
    query,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
CASES = REPO / "evals" / "trigger-cases.json"


def skill_plugins() -> list[dict[str, str]]:
    return [
        {"type": "local", "path": str(path)}
        for path in sorted((REPO / "skills").iterdir())
        if path.is_dir()
    ]


async def fired_skills(prompt: str) -> tuple[list[str], str]:
    """Return the skills that fired, and the answer text if none did."""
    options = ClaudeAgentOptions(
        plugins=skill_plugins(),
        setting_sources=[],
        allowed_tools=["Skill"],
        disallowed_tools=[
            "Bash", "Read", "Write", "Edit", "Glob", "Grep",
            "WebFetch", "WebSearch", "Task",
        ],
        max_turns=2,
        system_prompt=(
            "You have skills available. If one fits the request, invoke it. Then stop."
        ),
    )
    fired: list[str] = []
    spoken: list[str] = []
    async for message in query(prompt=prompt, options=options):
        if not isinstance(message, AssistantMessage):
            continue
        for block in message.content:
            if isinstance(block, ToolUseBlock) and block.name == "Skill":
                name = str(block.input.get("command") or block.input.get("skill") or "")
                # Only OUR skills count. An MCP tool call is the skill doing its
                # job, not a second skill competing for the request.
                if "-skills:" in name:
                    fired.append(name.split(":", 1)[1])
            elif hasattr(block, "text"):
                spoken.append(block.text)
    return fired, " ".join(spoken)[:120]


async def main() -> int:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    correct = 0
    for case in cases:
        fired, spoken = await fired_skills(case["prompt"])
        expected = case["expect"]
        unique = sorted(set(fired))
        if not expected:
            verdict = "CORRECT" if not unique else "SPURIOUS"
        elif unique == [expected]:
            verdict = "CORRECT"
        elif expected in unique:
            verdict = "ALSO-FIRED"
        elif unique:
            verdict = "WRONG-SKILL"
        else:
            verdict = "NONE-FIRED"
        correct += verdict == "CORRECT"
        print(f"[{verdict:11}] {case['prompt'][:64]}")
        print(f"              expected {expected or '(nothing)'}")
        print(f"              fired    {unique or '(none)'}")
        if not unique and expected:
            print(f"              said     {spoken}")
    print(f"\n{correct}/{len(cases)} correct")
    return 0 if correct == len(cases) else 1


if __name__ == "__main__":
    sys.exit(anyio.run(main))

#!/usr/bin/env python3
"""Turn evals/results/*.json into a readable per-skill provenance report."""

from __future__ import annotations

import json
import pathlib

RESULTS = pathlib.Path(__file__).resolve().parent / "results"

# Why a run could not exercise its servers on this machine. These are
# environment facts, not defects in the skill or the server.
BLOCKED = {
    "running-a-simulation-on-a-cluster": "spack, jarvis, slurm and lmod are not installed",
    "managing-software-environments": "lmod and spack are not installed",
    "writing-slurm-job-scripts": "slurm is not installed",
    "visualizing-3d-simulation-output": "ParaView is not installed",
    "recording-a-session-for-provenance": "no ChronoLog deployment",
    "diagnosing-a-slow-job": "darshan-parser is not installed and there is no real Darshan log",
    "analyzing-seismic-waveforms": "no SAC archive or earthquake catalog fixture",
}


def main() -> None:
    records = [json.loads(f.read_text()) for f in sorted(RESULTS.glob("*.json"))]
    print("# Skill evaluation, full provenance\n")
    print(f"{len(records)} skills. Each was given one realistic task with only its own")
    print("plugin loaded and only the MCP servers its frontmatter declares.\n")
    print("A failed tool call is a server or environment defect. Whether the skill")
    print("fired, and whether the tool sequence was right, is what judges the skill.\n")

    for r in sorted(records, key=lambda x: x["skill"]):
        print("=" * 78)
        print(f"## {r['skill']}")
        if "harness_error" in r:
            print(f"   harness error: {r['harness_error']}\n")
            continue
        fired = r["skill"] in r.get("skill_fired", [])
        print(f"   query    : {r['prompt']}")
        print(f"   servers  : {', '.join(r['servers_attached']) or 'none (knowledge skill)'}")
        print(f"   skill    : {'FIRED' if fired else 'DID NOT FIRE'}"
              + (f"  (fired instead: {r['skill_fired']})" if r["skill_fired"] and not fired else ""))
        print(f"   tools    : {r['tools_ok']} ok, {r['tools_failed']} failed, {r['tools_total']} total")
        if r["skill"] in BLOCKED:
            print(f"   blocked  : {BLOCKED[r['skill']]}")
        print(f"   cost     : ${r.get('cost_usd') or 0:.3f} over {r.get('turns','?')} turns, {r['seconds']}s")
        if r["tool_calls"]:
            print("   sequence :")
            for call in r["tool_calls"]:
                mark = "FAIL" if call["failed"] else " ok "
                print(f"     [{mark}] {call['tool'].replace('mcp__','')}"
                      f"  {json.dumps(call['input'])[:90]}")
                if call["failed"]:
                    print(f"            -> {call['output'][:150]}")
        print(f"   answer   : {r['answer'][:300]}\n")

    fired = sum(1 for r in records if r.get("skill") in r.get("skill_fired", []))
    ok = sum(r.get("tools_ok", 0) for r in records)
    bad = sum(r.get("tools_failed", 0) for r in records)
    print("=" * 78)
    print(f"fired {fired}/{len(records)}   tool calls {ok} ok / {bad} failed"
          f"   cost ${sum(r.get('cost_usd') or 0 for r in records):.2f}")


if __name__ == "__main__":
    main()

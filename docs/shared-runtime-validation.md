# Shared runtime qualification (#1319)

Implemented on `codex/shared-mcp-runtime` in clio-kit, with Agent integration on
`codex/provider-runtime-campaign`. The [plan](shared-runtime-plan.md) records the
alternatives and the selected installation boundary.

## Result

The default launcher runs each MCP server as a separate process in the selected
CLIO Kit installation. Dependencies are installed once for the requested extras;
normal invocation does no environment allocation, source copy, dependency solve,
sync, or cache maintenance. `--isolated` retains the explicit legacy path.

The built wheel passed offline initialize/tools-list exchanges for NDP, Geo,
Pandas, and Plot using the same Python installation. Repeating all four launches
created no CLIO Kit cache directory or per-server environment. A real three-row
CSV was profiled by Pandas and plotted by Plot over MCP, with a valid PNG output
and three reported data points.

## Local evidence

Windows, Python 3.12.0. The science/HPC wheel installation resolved 118 packages
in 2.07 seconds, prepared 117 packages in 20.89 seconds, and installed 118 in
3.10 seconds according to uv. This records one run's install phases, not an HPC
cold-install guarantee.

| Namespace | First process after install | Repeat process |
| --- | ---: | ---: |
| NDP | 6.785 s | 3.344 s |
| Geo | 9.667 s | 5.546 s |
| Pandas | 6.653 s | 4.757 s |
| Plot | 6.137 s | 4.984 s |

Each measurement includes the local MCP handshake, tools/list, and process
teardown. Probes were serial. No comparison against the reported shared HPC
filesystem was performed.

A retained earlier installation of the same science/HPC dependency set contained
14,575 files totaling 678,344,038 logical bytes (about 647 MiB). Bytecode was
redirected outside that environment. These are logical file sizes, not allocated
disk usage or a measured old-versus-new saving; uv hard links can share storage.

## Gates

- CLIO Kit: **185 passed**, zero failures/errors/skips, 178.55 seconds. Includes
  all root tests, built-wheel integration, explicit legacy mode, migration GC,
  dependency-extra parity, runtime identity, publishing metadata, and containment.
- CLIO Agent: **42 passed**, zero failures/errors/skips, 23.72 seconds. Includes
  existing spawn-diet coverage, v1 invalidation, unchanged-shim/source upgrades,
  pip user-install identity, and containment.
- Ruff passed on changed Python files. Mypy passed on eight Kit source/generator
  files, the two containment scripts, and the two Agent spawn-diet source files.
- The Kit lock check and exact file-size ratchet passed; the launcher shrank.
- Both final test harnesses exited successfully after removing their leased run
  trees. Only their base guard files remained.

Logs and JUnit reports are retained under
`D:/Libraries/Documents/projects/clio_develop_workspace/test-runs/hpc-shared-runtime-20260904/`:
`kit-final.log`, `kit-final.xml`, `agent-final.log`, and `agent-final.xml`.

Earlier runs exposed two stale size-baseline expectations and the old Ares
installation expectation; those were corrected and covered by the final green
run. Other earlier runs were interrupted during disk recovery and are not
passing evidence.

## Storage incident and remaining limits

Initial wheel tests used Windows user temp and uv cache defaults. After a disk
alert, validation stopped and a durable [test storage policy](test-storage.md)
was committed in both repositories. Its seven focused safety tests passed before
broad validation resumed. The policy redirects temp/cache/bytecode/CLIO/CTE
state, recovers abandoned marked runs and their children, and fails on cleanup
errors. The committed policy is in Kit `f41ab28`/`0d60150` and Agent
`600a0a83`/`f15be9a5`.

The earlier C: directories were already absent when this task checked them;
no C: space recovery is claimed by this task. Automatic approval review rejected
manual cleanup of the older, unleased D: scratch directories with only
"blocked by policy", including a retry using explicit literal paths. They were
left in place, with **0 bytes claimed freed**. `cleanup-report.json` records
984,578,287 logical bytes under `pytest`, 728,815,040 under `uv-cache`, 9,545,728
under `bytecode`, and an empty `temp` directory in the report root above.

The runtime changes are not published. Install this branch's wheel with the
chosen extras to qualify it with Agent; Agent's normal installer still pins
CLIO Kit 2.10.6, whose launcher behavior is legacy until the paired release.
The later Agent campaign used this candidate installation in a production MCP
boundary test: all four namespaces mounted, real CSV profile and plot calls
succeeded, and durable HTTP lineage was reloaded (**1 passed in 68.49 seconds**).
That campaign also qualified two real vLLM requests on the local WSL2 AVX2 CPU
path. Those later results do not change this report's historical Kit gate and do
not qualify an AMD GPU, HPC filesystem timings, allocated disk savings, an
installed CLIO/CTE UI, or all 24 server deployments. See the Agent campaign
[handoff](../../clio-agent-provider-runtime/docs/design/hpc-mcp-runtime-semantics-1321.md)
and [detailed local vLLM report](../../clio-agent-provider-runtime/docs/design/vllm-local-qualification-20260904.md).
The tested shared science stack and the existing OS permission policy are
separate concerns.

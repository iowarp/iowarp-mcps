# CLIO Kit 2.9.0 — ship plan

Goal: turn the current working tree into a published release — PyPI wheel plus a
marketplace anyone can install from — with nothing half-built and nothing
undecided.

**Where we are.** Branch `feat/360-meta-marketplace`, **4 commits ahead of
origin, not pushed**, on top of `f344cdc`. Version `2.8.0`. 223 tests pass,
ruff and mypy clean, marketplace validates under `--strict`.

**Phase 1 is complete** — the work is committed, so the "everything is
uncommitted" risk is gone. The largest remaining unknown is now the **upgrade
path** (Phase 4), because `6e3455b` moves plugin `source` paths and only fresh
installs have been tested.

**Release reality (from RELEASING.md).** Publication happens from a version tag
on `main`, behind an administrator-managed `pypi` environment and a short-lived
authorization secret bound to the exact tag and commit. An admin must run that
step. No amount of preparation removes that gate, so the plan ends by handing a
clean tag to a release maintainer, not by publishing.

---

## Phase 0 — Decisions (blocking, ~30 min of your time)

Nothing below is a bug. Each is a fork that changes what ships, so answering
them first avoids rework.

| # | Decision | Default if you say nothing |
|---|---|---|
| D1 | Ship all 20 skills, or trim first? | Ship all 20 |
| D2 | `web` sits in `clio-research` but is marked general-purpose. Intended? | Leave as-is |
| D3 | `scientific-catalog` was not in the approved 21. Keep it in `clio-research`? | Keep |
| D4 | Unpinned community entries auto-update users. State as policy? | State it, don't change it |
| D5 | Version: 2.9.0 (new CLI command + new rules) or 3.0.0? | **2.9.0** |
| D6 | Host non-Python servers in this release? | **No — index only** |

**On D1**, the honest read: 20 skills cost roughly 2,000 tokens in *every*
conversation whether or not they fire. You have `evals/trigger_eval.py` and
recorded scenarios on all 20. Running that once before shipping tells you which
skills actually fire, and that is a better basis than intuition. If you want to
trim, trim before release — removing a skill after users have it is a breaking
change to their context budget.

**Exit gate:** D1–D6 answered in writing.

---

## Phase 1 — Land what is already built ✅ DONE

Committed to `feat/360-meta-marketplace`, not pushed:

```
6e3455b  perf(plugins): ship manifests, not the server source they never execute
7a3642f  feat(marketplace): enforce the skill rules, and index federated marketplaces
23c173b  fix(runtimes): stop excluding a node server's shipped artifact
1cc4414  fix(docs): install the launcher before plugins, and verify with mcp list
```

Four commits rather than the six planned: three files each carry two concerns
(`plugins.py`, `generate_server_json.py`), and splitting a file across commits
needs interactive staging that cannot be verified non-interactively. Each
message states what its commit actually contains.

Verified from the committed tree: 223 tests, ruff check and format clean, mypy
clean, `claude plugin validate --strict` passes.

**Remaining here:** push, and open the PR. Not done — awaiting your call.

---

## Phase 2 — Close the last unproven claim (~1 hour)

**The npm indexing path has never been run end to end.** Claude Code genuinely
executes `npm install` (proved by a real E404 from registry.npmjs.org), but no
one has installed an npm-published MCP server through our marketplace. Until
that happens, "index your TypeScript server" is a documented promise with no
evidence behind it.

The package is already built and dry-run clean at
`.clio-installtest/dist/npm-proof/` — `@iowarp/clio-trial-mcp@0.1.0`, 5 files,
1.5 kB.

1. `npm publish --access public` from that directory
2. Add `community/entries/clio-trial.toml` with `type = "npm"`
3. Regenerate, `claude plugin install clio-trial@clio-kit`
4. `claude mcp list` → must report **Connected**
5. Record the result, remove the entry, `npm unpublish`

**Exit gate:** a recorded Connected line, or a written defect if it fails.

> This is the one item I could not do myself: publishing to a public registry is
> irreversible and outward-facing.

---

## Phase 3 — Fix the small real bugs (~half a day)

| Bug | Fix | Why it matters |
|---|---|---|
| Generator silently skips servers it cannot describe — printed "Generated: 22 servers" while ignoring one entirely | Fail loudly on any server directory it cannot describe | A silent omission means a server vanishes from the marketplace with no error. Language-independent bug. |
| `pyproject.toml` ships a `prompts/` directory that does not exist; `clio-kit prompts` always answers "No prompts found." | Remove the phantom path and the dead command, or restore the directory | A shipped command that can never work |
| `clio-kit --version` errors | Add it | Install docs talk about versions; the tool cannot report its own |

**Exit gate:** 223+ tests pass, all three fixed or explicitly deferred with a
reason.

---

## Phase 4 — Upgrade testing (~1 hour, do not skip)

Every install test so far was a **fresh** install. This release moves each
plugin's `source` from `./clio-kit-mcp-servers/<name>` to
`./plugins/clio-<name>`. Users install by name, so no user-facing coordinate
changes — but existing installations hold a cached copy resolved from the old
path.

1. Install `clio-hpc` from the **current released** marketplace
2. Update the marketplace to the new one
3. `claude plugin update`, restart, `claude mcp list`
4. Confirm every server still reports Connected and the cache shrinks

**Exit gate:** an existing install survives the upgrade, or a migration note is
written for the release.

---

## Phase 5 — Release (admin-gated)

Follow `RELEASING.md` exactly; it is stricter than a normal release and the
strictness is deliberate.

1. Bump `pyproject.toml` to the D5 version
2. Update `mcp-server-versions.toml` — `[mcp-registry-release] publish` should
   list only servers whose **contract** changed. No server contract changed this
   cycle, so this is likely empty
3. Merge the release PR to `main`; all required checks green
4. Admin: verify immutable releases are enabled, mint the authorization secret
   in the `pypi` environment, tag, push
5. Verify **both** channels independently:
   - `uv tool install --no-cache clio-kit==<version>` in a temp tool dir
   - `gh release verify v<version>`
6. Smoke test the published article: fresh machine, follow `setup.md` verbatim,
   `claude mcp list` shows Connected

**Exit gate:** both channels verified, setup.md reproduces on a clean machine.

---

## Explicitly out of scope for 2.9.0

**Hosting non-Python servers.** The runtime works — a TypeScript server
completed a full `initialize` + `tools/call` round trip through the launcher.
What is missing is CI and generator support:

- CI discovers servers with `test -f {}/pyproject.toml`, so a Node server would
  ship with **zero** lint, type or lock verification
- the generator would silently omit it (same bug as Phase 3, item 1)
- compiled output must live in `bundle/` — `dist/`, `lib/` and `build/` are all
  gitignored repo-wide, so output placed there is silently dropped

That is roughly a day, and none of it is hard. It is deferred because the cost
is not the work: hosting means every user needs `npm` or `go` on PATH, and
offline install disappears — our Python servers are vendored in the wheel and
need no network, which on a cluster login node decides whether anything works.

Revisit when a specific server genuinely requires it.

---

## Sequencing and effort

```
Phase 0  decisions        30 min   ── blocks everything
Phase 1  land the work    half day ── highest risk until done
Phase 2  npm proof        1 hour   ── needs an npm publish
Phase 3  small bugs       half day ── can run parallel to 2
Phase 4  upgrade test     1 hour   ── must precede release
Phase 5  release          admin    ── gated, not schedulable by us
```

Realistically **two working days** to tag, excluding review latency and the
admin release gate.

## Definition of done

- [ ] D1–D6 answered
- [ ] Working tree committed and merged; 223+ tests green
- [ ] An npm-published server installed through the marketplace and Connected
- [ ] Generator fails loudly instead of silently skipping
- [ ] An existing install survives the upgrade
- [ ] `clio-kit==2.9.0` on PyPI, verified in a clean tool environment
- [ ] `setup.md` followed verbatim on a clean machine ends in Connected servers

## Biggest risks

1. **The work is uncommitted.** Everything else is recoverable; this is not.
   Phase 1 first.
2. **The upgrade path is untested.** Fresh installs all pass. An existing user
   updating into the new plugin layout has never been exercised.
3. **Release is admin-gated and time-boxed.** The authorization secret expires
   in one hour and binds to an exact commit, so the tagging window needs a
   maintainer actually available, not just nominally assigned.

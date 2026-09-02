# CLIO Kit — mentor demo, from scratch

Every command here was run on this machine. Every prompt in Act 5 is copied from
a recorded eval run where that skill provably fired. Nothing below is written
from memory.

**Runtime: ~6 minutes live**, plus a one-time warm-up you do beforehand.

---

## Before the mentor arrives (10 min, once)

Servers build their dependencies from a pinned lock on first launch. That is the
only slow step in the system, and you do not want it happening live.

```bash
cd /path/to/clio-kit

# If a released clio-kit is already on PATH, remove it first, or the demo runs
# PyPI's launcher against your branch's plugins and you cannot honestly say the
# launcher is your work.  Check with: uv tool list | grep clio-kit
uv tool uninstall clio-kit 2>/dev/null

# --force --reinstall is required: a plain `uv tool install .` updates the
# receipt and leaves the old environment in place, so `uv tool list` will
# cheerfully report the new version while the old code still runs.
uv tool install --force --reinstall .    # installs THIS branch
export PATH="$HOME/.local/bin:$PATH"
clio-kit mcp-servers       # confirm it resolves before going further

# warm the servers the demo touches
for s in hdf5 adios parquet compression slurm node-hardware; do
  echo "warming $s"; timeout 600 clio-kit mcp-server "$s" < /dev/null > /dev/null 2>&1
done

# reset so the demo starts genuinely clean
uv tool uninstall clio-kit
claude plugin marketplace remove clio-kit 2>/dev/null
```

The built environments stay in `~/.cache/clio-kit`, so the live run reuses them
and starts in seconds.

**Also open in a second terminal:** `watch -n1 du -sh ~/.claude/plugins/cache/clio-kit`
if you want the size number visible while you talk.

---

## Act 1 — Install the launcher (45 s)

> "CLIO Kit is two things: a launcher, and a marketplace. Every plugin is a
> manifest that invokes the launcher. The plugin holds no server code at all."

```bash
uv tool install clio-kit      # from a clone: uv tool install .
clio-kit mcp-servers
```

**Expect:** 22 servers, grouped `Scientific:` and `General purpose:`.

> "This is the part our own setup guide used to get wrong. It told the agent to
> install plugins but never the launcher — so you got seven plugins reporting
> *enabled* and five servers dead with `ENOENT: clio-kit`. We only found it by
> following our own instructions literally."

---

## Act 2 — Marketplace and a bundle (60 s)

```bash
claude plugin marketplace add ./          # or iowarp/clio-kit once merged
claude plugin install clio-scientific-io@clio-kit
```

**Expect:**

```
✔ Successfully installed plugin: clio-scientific-io@clio-kit (scope: user)
  (+ 5 dependencies: clio-adios, clio-compression, clio-hdf5, clio-parquet,
     clio-scientific-io-skills)
```

> "One bundle pulled in four servers and a skill pack. A bundle is about ten
> lines — it *names* its members rather than containing them, so it cannot drift
> from what it bundles."

**The number to show:**

```bash
du -sh ~/.claude/plugins/cache/clio-kit
```

**Expect ~430 KB** for the bundle, its four servers and its skill pack. Say what
it was:

> "Last week this was 991 megabytes. The marketplace pointed each plugin at the
> server's whole source directory, and the client copies a plugin's source
> wholesale — so every install carried `src/`, `tests/` and a built `.venv`, none
> of which ever executes. Now the plugin is just two manifest files. Same
> function, 5,400× smaller."

---

## Act 3 — Servers actually connect (45 s)

```bash
claude mcp list
```

**Expect** every `plugin:clio-*` line ending `✔ Connected`:

```
plugin:clio-adios:clio-adios:             clio-kit mcp-server adios       - ✔ Connected
plugin:clio-compression:clio-compression: clio-kit mcp-server compression - ✔ Connected
plugin:clio-hdf5:clio-hdf5:               clio-kit mcp-server hdf5        - ✔ Connected
plugin:clio-parquet:clio-parquet:         clio-kit mcp-server parquet     - ✔ Connected
```

> ⚠️ **There is no MCP server called `clio-kit`.** Do not go looking for one.
> `clio-kit` is the launcher, and it appears in the *command* column on the
> right. The servers carry their own names — `clio-adios`, `clio-hdf5`,
> `clio-parquet`. Seeing `clio-kit mcp-server <name>` in that column is exactly
> the point: one launcher, many servers, and the plugin holds neither.

> "This is the check that matters. `claude plugin list` reports *enabled* even
> when every server underneath is broken — it literally cannot detect the failure
> mode we shipped. So the setup guide now ends on `claude mcp list`."

---

## Act 4 — Community: the meta-marketplace (90 s)

The part mentors probe hardest: is this a catalogue of your own work, or a real
marketplace?

First, a five-second moment worth having — the namespace is protected:

```bash
clio-kit plugin init /tmp/clio-demo
```

```
Error: name 'clio-demo' claims the reserved 'clio-' prefix, which is generated
from CLIO Kit's own servers, bundles and skills
```

> "An outside plugin cannot shadow one of ours by claiming our prefix."

Now the real one. **Use a path that does not exist yet** — `plugin init` refuses
to overwrite an existing manifest, so pick a fresh name each rehearsal or delete
the old directory first:

```bash
clio-kit plugin init /tmp/materials-lab
clio-kit plugin validate /tmp/materials-lab
```

**Expect:**
```
Scaffolded materials-lab in /tmp/materials-lab
Next: edit the manifest and the skill, then `clio-kit plugin validate`

OK: materials-lab would publish correctly
1 skill(s), ~228 characters carried in every session whether or not they fire.
```

**Expect** validation to pass *and* report the always-on cost:

```
OK: demo-plugin would publish correctly
1 skill(s), ~228 characters carried in every session whether or not they fire.
```

Now break it deliberately — this is the strongest 20 seconds of the demo:

```bash
rm /tmp/materials-lab/skills/example-workflow/evals.md
clio-kit plugin validate /tmp/materials-lab
```

**Expect a refusal:**

```
- example-workflow records no eval scenarios; add evals.md with the situations
  this skill was checked against. A skill with none is untested by definition.
Error: 1 problem(s) in /tmp/materials-lab
```

> "Outside contributions are indexed, not vendored — their code stays in their
> repo, on their release schedule, and we merge one file. But because we are not
> reviewing their code, the shape has to be checked mechanically. A skill with no
> recorded scenarios is untested by definition, and it never reaches the
> marketplace."

Then the submission itself:

```bash
# put the evals file back first, or submit refuses it too
clio-kit plugin submit /tmp/materials-lab --repo iowarp/materials-lab
```

**Expect** a ready-to-PR TOML entry.

> "Four source types — github, git-subdir, npm, url. So a TypeScript MCP server
> published to npm is listable without a line of its code living in our repo."

### Now show it with something real (this is the part that lands)

Do not stop at the scaffold. The catalogue indexes a **real, public repository**:
`iowarp/clio-core`, the sister project's own marketplace. Show the entry:

```bash
cat community/entries/iowarp-contributing.toml
```

```toml
name        = "iowarp-contributing"
description = "Uniform contributing guidelines for the IOWarp/Clio ecosystem..."
maintainer  = "Gnosis Research Center"

[source]
type = "git-subdir"
url  = "https://github.com/iowarp/clio-core.git"
path = ".claude-plugin/plugins/iowarp-contributing"
```

Then install it **from our marketplace**:

```bash
claude plugin install iowarp-contributing@clio-kit
claude plugin details iowarp-contributing@clio-kit
```

**Expect:**
```
✔ Successfully installed plugin: iowarp-contributing@clio-kit (scope: user)

Per-component (rounded)
  component      always-on  on-invoke
  contributing         ~70      ~5.5k
  git-etiquette        ~40       ~580
Always-on:   ~114 tok
```

> "That plugin lives in a different repository, in a subdirectory of a monorepo.
> We sparse-cloned 52 KB of it. Its skill and its agent both resolved. Nothing
> about it lives in CLIO Kit except one TOML file — and when they push, our
> users get it on their next marketplace update, with no release from us."

### And a whole marketplace, indexed as a referral

```bash
clio-kit marketplaces
```

**Expect:**
```
iowarp-clio -- Official IOWarp marketplace for the Clio ecosystem: dev environment
               setup, contributing guidelines, and team workflow consistency.
  maintained by Gnosis Research Center, indexed here but not reviewed here
  claude plugin marketplace add iowarp/clio-core

Read from the marketplace, as of its last update.
```

That last line matters. The referral is published *inside the marketplace*, so a
new catalogue reaches users on their next `marketplace update` with no clio-kit
release. If it instead says *"Read from clio-kit 2.8.0, which may be behind the
marketplace"*, the marketplace has not been added — that is the fallback.

> "Claude Code has no nested-marketplace concept — I tested it, it reports
> `Unknown field 'kind'` and ignores it. So a whole catalogue is carried as a
> referral: we list it, and hand the user the one command that adds it. Theirs
> stays theirs."

**If asked how fresh that list is:** the referral lives beside `marketplace.json`
as `.claude-plugin/federated-marketplaces.json`, so it travels with the
marketplace and refreshes on update. A copy is also baked into the wheel as a
fallback for anyone who has not added the marketplace, and the command tells you
which source it used. It could not go *inside* `marketplace.json` — a custom key
there fails `claude plugin validate --strict` as an unknown field, same as
`kind` does.

---

## Act 5 — A skill firing (2 min)

```bash
claude plugin details clio-scientific-io-skills@clio-kit
```

**Expect:**

```
Skills (3)  choosing-a-storage-format, reading-large-datasets-safely,
            exploring-an-unfamiliar-dataset
Always-on:  ~422 tok   added to every session
```

> "That number is the honest cost. A skill is carried in every conversation
> whether it fires or not, so it has to earn its place."

Now start Claude Code **in the fixtures directory** so the data file exists:

```bash
cd evals/fixtures && claude
```

### Query 1 — a tool-using skill (the main event)

Paste exactly:

```
Someone handed me sim.h5. Tell me what is in it, including units, and show me a
few values from the temperature data. Do not read the whole array.
```

**Expect** Claude to invoke `exploring-an-unfamiliar-dataset`, then inspect the
file structure, read attributes for units, and slice a few values rather than
reading the array whole.

*Recorded run: fired, 14 tool calls, 0 failures — the cleanest of the twenty.*

### Query 2 — a knowledge skill, no server needed

```
I have a 4-D simulation field and a table of run parameters. How should I store
each, and how should I chunk the field if it is mostly read one timestep at a
time?
```

**Expect** `choosing-a-storage-format` to fire and answer with HDF5-vs-Parquet
reasoning plus a chunking recommendation. No tool calls at all.

> "This is the kind of skill that pays for itself. The tools cannot tell you
> whether 4 MB chunks are right — that is judgement, and it is exactly what does
> not fit in a tool description."

### Query 3 — only if you installed `clio-hpc` too

```
Write me an sbatch script for a 16-rank MPI run of ./solver that needs about 90
minutes, sized against this machine.
```

**Expect** `writing-slurm-job-scripts` to fire and check the machine's real
limits before choosing numbers. *Recorded: fired, 4/4 tools ok.*

---

## The story to tell about skills

This is the most interesting result in the project, and it is worth leading with
rather than hiding.

We ran all twenty skills against real servers and recorded what happened.
**Only 7 of 20 ever fired.**

|                                     | fired   |
| ----------------------------------- | ------- |
| Skills with**no** MCP servers | 4 of 4  |
| Skills**with** MCP servers    | 3 of 16 |

It was not a wording problem. `writing-slurm-job-scripts` triggers on the literal
word *sbatch*, and the test prompt said *"write me an sbatch script."* It still
did not fire.

**The cause:** a description that names the *task* offers the model nothing the
visible tools do not already offer, so it calls the tools and skips the skill.
The three tool-using skills that did fire all named a *failure* instead — a read
that "would exhaust context", one that "has failed".

So every non-firing description was rewritten to lead with the specific wrong
thing that happens without it — statistics computed before profiling, citations
invented from memory, a bounding box that renders cleanly and is geometrically
wrong. Triggers and boundaries unchanged; no skill changed what it covers.

**Result: 19 of 20 now fire.** Verified one skill first
(`writing-slurm-job-scripts`: did-not-fire → fired on the identical prompt and
fixtures) before applying the pattern to the rest.

The remaining one, `surveying-literature-and-datasets`, exhausts the harness's
$0.60 per-skill budget before returning a verdict — a harness limit, not a
measured failure. Say that plainly if asked; it is the one skill still unproven.

---

## Cleanup

```bash
claude plugin uninstall iowarp-contributing@clio-kit
claude plugin uninstall clio-scientific-io@clio-kit
claude plugin prune -y
claude plugin marketplace remove clio-kit
rm -rf ~/.claude/plugins/cache/clio-kit
rm -rf /tmp/materials-lab /tmp/clio-demo
uv tool uninstall clio-kit
```

---

## If something breaks live

| Symptom                                               | Cause                           | Fix                                                                             |
| ----------------------------------------------------- | ------------------------------- | ------------------------------------------------------------------------------- |
| `ENOENT: Executable not found in $PATH: "clio-kit"` | launcher missing or PATH stale  | `uv tool install clio-kit && uv tool update-shell`, open a new shell          |
| A server hangs on first connect                       | building deps from its lock     | you skipped the warm-up;`claude mcp list` again after it finishes             |
| Tools never appear in Claude Code                     | session not restarted           | restart — MCP servers connect at session start                                 |
| A skill does not fire                                 | model's choice, not a hard rule | say so honestly; rerun the query, or fall back to Query 2 which needs no server |
| `Unknown plugin`                                    | marketplace not added           | `claude plugin marketplace list`                                              |

---

## Four numbers to lead with

1. **184 KB**, down from **991 MB**, to install a six-plugin bundle — 5,400×
2. **22 servers, 6 bundles, 20 skills**, one launcher, one marketplace
3. **19 of 20 skills fire**, up from 7 — measured before and after, not assumed
4. **223 tests**, ruff and mypy clean

## Three questions a mentor will ask, and the honest answer

**"Does the marketplace really take outside work?"**
Yes — indexed, not vendored. Four source types. I installed an external plugin
from a git URL end to end and its skill and MCP server both resolved. The one
gap: nobody has installed an *npm-published* server through it yet. The test
package is built and dry-run clean; it needs one publish to close.

**"Can you host a Go or TypeScript server?"**
The launcher can — a TypeScript server completed a full `initialize` and
`tools/call` round trip through it. We choose not to host: it would cost offline
install, which our Python servers have because they are vendored in the wheel,
and that matters on a login node with no outbound network. So non-Python servers
are indexed instead.

**"How do you know the skills help?"**
We measured. 7 of 20 fired, we found out why, fixed it, and now 19 of 20 fire.
The rules we enforce on contributors check a skill's *shape*; the eval harness
checks whether it *activates*. Both are in the repo.

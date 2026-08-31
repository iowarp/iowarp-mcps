# Set up CLIO Kit

Instructions for an AI agent. Follow them in order. Each step says how to check
it worked before moving on.

If you are reading this from a clone, the marketplace can also be added from
that clone directly: `claude plugin marketplace add ./` from the repository root,
which is useful before this lands on the default branch. Read the note in Step 2
before you do — a clone install copies more than you expect.

CLIO Kit publishes MCP servers for scientific computing, grouped into workflow
bundles. Installing a bundle brings in its servers plus written procedures for
using them together.

**Two things get installed, and both are required.** A plugin is a manifest that
runs `clio-kit`; it does not contain the server. If you install plugins without
the `clio-kit` launcher, every plugin reports `enabled` and every server fails to
connect. Step 1 installs the launcher for exactly this reason.

## Step 1. Install the prerequisites

```bash
claude --version    # any recent version
uv --version        # required
```

If `uv` is missing:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Do not use system `pip`. On current macOS and most Linux distributions it fails
with `externally-managed-environment` (PEP 668). `uv` manages its own Python and
avoids that.

## Step 2. Install the CLIO Kit launcher

Every plugin invokes `clio-kit` by name, resolved from `$PATH`. Install it
before any plugin:

```bash
uv tool install clio-kit
uv tool update-shell     # only if uv says its bin directory is not on PATH
```

Check it, and start a new shell first if `update-shell` changed anything:

```bash
clio-kit mcp-servers
```

Expect a grouped list of 22 servers. If you get `command not found`, `$PATH` has
not picked up `~/.local/bin` yet — open a new shell and try again. **Do not
continue until this command prints servers.** Everything after this point
depends on it.

Installing from a clone instead of PyPI:

```bash
uv tool install .        # from the repository root
```

## Step 3. Add the marketplace

```bash
claude plugin marketplace add iowarp/clio-kit
```

Expect: `Successfully added marketplace: clio-kit`.

CLIO Kit is a monorepo, so a full clone is large. To fetch only what the
marketplace needs:

```bash
claude plugin marketplace add iowarp/clio-kit \
  --sparse .claude-plugin plugins skills community
```

The server tree is deliberately absent from that list. Every plugin is a
manifest that invokes the `clio-kit` launcher you installed in Step 2; none of
them contains server code, so none of it needs fetching.

## Step 4. Decide what to install

Ask the user what they work on, then match it to one bundle. Do not install
everything. Each installed server adds tools to every conversation, and each
skill adds text carried in every session whether it fires or not.

| If the user works on | Install |
|---|---|
| Running codes on a cluster, Spack, Slurm, JARVIS pipelines | `clio-hpc` |
| Why a finished job was slow, I/O profiling, large logs | `clio-performance` |
| HDF5, ADIOS BP5, Parquet, compressed data files | `clio-scientific-io` |
| Statistics, plotting, ParaView, simulation visualisation | `clio-analysis` |
| GeoJSON, terrain, seismic waveforms, earthquake catalogs | `clio-geoscience` |
| Literature search, arXiv, finding datasets | `clio-research` |

If the user names one server rather than a workflow, install that server alone:
`clio-hdf5`, `clio-slurm`, and so on. Run `claude plugin marketplace list` to
see every entry.

If they already have the servers and want only the written procedures, install
`clio-<bundle>-skills`.

The marketplace also indexes contributions from outside this repository. Those
entries carry `metadata.indexed`, which marks them as pointed at rather than
maintained here. Install them the same way.

## Step 5. Install

```bash
claude plugin install clio-hpc@clio-kit
```

Expect a line naming the dependencies it pulled in, for example
`(+ 6 dependencies: clio-jarvis, clio-lmod, clio-node-hardware, ...)`.

A bundle is a manifest listing its members, so installing it installs them. You
do not install the servers separately.

## Step 6. Verify that the servers actually connect

`claude plugin list` only proves the manifests were read. It reports `enabled`
for plugins whose servers are completely broken, so it cannot be the check.

Restart the Claude Code session first — MCP servers connect at session start —
then run:

```bash
claude mcp list
```

Every `plugin:clio-*` line must end in `✔ Connected`. A server's first start
builds its dependencies from a pinned lock, so allow it time and a network.

If you see `✘ Failed to connect — ENOENT: Executable not found in $PATH:
"clio-kit"`, Step 2 did not take effect in this shell. Fix that before anything
else; no amount of reinstalling plugins will help.

Then report the ongoing context cost to the user:

```bash
claude plugin details clio-hpc-skills@clio-kit
```

This prints the skills that loaded and the tokens they add to every session.
That number is what you installed, paid on every conversation.

## If something fails

**`Unknown plugin`** -- the marketplace was not added, or the name is wrong. Run
`claude plugin marketplace list` and use a name exactly as it appears.

**`ENOENT: Executable not found in $PATH: "clio-kit"`** -- the launcher is not
installed or not on `$PATH`. Go back to Step 2. This is the most common failure
and it makes every server fail at once.

**Servers install but their tools never appear** -- the session was not
restarted. MCP servers connect at session start.

**A server fails to start** -- it builds its dependencies from a pinned lock on
first run, which takes time and needs network. Run
`clio-kit mcp-server <name>` directly to see the real error.

**Disabling a server is refused** -- a bundle still depends on it. Disable the
bundle first, or leave it.

## Removing

```bash
claude plugin uninstall clio-hpc@clio-kit
claude plugin prune -y
claude plugin marketplace remove clio-kit
```

Uninstalling does not reclaim the copied plugin sources. Remove them explicitly:

```bash
rm -rf ~/.claude/plugins/cache/clio-kit
```

To remove the launcher and the server runtimes it built:

```bash
clio-kit cache gc --all     # or: rm -rf ~/.cache/clio-kit
uv tool uninstall clio-kit
```

## Do not

- Install plugins before the launcher. Every server will fail with `ENOENT`.
- Report success on `claude plugin list`. It says `enabled` for broken servers.
  Use `claude mcp list`.
- Install every bundle to be safe. Tools and skills cost context in every
  conversation. Install what the user asked for.
- Report success before restarting the session and confirming tools respond.
- Use `pip install` for anything here.

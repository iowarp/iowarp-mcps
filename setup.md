# Set up CLIO Kit

Instructions for an AI agent. Follow them in order. Each step says how to check
it worked before moving on.

If you are reading this from a clone, the marketplace can also be added from
that clone directly: `claude plugin marketplace add .` from the repository root,
which is useful before this lands on the default branch.

CLIO Kit publishes MCP servers for scientific computing, grouped into workflow
bundles. Installing a bundle brings in its servers plus written procedures for
using them together.

## Step 1. Check prerequisites

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

## Step 2. Add the marketplace

```bash
claude plugin marketplace add iowarp/clio-kit
```

Expect: `Successfully added marketplace: clio-kit`.

CLIO Kit is a monorepo, so a full clone is large. To fetch only what the
marketplace needs:

```bash
claude plugin marketplace add iowarp/clio-kit \
  --sparse .claude-plugin plugins skills clio-kit-mcp-servers
```

## Step 3. Decide what to install

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

## Step 4. Install

```bash
claude plugin install clio-hpc@clio-kit
```

Expect a line naming the dependencies it pulled in, for example
`(+ 6 dependencies: clio-jarvis, clio-lmod, clio-node-hardware, ...)`.

A bundle is a manifest listing its members, so installing it installs them. You
do not install the servers separately.

## Step 5. Verify

```bash
claude plugin list
```

Every plugin should read `enabled`. Then:

```bash
claude plugin details clio-hpc-skills@clio-kit
```

This prints the skills that loaded and the tokens they add to every session.
Report that number to the user. It is the ongoing cost of what you installed.

Restart the Claude Code session so the MCP servers connect, then confirm the
tools are reachable before telling the user setup is done.

## If something fails

**`Unknown plugin`** -- the marketplace was not added, or the name is wrong. Run
`claude plugin marketplace list` and use a name exactly as it appears.

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
claude plugin marketplace remove clio-kit
```

## Do not

- Install every bundle to be safe. Tools and skills cost context in every
  conversation. Install what the user asked for.
- Report success before restarting the session and confirming tools respond.
- Use `pip install` for anything here.

# Community contributions

Plugins, skills and MCP servers that live in **someone else's repository** and
appear in the CLIO Kit marketplace. One file here per contribution.

Your code stays yours. You release on your own schedule, and your updates reach
users on their next `/plugin marketplace update` without a release from us. What
this repository holds is a pointer.

## What belongs where

| You have | Where it goes |
|---|---|
| A skill for CLIO Kit's own servers | A PR into `skills/`, not here — it names our tool names, so it has to move when those move |
| Your own MCP server, in any language | An entry here, pointing at your repo |
| Your own plugin, skills and servers together | An entry here |
| Your own marketplace | An entry here, pointing at its index |

## Adding an entry

Create `entries/<name>.toml`. The filename must match the `name` field.

```toml
name        = "materials-lab"
description = "Crystal structure and diffraction skills for materials workflows."
category    = "materials-science"
maintainer  = "some-lab"
keywords    = ["materials", "crystallography"]

[source]
type = "github"
repo = "some-lab/materials-agent-skills"
```

Then open a pull request. We review the entry, not your code — see
`../rework/packaging-design.md` for why that line is drawn where it is.

## Source types

**`github`** — the whole repository is the plugin.

```toml
[source]
type = "github"
repo = "owner/repo"
ref  = "v2.0.0"                              # optional: branch or tag
sha  = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6"    # optional: exact commit, wins over ref
```

**`git-subdir`** — the plugin lives in a subdirectory of a larger repository.
Fetched with a sparse clone, so a monorepo costs no more than the plugin.

```toml
[source]
type = "git-subdir"
url  = "https://github.com/acme/monorepo.git"
path = "tools/claude-plugin"
ref  = "v2.0.0"                              # optional
```

**`npm`** — published as a package. This is how a TypeScript or Go plugin gets
listed without living in this repository at all.

```toml
[source]
type     = "npm"
package  = "@acme/claude-plugin"
version  = "^2.0.0"                          # optional
registry = "https://npm.example.com"         # optional, for a private registry
```

**`url`** — a git repository somewhere other than GitHub.

```toml
[source]
type = "url"
url  = "https://gitlab.example.com/team/plugin.git"
ref  = "main"                                # optional
```

## Trying something before you index it

An entry here publishes to every user on their next marketplace update, so try
a contribution locally first. Nothing below touches this repository or your own
Claude Code config.

**A bare skill folder is not installable.** A `SKILL.md` on its own — the shape
most skill catalogues publish — has no `plugin.json`, so nothing can install it.
Wrap it first:

```bash
clio-kit plugin init /tmp/trial            # scaffold a plugin
rm -rf /tmp/trial/skills/example-workflow  # drop the placeholder
cp -r <their-skill-folder> /tmp/trial/skills/
clio-kit plugin validate /tmp/trial
claude plugin validate /tmp/trial --strict
```

**Then install it into a throwaway config**, so your real one is untouched:

```bash
export HOME=/tmp/trial-home && mkdir -p "$HOME"
claude plugin marketplace add /tmp/trial-marketplace
claude plugin install <name>@<marketplace> --scope user
claude plugin details <name>@<marketplace>   # skills found, and what they cost
```

`plugin details` is the number that decides whether something earns its place:
it reports the always-on cost a skill adds to *every* session, whether or not it
fires.

**What to look at before indexing:**

- Does every skill carry recorded scenarios (`evals.md`)? A skill with none is
  untested by definition. Ours are required to have them.
- Is the description triggers-only? A description restating what the body says
  is context paid forever for nothing.
- Does it declare boundaries against skills we already ship? Twenty skills with
  overlapping domains will hijack each other without "Not for X; use Y".
- What is the always-on total once it is added to what we already publish?

## Rules the generator enforces

Generation fails, rather than publishing something broken, when:

- the filename and the `name` field disagree
- `name` starts with `clio-`, which is reserved for plugins generated from this
  repository's own servers, bundles and skills
- `name` collides with a generated plugin or another community entry
- `description` is missing — it is what a user reads before installing
- `[source]` names an unknown type, omits a field that type requires, or carries
  a field that type does not use

## Pin your source if your users need stability

Without `ref` or `sha`, an entry tracks your default branch, so every push
reaches users on their next marketplace update. That is often what you want. If
it is not, pin it.

## What we ask of you

Keep the repository reachable and the plugin installable. If you stop
maintaining it, open a PR removing the entry — a listing that fails to install
is worse for a user than no listing.

Nothing here is reviewed line by line on every update, and users can see that:
each entry carries `metadata.indexed`, so the catalogue distinguishes what we
maintain from what we point at.

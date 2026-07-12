# Release procedure

CLIO Kit publishes from version tags on `main`. The workflow validates every
embedded lock including the agentic-search lock, runs the root, JARVIS, SLURM,
Spack, ChronoLog, and ADIOS release suites with zero skipped tests, builds every
server package, tests an isolated installed root wheel, attests the root
distributions, publishes to PyPI, and creates a verified immutable GitHub
release. Pull requests and `main` commits build and validate release artifacts
but do not publish advisory development packages to TestPyPI; only a qualifying
production tag publishes package bytes.

The quality workflow treats MyPy and every supported Python test lane as
required. Changes to the root lock, agentic-search lock, server-version map, or
workflow infrastructure trigger the full applicable matrix. Pytest JUnit
reports are rejected when they contain any skipped test.

Before creating a tag, an administrator must verify immutable releases. This
endpoint requires administration read access, which the Actions `GITHUB_TOKEN`
cannot be granted:

```bash
test "$(gh api \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/iowarp/clio-kit/immutable-releases \
  --jq .enabled)" = true
```

The operator must therefore publish a short-lived, exact authorization through
the `pypi` environment secret after this external check. Environment secrets in
an organization repository require repository `admin` access to manage; do not
use a repository Actions variable, which repository writers can replace. The
workflow accepts only an authorization bound to `iowarp/clio-kit`, the intended
stable tag, the exact current `main` commit, the enabled immutable-release
setting, and an integer verification time. It rejects future records, records
older than one hour, unknown fields, and reuse for a different repository, tag,
or commit. The workflow reads and validates the environment secret inside the
protected PyPI job immediately before upload, so queueing or environment-review
time cannot bypass the one-hour limit.

The `pypi` environment must remain an administrator-managed production boundary:
require an independent reviewer, prevent self-review, and restrict deployments
to release tags. PyPI trusted publishing must remain scoped to this repository,
`publish.yml`, and the `pypi` environment. These controls prevent a repository
writer from bypassing the authorization step in a modified workflow.

Do not tag unless the release PR is merged, all required checks pass, the local
commit equals remote `main`, and the tag matches the project version:

```bash
git fetch origin main --tags
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
version="$(uv run python -c \
  'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
tag="v${version}"
commit="$(git rev-parse HEAD)"
test -z "$(git tag -l "$tag")"
test -z "$(git ls-remote --tags origin "refs/tags/$tag")"
test "$(gh api \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  repos/iowarp/clio-kit/immutable-releases \
  --jq .enabled)" = true
authorization="$(jq -cn \
  --arg repository iowarp/clio-kit \
  --arg tag "$tag" \
  --arg commit "$commit" \
  --argjson verified_at_epoch "$(date +%s)" \
  '{
    schema_version: "clio-kit.release.authorization.v1",
    repository: $repository,
    tag: $tag,
    commit: $commit,
    immutable_releases: true,
    verified_at_epoch: $verified_at_epoch
  }')"
printf '%s\n' "$authorization" | \
  uv run python scripts/release_authorization.py \
    --repository iowarp/clio-kit \
    --tag "$tag" \
    --commit "$commit" \
    --max-age-seconds 3600 >/dev/null
gh secret set CLIO_KIT_RELEASE_AUTHORIZATION \
  --env pypi \
  --repo iowarp/clio-kit \
  --body "$authorization"
test "$(gh secret list --env pypi --repo iowarp/clio-kit \
  --json name --jq \
  'map(select(.name == "CLIO_KIT_RELEASE_AUTHORIZATION")) | length')" = 1
git tag "$tag" "$commit"
git push origin "refs/tags/$tag"
```

The release workflow rejects a tag that is not on `main` or differs from the
wheel version. After publication, verify both channels independently:

```bash
tool_dir="$(mktemp -d)"
tool_bin="$(mktemp -d)"
UV_TOOL_DIR="$tool_dir" UV_TOOL_BIN_DIR="$tool_bin" \
  uv tool install --no-cache "clio-kit==${version}"
"$tool_bin/clio-kit" --help
gh release verify "v${version}" --repo iowarp/clio-kit
gh release view "v${version}" --repo iowarp/clio-kit \
  --json tagName,targetCommitish,isDraft,isImmutable,assets
```

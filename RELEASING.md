# Release procedure

CLIO Kit publishes from version tags on `main`. The workflow validates every
embedded lock, runs the root, JARVIS, Spack, and ChronoLog release suites, builds
every server package, tests an isolated installed root wheel, attests the root
distributions, publishes to PyPI, and creates a verified immutable GitHub
release.

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

Do not tag unless the release PR is merged, all required checks pass, the local
commit equals remote `main`, and the tag matches the project version:

```bash
git fetch origin main --tags
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
version="$(uv run python -c \
  'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')"
test ! "$(git tag -l "v${version}")"
git tag "v${version}" HEAD
git push origin "v${version}"
```

The release workflow rejects a tag that is not on `main` or differs from the
wheel version. After publication, verify both channels independently:

```bash
uvx --isolated --no-cache --from "clio-kit==${version}" clio-kit --help
gh release verify "v${version}" --repo iowarp/clio-kit
gh release view "v${version}" --repo iowarp/clio-kit \
  --json tagName,targetCommitish,isDraft,isImmutable,assets
```

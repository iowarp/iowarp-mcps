# Version Bumping Conventions

This project uses automatic semantic versioning based on commit messages.

## Version Bump Rules

### Patch Bump (0.0.X) - Default
Any commit pushed to `main` will trigger a **patch version bump** by default.

Examples:
```
Fix server discovery for uvx isolated environments
Update documentation
Refactor code structure
```

### Minor Bump (0.X.0)
Commits that introduce **new features** or **enhancements** should trigger a minor bump:

- Start commit message with `feat:`
- Include `[minor]` anywhere in the commit message

Examples:
```
feat: add support for new MCP server type
[minor] Add configuration options for server discovery
feat: implement caching mechanism
```

### Major Bump (X.0.0)
Commits that introduce **breaking changes** should trigger a major bump:

- Include `[major]` anywhere in the commit message
- Include `BREAKING CHANGE:` in the commit message

Examples:
```
[major] Redesign CLI interface - remove deprecated flags
Update API with BREAKING CHANGE: removed legacy endpoints
[major] Change configuration file format
```

## How It Works

1. **Automatic Detection**: GitHub Actions analyzes the commit message on every push to `main`
2. **Version Calculation**: Determines bump type based on patterns in the commit message
3. **File Update**: Updates `version` in `pyproject.toml`
4. **Git Commit**: Creates a new commit with the version bump (`[skip ci]` to prevent loops)
5. **PyPI Publish**: Builds and publishes the new version to PyPI

## Skip Publishing

To push changes without triggering a PyPI publish, include `[skip ci]` in your commit message.

## Examples in Practice

```bash
# Patch bump (0.2.4 → 0.2.5)
git commit -m "Fix bug in server discovery"

# Minor bump (0.2.4 → 0.3.0) 
git commit -m "feat: add new compression server"

# Major bump (0.2.4 → 1.0.0)
git commit -m "[major] Remove deprecated CLI arguments"

# No publish
git commit -m "Update README [skip ci]"
```
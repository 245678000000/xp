---
name: release
description: >
  Prepare a release: version bump, changelog notes, tag guidance. Use when the user
  asks to release, ship a version, or /release.
---

# Release Prep

Prepare a clean release from the current branch state.

## Steps

1. Inspect recent commits since last tag: `git tag --sort=-v:refname | head`, `git log`.
2. Summarize user-facing changes (features, fixes, breaking).
3. Propose:
   - next version (semver)
   - CHANGELOG / release notes bullets
   - tag command (do **not** push tags unless asked)
4. If the project has a version file (`pyproject.toml`, `package.json`, etc.), update it when asked.
5. Verify tests/build if a standard command exists.

## Rules

- Never force-push tags or rewrite published history.
- Do not publish to PyPI/npm unless explicitly requested with credentials already configured.
- Ask before `git push --tags`.

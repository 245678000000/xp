---
name: commit
description: >
  Create a well-formatted git commit from current changes using conventional commits.
  Use when the user wants to commit, says /commit, or asks to save work to git.
---

# Git Commit

Create one clear commit. Do not push.

## Steps

1. Inspect state in parallel:
   - `git status`
   - `git diff` and `git diff --staged`
   - `git log -5 --oneline` (match local message style)
2. Decide what belongs in **this** commit. If mixed concerns are huge, prefer one
   focused commit for the main change; ask before splitting into multiple commits.
3. Stage relevant files only. Never stage secrets (`.env`, credentials, private keys).
4. Draft a conventional commit message:
   - Format: `type(scope): short summary` then optional body
   - Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`
   - Summary: imperative mood, ≤72 chars, explains **why** when non-obvious
5. Commit with a HEREDOC so formatting is preserved:

```bash
git commit -m "$(cat <<'EOF'
type(scope): summary

Optional body with context.
EOF
)"
```

6. Run `git status` after and report the commit hash + subject.

## Rules

- Do not use `--no-verify`.
- Do not amend unless the user explicitly asks and the commit is local/unpushed.
- Do not push.
- If there is nothing to commit, say so and stop.

---
name: pr
description: >
  Create or update a GitHub pull request for the current branch with a clear summary
  and test plan. Use when the user wants a PR, says /pr, or asks to open a pull request.
---

# Pull Request

Open (or update) a PR with a useful description. Confirm before push if the branch is new.

## Steps

1. Gather context in parallel:
   - `git status`, `git branch -vv`
   - `git log --oneline main...HEAD` (or `master` / default base)
   - `git diff main...HEAD` (adjust base as needed)
   - `gh pr view` if a PR already exists
2. Ensure the branch is pushed:

```bash
git push -u origin HEAD
```

Ask first if push would publish unexpected commits or force anything.

3. Create the PR with `gh`:

```bash
gh pr create --title "type: summary" --body "$(cat <<'EOF'
## Summary
- What changed and why (2–4 bullets)

## Test plan
- [ ] How you verified (commands, manual checks)

## Notes
- Risk / rollout / follow-ups if any
EOF
)"
```

4. If a PR already exists, update the body/title with `gh pr edit` instead of opening a duplicate.
5. Return the PR URL.

## Rules

- Prefer the repo's PR template if one exists (`.github/PULL_REQUEST_TEMPLATE*`).
- Title should match conventional-commit style when the project uses it.
- Do not force-push. Do not merge.
- Include a real test plan, not placeholders only.

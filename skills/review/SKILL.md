---
name: review
description: >
  Review code changes for correctness, design, and risk. Use when the user wants a
  code review, /review, or feedback on a diff/PR.
---

# Code Review

Review the current branch or specified files. Prefer evidence over taste lectures.

## Steps

1. Establish scope:
   - `git status`, `git diff` / `git diff main...HEAD` (or asked base)
   - List changed files and risk areas
2. Read the real diffs and surrounding code — do not invent issues.
3. Check for:
   - Correctness / edge cases / error handling
   - Security (secrets, injection, path traversal)
   - API/contract breaks
   - Missing tests for new behavior
   - Unnecessary complexity or wrong layer
4. Optionally `spawn_task` to investigate a specific module while you summarize another.

## Output

Prioritize findings:

1. **Blockers** — must fix before merge
2. **Suggestions** — valuable improvements
3. **Nits** — optional style notes (keep few)

For each finding: file path, what's wrong, why it matters, concrete fix direction.
If nothing serious: say so and note residual risk.

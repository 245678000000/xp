---
name: ship
description: >
  End-to-end implement → verify → commit loop for a clear coding task. Use when the
  user wants something fully done and committed, or says /ship.
---

# Ship Loop

Complete a focused task and leave the tree clean and committed (no push unless asked).

## Phases

### 1. Scope

- Restate the goal in one sentence.
- Identify success criteria (tests to pass, behavior to show).
- If scope is ambiguous or multi-day, stop and ask — do not invent product decisions.

### 2. Implement

- Read existing patterns first; extend them rather than inventing parallel structure.
- Make the smallest coherent change set.
- No unsolicited docs or drive-by cleanups outside the task.

### 3. Verify

Run whatever the repo already uses, preferring the narrowest useful checks:

- unit/integration tests for touched areas
- typecheck / lint if configured
- a manual smoke command if no automated test exists

Do not claim "done" without evidence.

### 4. Commit

If verification looks good and the user invoked `/ship` (or clearly wants a commit):

1. Follow the **commit** skill flow (conventional message, no secrets, no `--no-verify`)
2. Report hash + summary of changes
3. **Do not push or open a PR** unless the user also asked (`/pr`)

### 5. Handoff

Final message structure:

```
## Done
- ...

## Verification
- commands + results

## Commit
- hash + subject

## Follow-ups (optional)
- ...
```

## Stop conditions

- Verification fails and you cannot fix within a few iterations → report failure state
- Need product/API secrets/credentials you do not have → ask
- Would require force-push or rewriting published history → refuse and explain

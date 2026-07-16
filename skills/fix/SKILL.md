---
name: fix
description: >
  Systematically investigate and fix a bug. Use when the user reports a failure,
  stack trace, flaky test, or says /fix. Prefer root-cause fixes over symptoms.
---

# Bug Fix Loop

Find the root cause, fix it, and prove it.

## Process

### 1. Reproduce

- Capture the exact error, command, or user path that fails.
- Reproduce with the smallest command/test possible.
- If you cannot reproduce, say what you tried and what is still missing.

### 2. Localize

- Read the stack trace / logs carefully.
- Search for the failing symbol and recent related changes (`git log -p -- path`).
- Trace data flow: input → boundary → logic → side effect.
- Form **one primary hypothesis** before large edits.

### 3. Fix

- Prefer the minimal change that addresses the root cause.
- Avoid shotgun patches (many speculative edits).
- Match existing error-handling and logging style.
- Add or update a regression test when the project has a test harness and the bug is unit/integration-testable.

### 4. Verify

- Re-run the failing case.
- Run the nearest relevant test suite / typecheck / lint the project already uses.
- Check for nearby regressions (call sites, similar code paths).

### 5. Report

Return:

1. **Root cause** (1–3 sentences)
2. **Fix** (what changed, key files)
3. **Evidence** (commands run + outcomes)
4. **Residual risk** (if any)

## Anti-patterns

- Guessing without reading the failure site
- Catching-and-swallowing errors to "make it green"
- Disabling tests or skipping hooks
- Large refactors mixed into a bugfix without being asked

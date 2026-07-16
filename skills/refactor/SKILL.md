---
name: refactor
description: >
  Refactor code for clarity without changing behavior. Use when the user asks to
  clean up, simplify, restructure, or /refactor.
---

# Refactor

Improve structure while preserving behavior.

## Steps

1. Define the target smell (long function, duplication, wrong layer, etc.).
2. Capture a safety net: run existing tests, or add a characterization test first if none exist.
3. Make small, reviewable steps; prefer `apply_patch` / `str_replace`.
4. Re-run tests after each meaningful step.
5. Stop when the smell is gone — no drive-by rewrites.

## Rules

- No behavior changes, feature adds, or public API renames unless asked.
- Do not mix refactors with bug fixes in the same change unless the user wants that.
- Prefer deleting dead code over adding abstraction.

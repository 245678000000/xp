---
name: test
description: >
  Add or improve automated tests for the current change. Use when the user asks for
  tests, pytest, coverage, or /test.
---

# Write Tests

Add focused tests that lock behavior and prevent regressions.

## Steps

1. Identify the behavior under test (diff, failing case, or user story).
2. Match the project's existing test style and runner (`pytest`, `npm test`, etc.).
3. Prefer:
   - Small unit tests for pure logic
   - One integration test for the critical path when needed
4. Run the tests and fix failures you introduced.
5. Do not chase 100% coverage; cover the risky branches.

## Rules

- No flaky sleeps; mock time/network when the suite already does.
- Do not delete failing tests to go green — fix code or fix the test with reason.
- Keep fixtures local unless the repo has a shared pattern.

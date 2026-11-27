---
name: triage
description: Debug a failing behaviour with a reproduce-first, two-strike method
argument-hint: [paste error]
---
Bug report: $ARGUMENTS
If not already given, ask for: EXPECTED, ACTUAL, ERROR (verbatim), REPRO, RECENT CHANGE, SUSPECT.
Do not explore unrelated files.

1. Root-cause hypothesis in <=3 bullets BEFORE editing.
2. Reproduce first: write a failing test that captures the bug; run it and paste the failure.
3. Minimal fix. No refactors. Never change pinned model IDs or openapi.yaml without asking.
4. Run the new test, then the full suite (`cd backend && uv run pytest -q`, `cd frontend && npm run lint`,
   `bash scripts/smoke_demo.sh`). Paste raw output. Done only when all green.
5. One retry max. If still broken: stop, list what you ruled out, and tell the human to /rewind
   and re-prompt with a cleaner report.

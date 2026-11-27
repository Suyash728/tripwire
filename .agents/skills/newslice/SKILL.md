---
name: newslice
description: Build one vertical slice from docs/traceability.md; use when the user runs /newslice N
argument-hint: [slice-number]
disable-model-invocation: true
---
Build slice $ARGUMENTS only. Do not start the next slice.

1. Read AGENTS.md, openapi.yaml, agents/graph.md and docs/traceability.md (if traceability is missing, stop and ask).
2. Plan first (Plan Mode): list requirement IDs covered, files to touch, tests to add. Wait for approval.
3. Build in order, data -> API/agent -> UI:
   - Data: seed rows in backend/app/seed.py or a Supabase migration.
   - API: FastAPI route matching openapi.yaml and the {success, data, error} envelope. Validate all inputs (Pydantic).
   - Agent: plain function unless agents/graph.md names a LangGraph node. Emit a trace event per step.
     ALL model calls go through backend/app/services/llm.py. If the event has a sponsor model, use it when AGENTS.md's Pinned models table names it; never change pinned models without asking.
   - UI: wired to the real route, with a "Load sample case" path. Accessible: labels, keyboard, focus, contrast, aria-live for streaming.
   - Hot path: cache repeat calls and stream long responses.
4. Tests: unit tests plus e2e/axe tests for the slice, including at least one edge case (empty, oversized or bad input).
5. Run and paste RAW output for each (if a tool is not configured, print "NOT CONFIGURED: <tool>", never fake a pass):
   `cd backend && uv run ruff check . && uv run pytest -q --cov=app`
   `cd frontend && npm run lint && npx tsc --noEmit && npx vitest run && npx playwright test`
   `bash scripts/smoke_demo.sh`
6. Tick the covered requirement IDs in docs/traceability.md.
7. Stop. List files changed and propose one commit message.

Use context7 for any library API you are unsure of.

---
name: harden
description: Audit the repo against the six quality pillars at scope freeze
---
Run at scope freeze. Read AGENTS.md (Definition of Done), openapi.yaml, docs/traceability.md and README.md.

1. Audit each pillar against the Definition of Done:
   - Code quality: ruff/eslint clean, no dead code, no TODOs on the demo path, types on public functions.
   - Security: no secrets in git (`git grep -nE '(sk-|gsk_|AIza|eyJ)'`), inputs validated, CORS scoped,
     .env names only in .env.example, Supabase RLS on, no PII in logs or traces.
   - Efficiency: hot path cached/streamed, no N+1 or repeated model calls, router falls back correctly.
   - Testing: unit + e2e/axe on the demo path, at least one edge case per slice, coverage reported.
   - Accessibility: labels, keyboard path, focus order, contrast, aria-live on streaming output (axe clean).
   - Problem alignment: every MUST in AGENTS.md maps to a ticked requirement ID and is visible in the demo.
2. Output one table: pillar | finding | severity (HIGH/MED/LOW) | fix.
3. Fix HIGH findings only. Leave MED/LOW in the table. Never touch openapi.yaml or pinned model IDs.
4. Re-run CI and paste RAW output (print "NOT CONFIGURED: <tool>" rather than skipping silently):
   `cd backend && uv run ruff check . && uv run pytest -q --cov=app`
   `cd frontend && npm run build && npm run lint && npx tsc --noEmit && npx vitest run && npx playwright test`
   `bash scripts/smoke_demo.sh`
5. Update the README "Quality evidence" section: the pillar table, commands run, pass/fail counts, coverage %.

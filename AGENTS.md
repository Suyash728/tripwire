# AGENTS.md: Tripwire (SEED Hackathon 2026, Kill Switch track, team Nexus)

Single source of truth for every coding agent. `CLAUDE.md` is a symlink to this file.
Before any change read: this file, `openapi.yaml`, `agents/graph.md`, `docs/traceability.md`.

## What we build
Tripwire is a gateway in front of an agent network. Fixed rules and canary records quarantine one
agent. A provenance graph decides what to roll back. Compensating writes undo only tainted work.
A receipt proves it. Demo network: Support, Refund, Inventory, Finance agents on a mock D2C store.

## Commands
- `make dev` (or `bash scripts/dev.sh`)      backend API + frontend :3000
- `make mock`     Prism mock of openapi.yaml on :4010 (`npx @stoplight/prism-cli mock openapi.yaml -p 4010`)
- `make test`     ruff + pytest --cov + vitest (`cd backend && uv run pytest -q --cov=app` + `cd frontend && npm run test:coverage`)
- `make e2e`      Playwright demo path + axe (`cd frontend && LLM_MOCK=1 npm run test:e2e`)
- `make bench`    runs the bench harness, prints JSON (containment ms, preserved %, missing entries)
- `make lint`     ruff check/format + eslint/prettier
- `make typecheck` frontend tsc (`cd frontend && npm run typecheck`)
- `make seed CASE=1`   reset DB to seed case 1, 2 or 3
- `bash scripts/ci-local.sh`   full local CI suite (same checks CI runs)

## HARD RULE: no LLM in the containment path
`app/gateway`, `app/policy`, `app/ledger`, `app/provenance`, `app/rollback` must never import
`app/services/llm.py`. Tested by `backend/tests/test_containment_no_llm.py`. The LLM is allowed only
in `app/agents/*` (the demo network) and optionally to phrase the receipt text.

## Model policy (IDs from pins.md, last verified 23 Nov 2026; do not change without asking)
- Router: `app/services/llm.py`, one OpenAI-compatible client, 3 s timeout per tier.
- Tier 1 Groq: `openai/gpt-oss-20b` (demo agents). `openai/gpt-oss-120b` only if 20b fails the hijack spike.
- Tier 2 Gemini: `gemini-3.5-flash-lite` (fallback). `gemini-3.8-flash` ONLY for receipt phrasing (about 20 req/day free).
- Tier 3 local vLLM `http://localhost:8000/v1`: `nvidia/Qwen3-14B-NVFP4`. One model loaded at a time (16 GB VRAM).
- Never use: `gemini-2.5-flash`, `gemini-2.5-pro`, `llama-3.1-8b-instant`, `llama-3.3-70b-versatile` (retired).
- Unsure about an SDK signature: check Context7 or the official docs. Never guess.

## Architecture map
- `backend/app/api/`         FastAPI routes, response envelope
- `backend/app/gateway/`     identity check, call handling, executor
- `backend/app/policy/`      per-agent rules, cumulative caps, canary check
- `backend/app/ledger/`      append-only hash chain, anchor file, verify
- `backend/app/provenance/`  read stamps, edges, NetworkX blast radius
- `backend/app/rollback/`    tool inverse registry, plan and apply, receipt
- `backend/app/agents/`      demo network (live LLM + scripted mode), tool definitions
- `backend/app/bench/`       bench harness and ground-truth metrics
- `backend/app/services/`    llm.py router, supabase client
- `frontend/`                Next.js 14 console (feed, agent cards, graph, receipt, trace panel)
- `db/schema.sql`            tables, triggers, RLS (apply as a migration)
- `seed/`                    seed cases 1-3 with ground-truth labels

## Response envelope (every endpoint)
`{ "success": bool, "data": object | null, "error": { "code": str, "message": str } | null }`

## Domain invariants (do not break)
- Ledger is append-only. `hash = sha256(prev_hash + canonical_json(entry))`. Genesis prev_hash = 64 zeros.
- Appends are serialised with a Postgres advisory lock; `idx` is app-assigned, gapless, starts at 1.
- After each append write the head hash to `ANCHOR_LOG_PATH` (outside the DB).
- Agent identity: HMAC-SHA256 over `agent_id|task_id|tool|canonical(args)|ts|nonce`, per-agent secret. Reject stale ts (>30 s) and reused nonces.
- Reads through the gateway return `{record, version}`; the read set is stamped per `task_id`.
- Taint seed = writes by the tripping agent within the tripping call's `task_id`. Spread is by data: a write is tainted if its read set contains a version produced by a tainted write.
- Rollback = compensating tool calls in descending ledger idx. Each rollback step is itself ledgered (`kind=rollback`, `rollback_of=idx`).
- Replay oracle: DB state after rollback must equal a replay of legit-only actions.
- Irreversible tools never auto-run for a quarantined agent; they are denied.
- Default deny: a tool or table not in the agent's policy is denied.

## Metric definitions (bench)
- Containment ms = time quarantine applied minus time the first malicious call was received.
- Preserved % = legit actions kept / legit actions total (ground truth from `seed/`).
- Taint precision and recall are reported against ground-truth labels.
- Missing ledger entries = calls received minus ledger rows; must be 0.
- Report the measured numbers honestly even when below target (targets: under 2 s, at least 75%).

## UI test IDs (contract for Playwright)
`agent-support`, `agent-refund`, `agent-inventory`, `agent-finance`, `stopwatch`, `chain-status`,
`ledger-row-<idx>`, `blast-graph`, `compare-table`, `receipt`; buttons named "Load sample incident",
"Apply rollback", "Inject fault", "Tamper with a row".

## MUST scope (frozen at 29 Nov 19:00 IST)
R1 identity, R2 ledger + hash chain, R3 provenance, R4 rules + cumulative caps, R5 canaries,
R6 no-LLM containment, R7 quarantine, R8 rollback, R9 receipt, R10 four-agent network,
R11 minimal console, R12 bench harness, R13 three fault types. See `docs/traceability.md`.
SHOULD: R14 offline run on local model, R15 irreversible-action hold.

## WON'T (banned until MUST is demoable)
UPI features, multi-tenant or real auth, real payments, vLLM guard classifier, n8n, LangGraph,
CrewAI, MCP proxy mode, India-specific features.

## Do not touch without asking
`openapi.yaml`, `pins` and model IDs, `.env*`, applied migrations, ledger triggers, `main` (PRs only),
the containment-path import rule, `.claude/hooks/guard.sh`.

## Definition of Done (every slice)
- [ ] Works end to end on seed data
- [ ] Slice tests written and passing, with at least one edge case
- [ ] ruff, prettier/eslint and tsc clean
- [ ] Inputs validated (Pydantic/zod); no secrets or PII in client or logs
- [ ] Keyboard-usable, labelled, contrast OK; axe has no serious or critical issues
- [ ] Hot path (`POST /gw/call`) measured; no N+1 queries
- [ ] Requirement IDs ticked in `docs/traceability.md`
- [ ] CI green; commit message names the requirement IDs

## Disclosure
Payments and the store database are mocked and synthetic. Say so in README and `AI_DISCLOSURE.md`.

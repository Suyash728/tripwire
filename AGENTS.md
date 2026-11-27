# AGENTS.md — <PROJECT NAME>
Single rules file for every coding agent (Claude Code via the CLAUDE.md symlink, Antigravity, opencode). Keep < 150 lines.

## Purpose
<one line: who, pain, our twist>  ← fill at Gate 3 from the problem statement.
- MUST: <feature> — <rubric line / Req ID>   (each MUST maps to a row in docs/traceability.md)
- WON'T: <feature>   (banned until every MUST is demoable)

## Commands
```
bash scripts/dev.sh                          # API :8787 + UI :3000
bash scripts/ci-local.sh                     # full local CI, same steps as .github/workflows/ci.yml
cd backend && uv run ruff check . && uv run ruff format --check .
cd backend && uv run pytest -q --cov=app --cov-report=term-missing
cd backend && uv run bandit -q -r app -ll && uv run pip-audit
cd frontend && npm run lint && npm run typecheck && npm test
cd frontend && npm run test:e2e              # Playwright demo path + axe scan
bash scripts/smoke_demo.sh [--privacy]       # MUST pass before every commit; paste raw output
bash scripts/vllm-up.sh coding|vision|omni|stop|status   # Tier 3 local model (one at a time)
```

## Model policy
- **Every** LLM call goes through `backend/app/services/llm.py` (`chat()`). No provider SDKs anywhere else.
- Tier order: Groq -> (429/timeout/error) Gemini Flash-Lite -> (no network / Privacy Mode) local vLLM.
- If the event has a sponsor model, it becomes Tier 1 when the event says so: add it as a tier in llm.py and to the table below.
- Model IDs come from env/config (`GROQ_MODEL`, `GEMINI_MODEL`, `VLLM_MODEL`, ...), never hard-coded in routes or agents.
- `PRIVACY_MODE` (env) or `privacy_mode` (request) forces the local tier only. `LLM_MOCK=1` returns canned replies (tests/CI).
- VRAM rule: one vLLM model at a time; swap between slices, never during the demo.

| Tier | Model | Notes |
|---|---|---|
| 1 Groq | `openai/gpt-oss-120b` (fast: `openai/gpt-oss-20b`) | 3 s timeout |
| 1 Groq vision | `qwen/qwen3.8-27b` | Preview — image input only |
| 2 Gemini | `gemini-3.5-flash-lite` | fallback, 500 req/day free |
| 2 Gemini hero | `gemini-3.8-flash` | ONE wow call only, 20 req/day free |
| 3 local | `nvidia/Qwen3-14B-NVFP4` @ `http://localhost:8001/v1` | vision: Qwen2.5-VL-7B-NVFP4; omni: Phi-4-mm-NVFP4 |
| Embeddings | `gemini-embedding-2` @768 dims, or local `BAAI/bge-m3` | |
| STT | Groq `whisper-large-v3` | |

## Architecture map
- `backend/app/main.py` — FastAPI routes; envelope `{success, data, error}` on every response (errors too)
- `backend/app/services/llm.py` — the only place model calls happen (3-tier router, cache, mock)
- `backend/app/services/trace.py` — per-run events -> SSE `GET /runs/{id}/events`
- `backend/app/services/store.py` — run persistence: memory by default; Supabase (RLS, caller's JWT) when configured · `supabase/` — config, migrations, pgTAP RLS tests (docs/SUPABASE.md)
- `backend/app/agents/graph.py` — LangGraph (spec: `agents/graph.md`); `crew.py` optional CrewAI (`uv sync --extra crew`)
- `backend/app/seed.py` — sample cases for "Load sample case"; `backend/tests/` — pytest (no real providers)
- `frontend/src/app/page.tsx` — main screen; `frontend/src/components/` — UI (TracePanel); `frontend/e2e/` — Playwright
- `agents/` — agent specs · `n8n/` — workflow exports · `scripts/` — dev, smoke, CI, tunnel, vLLM, event MCP
- `docs/` — traceability.md, TOOLKIT.md, SUPABASE.md · `openapi.yaml` — frozen API contract (Prism mock: `npx @stoplight/prism-cli mock openapi.yaml -p 4010`)

## Conventions
- Response envelope `{success, data, error}` for every route, including 4xx/5xx.
- Pydantic model (with length/size limits) on every request body; TS types (or zod) for every API response on the frontend.
- Typed code: TS strict, Python type hints on public functions. Small functions, feature folders, no dead code, no TODOs on the demo path.

## Security
- No secrets client-side: only `NEXT_PUBLIC_*` values that are safe to publish. No `dangerouslySetInnerHTML`.
- CORS from `CORS_ORIGINS` (never `*` in prod). Rate limits on LLM routes. Validate and size-limit inputs and uploads.
- Prompt-injection guard: system/user message separation, tool allowlist, schema-validated LLM output before acting.
- No PII or secrets in logs or trace events. Supabase RLS on every user table. Security headers on API and UI.

## Accessibility (target WCAG 2.2 AA)
Semantic HTML and landmarks, a label for every control, contrast >= 4.5:1, full keyboard path, visible focus,
`aria-live` for streamed AI output and status changes. axe scan must report no serious/critical violations.

## Efficiency
Async I/O on network calls, TTL cache on LLM/external calls, stream long responses, DB indexes + pagination on lists.

## Definition of Done (every slice)
- [ ] Works end-to-end on seed data ("Load sample case")
- [ ] Unit tests incl. at least one edge case; e2e/axe on the demo path
- [ ] Lint, format and types clean (ruff, eslint, prettier, tsc)
- [ ] Inputs validated; errors return the envelope
- [ ] a11y basics + axe clean
- [ ] Hot path cached or streamed
- [ ] Requirement IDs ticked in docs/traceability.md
- [ ] CI green; commit message names the requirement IDs

## Do-not-touch
- Never read `.env*` (only `.env.example`). Never push to `main`.
- Env setup is a human step: agents may not create or copy env files (`cp .env.example .env.local` is blocked).
- Never edit `openapi.yaml` or change model IDs without asking.
- Never disable tests, skip checks or lower thresholds (COV_MIN etc.) to make CI pass.

## Rules
- Vertical slices only (storage -> API/agent -> UI). One slice per session; start a fresh session after each commit (Claude Code: `/clear`; Antigravity/opencode: start a new session).
- Use the context7 MCP server (configured in all three agents) for any library API you are not certain of.
- Fix fails twice -> stop and restart the session (Claude Code: `/rewind`), then re-prompt with the triage skill.

## Toolkit (details: docs/TOOLKIT.md)
- Project skills live in `.agents/skills/` (`.claude/skills` is a symlink):
  `/newslice N` build one slice · `/triage` failing test, two strikes · `/harden` scope-freeze audit ·
  `/submitpack` submission artefacts · `/demoprep` before recording/judging · `/agentgraph` LangGraph build.
- Global skills: frontend-design, web-design-guidelines, vercel-react-best-practices (UI); webapp-testing (browser checks);
  mcp-builder, skill-creator, find-skills (tooling).
- MCP = context7 (library docs) + playwright (browser). Add others only if docs/TOOLKIT.md enables them
  for this event (`scripts/event-mcp.sh`).
- Prefer CLIs over MCP wrappers: gh, git, supabase, vercel, uv, pytest, npm.

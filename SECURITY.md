# Security

## Reporting
Found a vulnerability? Please open a private security advisory on GitHub (Security → Advisories → Report a vulnerability)
instead of a public issue.

## Measures in place
| Area | Measure | Where |
|---|---|---|
| Secrets | Keys live only in `.env` / `.env.local` (git-ignored) and the host's secret store; `.env.example` lists names only | `.gitignore`, `.env.example`, `render.yaml` (`sync: false`) |
| Secrets in git | gitleaks scan on every push/PR | `.github/workflows/ci.yml` |
| Client exposure | Only `NEXT_PUBLIC_*` values reach the browser; no keys are `NEXT_PUBLIC_*` | `frontend/` |
| Input validation | Pydantic models with length limits; invalid bodies return 422 in the envelope | `backend/app/main.py` |
| CORS | Allowed origins from `CORS_ORIGINS`; localhost default, never `*` | `backend/app/main.py` |
| Rate limiting | Per-IP limits on LLM routes (429 in the envelope) | `backend/app/main.py` |
| Security headers | nosniff, Referrer-Policy, frame-ancestors/X-Frame-Options, Permissions-Policy (API + UI); CSP on UI | `backend/app/main.py`, `frontend/next.config.mjs` |
| LLM safety | All calls via one router; system/user separation; tool allowlist; human approval before irreversible actions | `backend/app/services/llm.py`, `backend/app/agents/graph.py` |
| Privacy | Privacy Mode routes every model call to a local model; no PII in logs/traces | `llm.py`, `trace.py` |
| Dependencies | `pip-audit` and `npm audit --audit-level=high` on every CI run (no automated version-bump PRs) | CI |
| Static analysis | bandit (medium+), ruff, eslint (incl. jsx-a11y) | CI |
| Agent guardrails | Coding agents may not read `.env*`, push to main or edit the API contract | `.claude/hooks/guard.sh`, `AGENTS.md` |

## Threat model (fill per event)
| Threat | Mitigation | Where |
|---|---|---|
| Prompt injection via user input or retrieved content | System/user separation, tool allowlist, schema-validated output, approval interrupt | `llm.py`, `graph.py` |
| API key leakage | Server-side only, git-ignored env files, gitleaks in CI | CI, `.gitignore` |
| Abuse / cost blow-up on LLM routes | Rate limit + TTL cache + input size limits | `main.py`, `llm.py` |
| XSS | React escaping, no `dangerouslySetInnerHTML`, CSP | `frontend/` |
| Unauthorised data access | RLS on `public.runs` (owner-only policies, `anon` has no grants); backend queries with the caller's JWT, never the secret key | `supabase/migrations/*_runs.sql`, pgTAP: `supabase/tests/rls_runs.test.sql`, `backend/app/services/store.py` |
| <threat> | <mitigation> | <where> |

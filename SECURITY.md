# SECURITY.md: threat model for the Tripwire prototype

Tripwire is tamper-evident, not tamper-proof. All data is synthetic and payments are mocked.

| Threat | Where | Mitigation | Residual risk |
|---|---|---|---|
| Hostile text in a ticket hijacks an agent | Support to Refund agent | The gateway is the defence: default-deny policies, spend caps and canaries, no LLM in containment | A hijack below every cap goes unnoticed; the receipt shows the cap values |
| Forged or replayed agent call | `POST /gw/call` | HMAC-SHA256 per-agent secret; reject ts older than 30 s and reused nonces | Shared secrets: use per-agent keypairs in production |
| Edit of a past ledger row | `action_ledger` | Hash chain, UPDATE/DELETE triggers, `/ledger/verify` | A DB owner can disable the triggers and recompute the chain |
| Whole-chain rewrite by a DB admin | `action_ledger` | Head hash is also written to `ANCHOR_LOG_PATH` outside the database; verify compares both | The anchor file is only as safe as its host |
| Hash-chain fork under concurrent writes | Gateway | Postgres advisory lock; app-assigned gapless `idx` | A lock timeout returns an error rather than skipping an entry |
| Rollback of the wrong rows | Rollback engine | Plan first, one-click apply, replay oracle test | Irreversible actions are marked `manual` |
| Service-role key leak | Env, client bundle | Key stays server-side; console uses the anon key with read-only RLS; gitleaks in CI | Rotate after the event |
| Admin endpoints abused | `/demo/*`, `/bench/*`, rollback, quarantine | `X-Admin-Token`; CORS allowlist; rate limit on `/gw/call` | Prototype-grade auth |
| Prompt injection into receipt phrasing | Optional LLM narrative | Receipt numbers come from the DB; the LLM only phrases them | Phrasing can be wrong; numbers cannot |
| XSS from ticket text in the console | Next.js UI | React escaping; no `dangerouslySetInnerHTML`; CSP | Third-party packages |

Reporting: open an issue in the repo.

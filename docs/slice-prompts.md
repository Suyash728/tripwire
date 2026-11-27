# docs/slice-prompts.md: paste one slice at a time into the coding agent

Every prompt starts with the same preamble. Do not skip it.

```
Read AGENTS.md, openapi.yaml, agents/graph.md, db/schema.sql and docs/traceability.md first.
Follow AGENTS.md exactly (model policy, no-LLM containment rule, do-not-touch list).
Work only on this slice. If the contract is wrong or missing something, stop and tell me; do not edit openapi.yaml.
Write tests first for each rule, then the code. Finish with the Definition of Done checklist and tick R-IDs.
```

Deadlines (IST): S1 Wed 25 Nov 23:59. S2 Thu 26 Nov 23:59 (fallback trigger). S3 Sat 28 Nov 23:59 (50% MUST demoable Sun 00:00). S4 Sun 29 Nov 19:00 (scope freeze).

---

## Slice 1: identity and ledger (R1, R2, R10 partial)
**Goal:** a signed call goes through `POST /gw/call`, is executed against the seed DB, and lands in a verified hash chain.

Build:
1. Supabase client + advisory-lock ledger writer (`app/ledger`): gapless `idx`, `hash = sha256(prev_hash + canonical_json(entry))`, genesis 64 zeros, anchor file append after each write.
2. HMAC identity check (`app/gateway`): signature over `agent_id|task_id|tool|canonical(args)|ts|nonce`; reject ts older than 30 s and reused nonces (401).
3. Tool executor for all tools in `agents/graph.md` with before/after images and read/write version stamps.
4. `GET /ledger`, `GET /ledger/verify` (recompute chain + compare with anchor), `GET /agents`, `POST /demo/load` (cases 1-3, scripted), `POST /demo/tamper`.
5. Seed files in `seed/` with ground-truth labels per ledger action (legit or malicious).

Tests: forged, stale and replayed calls return 401; two parallel calls produce no gap or fork; tampering a row makes verify name the first broken idx; anchor mismatch is detected.
Do not: add rules, quarantine or provenance (slice 2 and 3).

## Slice 2: rules, canaries, quarantine (R4, R5, R6, R7)
**Goal:** the Refund agent trips on seed case 1 and case 3; other agents keep working.

Build:
1. Policy engine (`app/policy`): default-deny tool and table allowlists, `R-CALL`, `R-TASK`, `R-HOUR` cumulative caps (values in `agents/graph.md`), `R-CANARY`.
2. Trip handling: first deny by `R-CANARY`, `R-TASK`, `R-HOUR` or `R-CALL` sets status `quarantined`, creates the incident row with `containment_ms`, then later calls return `quarantined_deny` and increment `blocked_calls`.
3. `POST /agents/{id}/quarantine`, `POST /demo/inject` (`injection`, `canary_read`, `salami_split`), `GET /events` SSE with trace events (`decider` is `rule`, `canary` or `human`).
4. `test_containment_no_llm.py` must stay green.

Tests: each rule denies; legit seed traffic never trips; case 3 trips `R-HOUR` and not `R-TASK`; after the trip Refund gets 403 and Support gets 200; no import of `services/llm.py` in containment packages.
Do not: touch rollback.

## Slice 3: provenance, blast radius, rollback, receipt (R3, R8, R9)
**Goal:** selective rollback restores state equal to a legit-only replay.

Build:
1. Read stamps per `task_id`, `provenance_edges` writer, NetworkX closure with `scoped` and `strict` modes (`app/provenance`).
2. `GET /incidents/{id}/blast-radius` including `naive_lost_count`.
3. Compensating-tool registry and `POST /incidents/{id}/rollback` (`plan`, `apply`), rollback steps ledgered as `kind=rollback`, irreversible steps marked `manual`.
4. `GET /incidents/{id}/receipt` with numbers from the DB; optional LLM narrative via `gemini-3.8-flash` (receipt phrasing only, falls back to a template).

Tests: replay oracle on cases 1, 2, 3 (final state equals legit-only replay); closure equals labelled tainted set on case 1; on case 2 `scoped` keeps the Finance summary chain and `strict` over-taints it; receipt counts match DB; double apply returns 409.
Do not: let the receipt LLM change any number.

## Slice 4: bench, faults, side-by-side (R12, R13, R14)
**Goal:** honest measured numbers and a jury-proof drill.

Build:
1. `POST /bench/run` and `make bench`: n runs per case, containment ms (p50, p95, max), preserved %, taint precision and recall, missing ledger entries.
2. Fault drill wired to the "Inject fault" button; each fault ends in a receipt.
3. Side-by-side data: `naive_lost_count` vs Tripwire kept count.
4. SHOULD: offline run on local vLLM (R14), `hold` for irreversible actions (R15) only if time remains.

Tests: bench on 30 runs per case; assert missing entries is 0; print numbers even when below target.
Do not: hard-code results or round up. Report the measured values.

---

## Frontend lane (can run in parallel from the first commit, against `make mock`)
Prompt: "Build the console in `frontend/` against `make mock`. Components: agent cards (`agent-<id>`), live feed with `ledger-row-<idx>`, `stopwatch`, `chain-status`, `blast-graph`, `compare-table`, `receipt`, trace panel from `/events`. Buttons named exactly: Load sample incident, Apply rollback, Inject fault, Tamper with a row. Label SCRIPTED mode visibly. Keyboard usable, contrast OK, `frontend/e2e/demo.spec.ts` passes with no serious axe issues."

# docs/traceability.md

Tick a row only when its test passes and the demo moment works. Commit messages name the R-IDs.

| ID | Requirement (source) | Feature | Test | Demo moment | Rubric line | Done |
|---|---|---|---|---|---|---|
| R1 | Every action carries an agent identity (abstract) | HMAC-signed agent identity, stamped on each call | pytest: unsigned, forged, stale or reused-nonce call returns 401 | 0-10 s | Auditability | [x] |
| R2 | Append-only, hash-chained ledger with before-values (abstract) | `action_ledger`, triggers, `/ledger/verify`, anchor file | pytest: edit a row, verify names the first broken idx; UPDATE/DELETE blocked | 70-80 s | Auditability | [x] |
| R3 | Provenance of earlier data used (abstract) | Read stamps, `provenance_edges`, NetworkX closure | pytest: closure on seed case 1 equals the labelled tainted set | 35-55 s | Technical depth | [ ] |
| R4 | Rule checks: tools, spend limit, tables (abstract) | `R-TOOL`, `R-TABLE`, `R-CALL`, `R-TASK`, `R-HOUR` | pytest: each rule denies; case 3 trips `R-HOUR` | 25-35 s | Survives attack | [x] |
| R5 | "Special records" (abstract) | Canary rows, `R-CANARY` | pytest: canary touch trips; no trips on legit seed traffic | 25-35 s | Survives attack | [x] |
| R6 | Containment never depends on an LLM (abstract) | Rule-only containment path | pytest: `test_containment_no_llm.py` | Trace panel (decider = rule) | Auditability | [x] |
| R7 | Quarantine one agent, others continue (abstract) | Agent status, `quarantined_deny`, `blocked_calls` | pytest: Refund 403, Support 200 after the trip | 25-35 s | Survives attack | [x] |
| R8 | Reverse affected actions in order (abstract) | Rollback plan and apply, compensating tools | pytest: replay oracle (final state equals legit-only replay) | 35-55 s | Technical depth | [ ] |
| R9 | Report of what happened, reversed, prevented (abstract) | Incident receipt | pytest: receipt counts match the DB | 55-70 s | Auditability | [ ] |
| R10 | Four-agent demo network (abstract) | Support, Refund, Inventory, Finance; live and scripted | pytest: seed run yields the labelled action counts | 0-10 s | Prototype | [ ] |
| R11 | Monitoring dashboard (abstract) | Console: feed, agent cards, graph, trace panel | Playwright demo path plus axe | All | Prototype | [ ] |
| R12 | Contain under 2 s, keep at least 75% of legit work, no missing entries (abstract) | `/bench/run` and `make bench` | bench asserts, 30 runs per case | 80-90 s | Impact | [ ] |
| R13 | Unseen-fault drill (implicit: jury attack) | "Inject fault": injection, canary_read, salami_split | pytest: each fault trips | 80-90 s | Survives attack | [ ] |
| R14 | Offline run on a local model (abstract, SHOULD) | Router tier 3 | Wi-Fi-off run, recorded | n/a | Prototype | [ ] |
| R15 | Hold irreversible actions (innovation, SHOULD) | `hold` decision, human release | pytest: held action does not execute | Receipt | Technical depth | [ ] |

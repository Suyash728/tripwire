# docs/quality-kit.md: quality tier F

Applies to every slice. Tick in the PR description.

## Per-slice gate
- [ ] Works on seed data, end to end
- [ ] Tests written (at least one edge case); replay-oracle test for anything touching rollback
- [ ] `make lint && make typecheck && make test` pass
- [ ] Inputs validated; no secret or PII in client bundle or logs
- [ ] Hot path measured: `POST /gw/call` p95 under 150 ms locally (excl. LLM)
- [ ] R-IDs ticked in `docs/traceability.md`

## Test layers
| Layer | Tool | What |
|---|---|---|
| Unit | pytest | rules, hash chain, taint closure, inverse registry |
| Property | pytest | for any call sequence: rollback then state equals legit-only replay |
| API | pytest + TestClient | signed-call auth, rule denials, envelope shape |
| Contract | Redocly lint, Prism | `openapi.yaml` valid; frontend works against `make mock` |
| E2E | Playwright + axe | demo path, no serious or critical a11y violations |
| Bench | `make bench` | containment ms, preserved %, taint precision/recall, missing entries |

## Coverage floor
60% at first, 75% at the hardening pass (29 Nov 19:00 IST). Containment packages should be higher.

## Do not
- Skip a failing test; fix or ask.
- Edit applied migrations; add a new one.
- Report a bench number you did not measure.

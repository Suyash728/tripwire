# Traceability

Every MUST in AGENTS.md has a row here. `/newslice` ticks rows; `/harden` and `/submitpack` read them.
Source: **PS-explicit** (stated in the problem statement) · **PS-implicit** (needed to satisfy it) · **User need** (from research/interviews).
Status: `todo` · `in progress` · `done` (tested + demoable) · `cut` (moved to WON'T).

| Req ID | Requirement | Source | Feature | Test(s) | Demo moment | Status |
|---|---|---|---|---|---|---|
| R1 | <what the user must be able to do> | PS-explicit | <slice / screen> | `backend/tests/test_<x>.py::test_<y>`, `frontend/e2e/<z>.spec.ts` | <mm:ss in demo> | todo |
| R2 | <...> | PS-implicit | <...> | <...> | <...> | todo |
| R3 | <...> | User need | <...> | <...> | <...> | todo |

## Non-functional requirements
| Req ID | Requirement | Evidence | Status |
|---|---|---|---|
| NF1 | Works offline (Privacy Mode: local model only) | `bash scripts/smoke_demo.sh --privacy` | todo |
| NF2 | Accessible (WCAG 2.2 AA target, axe clean) | `frontend/e2e/demo-path.spec.ts` | todo |
| NF3 | Secure by default (headers, CORS, rate limit, validation) | SECURITY.md, `backend/tests/` | todo |
| NF4 | CI green (lint, types, tests, coverage, audits) | `.github/workflows/ci.yml` | todo |

## Worked example (template sample case)
What the template already does, filled in as a reference. Every test cited exists; replace this section with
your event's rows (or keep R-ex rows that you demo). Vitest tests are cited as `file::"it name"`.

| Req ID | Requirement | Source | Feature | Test(s) | Demo moment | Status |
|---|---|---|---|---|---|---|
| R-ex1 | Load a sample case into the input | User need | `GET /samples` + "Load sample case" button (`page.tsx`) | `backend/tests/test_api.py::test_samples_are_seeded`, `frontend/src/app/page.test.tsx::"loads the sample case into the input"`, `frontend/e2e/demo-path.spec.ts` (demo path) | first click of the demo | done |
| R-ex2 | Run the agent, approve, and watch trace events stream live | PS-implicit | `POST /runs` + SSE `GET /runs/{id}/events` + `TracePanel` | `backend/tests/test_api.py::test_graph_interrupt_and_resume`, `backend/tests/test_api.py::test_graph_reject_cancels_action`, `frontend/src/components/TracePanel.test.tsx::"renders one live list item per event with tier and timing"`, `frontend/e2e/demo-path.spec.ts` (only test that exercises the SSE stream end to end) | run + approve | done |
| R-ex3 | Privacy Mode forces the local model tier | User need | `privacy_mode` / `PRIVACY_MODE` in `llm.py` | `backend/tests/test_llm.py::test_privacy_mode_never_calls_cloud`, `backend/tests/test_llm.py::test_privacy_mode_env_accepts_truthy_values`, `backend/tests/test_llm.py::test_tier_order_default_and_privacy`; live: `bash scripts/smoke_demo.sh --privacy` | toggle Privacy Mode, trace shows `local` | done |
| NF-ex | Accessible demo path (WCAG 2.2 AA tags, no serious/critical axe violations) | PS-implicit | labelled landmarks + controls, `aria-live` trace/result | `frontend/e2e/demo-path.spec.ts` (axe at load, after run, after approve), `frontend/src/app/page.test.tsx::"has a labelled main landmark and a labelled case input"`, `frontend/src/components/TracePanel.test.tsx::"shows an empty state inside a labelled complementary landmark"` | whole demo | done |

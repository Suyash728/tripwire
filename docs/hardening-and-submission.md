# docs/hardening-and-submission.md

## E. Hardening pass (start at scope freeze, Sun 29 Nov 19:00 IST; about 6 h)
1. Raise the CI coverage floor from 60 to 75 in `ci.yml`.
2. Run `make bench` with 30 runs per case; paste the real numbers into the README table.
3. Security sweep against `SECURITY.md`: admin token on every admin route, CORS allowlist, rate limit on, no service-role key in the client bundle, gitleaks green.
4. Remove or gate `/demo/tamper` and `demo_tamper_row` behind `ADMIN_TOKEN` and a `DEMO_MODE=1` flag.
5. Cold-start the deployed backend (Render sleeps). Add a warm-up step to the demo script.
6. Wi-Fi-off run on the local model (R14) if built; record it.
7. Fresh-clone test: clone, `.env` from `.env.example`, `make seed CASE=1`, `make dev`, demo path passes in under 10 min.
8. Fill `AI_DISCLOSURE.md` (every TODO) and tick `docs/traceability.md`.
9. Fix the known gaps in the README "Limits" section instead of hiding them (taint over-approximation, tamper-evident not tamper-proof, scripted attack in demo, mocked payments).

## F. Submission pack

### README skeleton
1. One-line pitch and demo link, video link, live URL
2. Problem: agents act, and after an incident teams either kill everything or guess. Cite survey figures with their real sources: Salt Security (49.8%, 41.9%, 12.5%, 76.8%), VB Pulse (14%), Gravitee (6%, 1 in 8), EMA/Cequence (65%). Note that the 12.5% figure belongs to Salt Security, not VB Pulse. The abstract linked it wrongly and is already submitted, so correct it here.
3. How it works: gateway, rules and canaries, ledger, provenance graph, selective rollback, receipt. Diagram.
4. Measured results table (real bench output, n and date)
5. Related work and what is different: Warrant (run-level kill and rollback), agents-firewall, agent_acid (compensating actions, the salami-slicing finding; this is the "ACID-based safeguards" referenced in the abstract), Rubrik Agent Rewind (early access as of 28 Oct 2026; SaaS apps), agent-forensics (memory-level provenance and rollback), TaintCTL (blocks flows, no undo), Revoco (pre-action rollback plans)
6. Limits and honesty: conservative taint, tamper-evident not tamper-proof, irreversible actions are held or marked manual, scripted attack mode labelled, synthetic data and mocked payments
7. Run it: `.env.example`, `make seed`, `make dev`, `make bench`
8. Requirements traceability link, `SECURITY.md`, `AI_DISCLOSURE.md`

### 90-second video script (matches `docs/traceability.md` demo moments)
| Time | Screen | Voice-over (short) |
|---|---|---|
| 0-10 s | Console, four agents green, ledger scrolling | "Four agents run a store. Every action goes through one gateway." |
| 10-25 s | Click Load sample incident; poisoned ticket T-666 appears | "One support ticket carries hidden instructions. The Refund agent starts paying out." |
| 25-35 s | Refund card turns red, stopwatch stops, trace shows decider = rule | "A fixed rule trips. No AI made that call. Refund is isolated; Support keeps working." |
| 35-55 s | Blast graph; click Apply rollback | "The provenance graph shows what the bad actions touched. Only that is reversed." |
| 55-70 s | Receipt and compare table | "Naive: restore everything and lose N legit actions. Tripwire: reversed 11, kept the rest." |
| 70-80 s | Tamper with a row; chain turns red | "Edit history and the chain breaks at the exact row." |
| 80-90 s | Bench numbers; Inject fault: canary_read | "Measured, not claimed. Try a fault of your own." |

Use the real counts from the bench; do not say 75% or 2 s unless measured.

### Judge Q&A (8)
1. **How is this different from Rubrik Agent Rewind or Warrant?** As far as we found, Rubrik targets recovery of SaaS data through its platform (early access as of 28 Oct 2026) and Warrant kills and rolls back at run level. Tripwire sits in the call path of a multi-agent network, quarantines one agent by fixed rules, and reverses only the actions that depend on the bad ones. Check both repos or pages again before submission and soften the wording if either changed.
2. **Why no LLM in containment?** An attacker who can steer an agent can steer a model judge. Rules, canaries and caps are deterministic and testable. The only LLM use is phrasing the receipt text.
3. **What if the attack stays under every cap?** Then Tripwire does not trip. We show cap values in the receipt and ship the salami case as the example where a cumulative rule catches a split attack. A new attack shape needs a new rule.
4. **Is taint tracking accurate?** It is conservative. `scoped` mode is reported with precision and recall on seed case 2; `strict` over-taints. Numbers are in the README.
5. **Can the ledger be tampered with?** Edits are detected, not prevented. The head hash is anchored outside the database; a DB owner who rewrites the whole chain and the anchor is out of scope.
6. **What about irreversible actions?** Support replies cannot be unsent. They are marked `manual` in the rollback plan; the SHOULD feature holds them for human release.
7. **Is the attack real?** The demo has a live-LLM mode and a labelled scripted mode. The default is scripted so the demo is repeatable, and the UI says so.
8. **Does it scale?** The prototype serialises ledger writes with one advisory lock, which is the bottleneck. A production design would shard the chain per tenant. We did not build that and say so.

### Final submission checklist (target Wed 2 Dec 18:00 IST)
- [ ] Live URL works from a fresh browser; backend warmed
- [ ] Repo public (or as required), no secrets in history (gitleaks green)
- [ ] Video under the length limit, captions on
- [ ] README numbers copied from the last `make bench`
- [ ] `AI_DISCLOSURE.md` and abstract disclosure consistent
- [ ] Submitted a day early if the portal allows resubmission; confirm format against the Unstop page

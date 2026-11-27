# docs/team-ops-and-judging.md

## I. Team ops (team Nexus: Gauranshi, Madhu Mitha, Suyash)

### Lanes (flexible; confirm on day 1)
| Lane | Owns | Default |
|---|---|---|
| A: Gateway core | Slices 1-3 backend: ledger, identity, policy, provenance, rollback | TBD |
| B: Agents + integration | Demo agents, seed cases, LLM router, bench (slice 4), CI, merges | Suyash |
| C: Console + story | Frontend lane, Playwright/axe, video, README, submission | TBD |

Rule: one owner per file at a time. Contract files (`openapi.yaml`, `db/schema.sql`, `AGENTS.md`) change only by PR approved by all three.

### Daily rhythm (IST)
- **10:00 stand-up (10 min, voice):** yesterday done, today, blocker. Post the three lines in the group chat if someone can't join.
- **22:00 sync (15 min):** merge to `main`, demo the current state on the deployed URL, update `docs/traceability.md`.
- **Async:** PRs small (under 400 lines), reviewed within 3 h by anyone in another lane.

### Availability (fill now, it decides the plan)
| Person | 25 Nov | 26 Nov | 27 Nov | 28 Nov | 29 Nov | 30 Nov | 1 Dec | 2 Dec |
|---|---|---|---|---|---|---|---|---|
| Gauranshi | | | | | | | | |
| Madhu Mitha | | | | | | | | |
| Suyash | | | | (Code to Cart R2?) | (Code to Cart R2?) | | | |

If Suyash runs Agentware (27-30 Nov) or Code to Cart R2 (28-29 Nov): hand off bench and integration to lane A by 26 Nov 23:59 and keep only the bench run plus video edit.

### Decision rules
- Scope questions: check MUST/WON'T in `AGENTS.md`; if not covered, the leader (Gauranshi) decides within 1 h.
- Blocked over 2 h: say so in the group chat; the 22:00 sync re-plans.
- Fallback to Tripwire-lite if Slice 2 is not done by Thu 26 Nov 23:59. No debate at that point.

### Risk register
| Risk | Trigger | Response |
|---|---|---|
| LLM hijack unreliable | Spike under 8/10 | Scripted mode default, labelled |
| Free-tier limits (Groq, Gemini 3.8 at ~20/day) | 429s | Router falls back; receipt uses template text |
| Render cold start in demo | First call over 10 s | Warm-up hit 2 min before demo |
| Teammate unavailable | Missed 2 syncs | Reassign their open slice at the next sync |
| Overlapping hackathons | Calendar | Hand-off date above |

## J. Judging-day checklist (mentorship 3-7 Dec, finale Wed 9 Dec)

### Day before
- [ ] Rehearse the 90 s demo 3 times; one teammate tries to break it each time
- [ ] Bench numbers in slides and README match the last `make bench`
- [ ] Recorded backup video downloaded locally (no streaming)
- [ ] Re-check Rubrik Agent Rewind and Warrant pages; update Q&A 1 if changed
- [ ] Each person can answer all 8 Q&As; assign primary answerer per question
- [ ] Charge laptops; HDMI/USB-C adapters; phone hotspot as backup internet

### 30 min before
- [ ] Warm backend (`/health`, then `make seed CASE=1` on the deployed DB)
- [ ] Open tabs: console, `/ledger/verify`, README, backup video
- [ ] Close notifications; browser zoom 125%; dark/light checked on the projector
- [ ] Local model running if showing offline mode

### During
- [ ] Lead with the moment: Refund card goes red, Support stays green
- [ ] Say "measured" with n and date when quoting numbers
- [ ] When the jury tries to break it: use "Inject fault" first, then their idea; if it doesn't trip, say which rule would catch it and that the receipt shows the caps (Q&A 3)
- [ ] If something fails live: switch to the backup video within 20 s, don't debug on stage

### After
- [ ] Note every jury question and the answer given
- [ ] Fix anything that broke before the next round

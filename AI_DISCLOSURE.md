# AI_DISCLOSURE.md

Fill in honestly before submission. Replace every TODO.

## Written by the team without AI
- The SEED abstract (hand-written by the team, as the event requires). TODO: confirm.
- TODO: list anything else.

## AI tools used while building
| Tool | Used for | Who |
|---|---|---|
| TODO (for example Claude Code, Antigravity, opencode, Cursor) | Code generation inside the slice prompts, tests, README drafts | TODO |
| Claude (chat) | Planning, rubric analysis, contract files (`AGENTS.md`, `openapi.yaml`, `agents/graph.md`, schema, CI) prepared before the build window | Suyash |

## Starter material
- Template repo `Suyash728/hackathon-starter` (router, health check, CI scaffold, trace panel). Public starter, not a pre-built solution.
- Design and contract files above were prepared before the build window and are in the first commit. No application code existed before the window opened. TODO: confirm.

## AI inside the product
- The four demo agents (Support, Refund, Inventory, Finance) are LLM agents in live mode and scripted in scripted mode. The UI labels the mode.
- Models: see `AGENTS.md` model policy.
- **No AI model takes any containment, quarantine or rollback decision.** Those use fixed rules, canaries and a graph traversal. An optional LLM only phrases the receipt text.

## Data
- All data is synthetic. Payments and the store database are mocked.

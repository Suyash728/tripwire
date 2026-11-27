# Agent graph spec (fill at Gate 3)

Framework: plain function calling | LangGraph | LangGraph + CrewAI node  (decision rule, section 4)

## State
| field | type | written by |
|---|---|---|
| input | str | API |
| privacy_mode | bool | API |
| plan | str | planner |
| evidence | list[str] | tools |
| verdict | str | verifier |
| approved | bool | approval (interrupt) |
| result | str | act |

## Nodes -> edges
START -> planner -> tools -> verifier -> approval (interrupt) -> act -> END

## Tools
- sample_lookup: <replace>

## Interrupt points
- approval: before any irreversible action. Resume via `POST /runs/{id}/resume {approve}`.

## Trace events
Every node emits `{node, status, tier_used, ms}`; the UI trace panel renders them live.

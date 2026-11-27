---
name: agentgraph
description: Build or adapt the LangGraph in backend/app/agents/graph.py from the node/edge spec in agents/graph.md, with a trace event per node
disable-model-invocation: true
---
Enter Plan Mode. Read agents/graph.md, CLAUDE.md and the existing backend/app/agents/graph.py.
Use context7 for langgraph (1.2.x API: StateGraph, langgraph.types.interrupt/Command, InMemorySaver).
- State: exactly the fields in agents/graph.md (TypedDict).
- Nodes: one function per node; every model call via services.llm.chat(privacy_mode=state["privacy_mode"]).
- Every node emits trace.emit(run_id, node, status, tier_used, ms).
- Human approval: interrupt() before any irreversible action; resume via POST /runs/{id}/resume.
- Checkpointer: InMemorySaver (SQLite only if resume across restarts is needed).
Test: `cd backend && uv run pytest -q`, then run the API and `bash scripts/smoke_demo.sh`; paste output.
Then build/adjust frontend/src/components/TracePanel.tsx only if new event fields were added.

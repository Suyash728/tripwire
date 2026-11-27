"""Example LangGraph: planner -> tools -> verifier -> [interrupt: human approval] -> act.

Adapt at Gate 4; keep the shape (trace event per node, interrupt before anything
irreversible). Spec lives in agents/graph.md.
"""

from __future__ import annotations

import json
import time
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from app.services import llm, trace


class State(TypedDict, total=False):
    run_id: str
    input: str
    privacy_mode: bool
    plan: str
    evidence: list[str]
    verdict: str
    approved: bool
    result: str


def _call(state: State, node: str, system: str, user: str) -> str:
    trace.emit(state["run_id"], node, "start")
    t0 = time.perf_counter()
    r = llm.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        privacy_mode=state.get("privacy_mode", False),
    )
    trace.emit(state["run_id"], node, "done", r.tier, int((time.perf_counter() - t0) * 1000))
    return r.text


def planner(state: State) -> State:
    return {"plan": _call(state, "planner", "Write a 3-step plan. Be terse.", state["input"])}


def tools(state: State) -> State:
    # Replace with real tools (DB lookup, search, OCR...). Deterministic for the demo.
    trace.emit(state["run_id"], "tools", "start")
    evidence = [f"sample-evidence for: {state['input'][:60]}"]
    trace.emit(state["run_id"], "tools", "done", None, 0, tool="sample_lookup")
    return {"evidence": evidence}


def verifier(state: State) -> State:
    text = _call(
        state,
        "verifier",
        'Check the plan against the evidence. Reply JSON {"ok": bool, "why": str}.',
        json.dumps({"plan": state.get("plan"), "evidence": state.get("evidence")}),
    )
    return {"verdict": text}


def approval(state: State) -> State:
    # No emit before interrupt(): LangGraph re-runs this node from the top on resume.
    # main._run emits "approval waiting" when the graph pauses.
    decision = interrupt({"question": "Approve this action?", "plan": state.get("plan")})
    trace.emit(state["run_id"], "approval", "approved" if decision else "rejected")
    return {"approved": bool(decision)}


def act(state: State) -> State:
    trace.emit(state["run_id"], "act", "done")
    return {"result": "action executed" if state.get("approved") else "action cancelled"}


def build():
    g = StateGraph(State)
    for name, fn in [
        ("planner", planner),
        ("tools", tools),
        ("verifier", verifier),
        ("approval", approval),
        ("act", act),
    ]:
        g.add_node(name, fn)
    g.add_edge(START, "planner")
    g.add_edge("planner", "tools")
    g.add_edge("tools", "verifier")
    g.add_edge("verifier", "approval")
    g.add_edge("approval", "act")
    g.add_edge("act", END)
    return g.compile(checkpointer=InMemorySaver())


GRAPH = build()


def start(run_id: str, text: str, privacy_mode: bool = False) -> dict:
    cfg = {"configurable": {"thread_id": run_id}}
    return GRAPH.invoke({"run_id": run_id, "input": text, "privacy_mode": privacy_mode}, cfg)


def resume(run_id: str, approve: bool) -> dict:
    cfg = {"configurable": {"thread_id": run_id}}
    return GRAPH.invoke(Command(resume=approve), cfg)

"""API routes for Tripwire: gateway, ledger, agents, quarantine, inject, and SSE events."""

from __future__ import annotations

import asyncio
import hmac
import json
import os
import time
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.gateway.events import get_trace_bus
from app.gateway.executor import ToolExecutionError, execute_tool
from app.gateway.identity import IdentityError, verify_call_identity
from app.ledger.chain import verify_chain
from app.ledger.repository import get_store
from app.seed import load_case

router = APIRouter()


def envelope(
    data: Any = None,
    *,
    error: dict[str, str] | None = None,
    success: bool = True,
) -> dict[str, Any]:
    """Build standard {success, data, error} response envelope."""
    return {"success": success, "data": data, "error": error}


def _require_admin(x_admin_token: str | None) -> None:
    expected = os.environ.get("ADMIN_TOKEN", "")
    if not expected:
        return
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=401, detail="invalid or missing X-Admin-Token")


class CallRequest(BaseModel):
    agent_id: Literal["support", "refund", "inventory", "finance"]
    task_id: str = Field(min_length=1, max_length=128)
    tool: str = Field(min_length=1, max_length=64)
    args: dict[str, Any] = Field(default_factory=dict)
    ts: str = Field(min_length=1, max_length=64)
    nonce: str = Field(min_length=1, max_length=128)
    signature: str = Field(min_length=1, max_length=128)


class DemoLoadRequest(BaseModel):
    case: Literal[1, 2, 3]
    mode: Literal["live", "scripted"] = "scripted"


class TamperRequest(BaseModel):
    ledger_idx: int = Field(ge=1)


class InjectRequest(BaseModel):
    fault: Literal["injection", "canary_read", "salami_split"]


def _execute_gateway_step(
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    args: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """Run policy + executor + ledger append + trace publish for a verified call."""
    start = time.perf_counter()
    store = get_store()
    outcome = store.execute_and_append(
        agent_id=agent_id,
        task_id=task_id,
        tool=tool,
        args=args,
        executor_fn=execute_tool,
    )
    ms = round((time.perf_counter() - start) * 1000.0, 3)
    entry = outcome["entry"]
    policy = outcome["policy"]

    get_trace_bus().publish(
        {
            "ts": entry["ts"],
            "agent": agent_id,
            "tool": tool,
            "decision": policy.decision,
            "decider": policy.decider,
            "rule_id": policy.rule_id,
            "ms": ms,
            "ledger_idx": entry["idx"],
            "hash": entry["hash"],
        }
    )

    if policy.decision == "allow":
        return 200, envelope(
            {
                "decision": "allow",
                "ledger_idx": entry["idx"],
                "rule_id": None,
                "result": outcome["result"],
                "ms": ms,
            }
        )

    return 403, envelope(
        {
            "decision": policy.decision,
            "ledger_idx": entry["idx"],
            "rule_id": policy.rule_id,
            "result": None,
            "ms": ms,
        },
        success=False,
        error={"code": policy.decision, "message": policy.reason},
    )


@router.post("/gw/call")
async def gateway_call(req: CallRequest) -> JSONResponse:
    """Verify agent HMAC identity, evaluate policy, execute tool, and append to ledger."""
    try:
        verify_call_identity(
            agent_id=req.agent_id,
            task_id=req.task_id,
            tool=req.tool,
            args=req.args,
            ts=req.ts,
            nonce=req.nonce,
            signature=req.signature,
        )
    except IdentityError as exc:
        return JSONResponse(
            status_code=401,
            content=envelope(
                None,
                success=False,
                error={"code": "unauthorized", "message": str(exc)},
            ),
        )

    try:
        status_code, body = _execute_gateway_step(
            agent_id=req.agent_id,
            task_id=req.task_id,
            tool=req.tool,
            args=req.args,
        )
    except ToolExecutionError as exc:
        return JSONResponse(
            status_code=422,
            content=envelope(
                None,
                success=False,
                error={"code": "invalid_tool_call", "message": str(exc)},
            ),
        )

    return JSONResponse(status_code=status_code, content=body)


@router.get("/ledger")
async def list_ledger(
    after: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    """Return ledger entries after an index."""
    entries = get_store().list_ledger(after=after, limit=limit)
    return envelope({"entries": entries})


@router.get("/ledger/verify")
async def verify_ledger() -> dict[str, Any]:
    """Recompute the hash chain and compare head hash with anchor file."""
    entries = get_store().all_ledger()
    return envelope(verify_chain(entries))


@router.get("/agents")
async def list_agents() -> dict[str, Any]:
    """Return all agents and their status."""
    return envelope({"agents": get_store().list_agents()})


@router.post("/agents/{agent_id}/quarantine")
async def quarantine_agent(
    agent_id: str,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> JSONResponse:
    """Manual isolate button: quarantine an agent and emit a human trace event."""
    _require_admin(x_admin_token)
    agent = get_store().quarantine_agent(agent_id)
    if not agent:
        return JSONResponse(
            status_code=404,
            content=envelope(
                None,
                success=False,
                error={"code": "not_found", "message": f"agent {agent_id} not found"},
            ),
        )
    get_trace_bus().publish(
        {
            "ts": datetime.now(UTC).isoformat(),
            "agent": agent_id,
            "tool": "manual.quarantine",
            "decision": "quarantine",
            "decider": "human",
            "rule_id": None,
            "ms": 0.0,
            "ledger_idx": len(get_store().all_ledger()),
            "hash": "",
        }
    )
    return JSONResponse(status_code=200, content=envelope(agent))


@router.post("/demo/load")
async def demo_load(
    req: DemoLoadRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Reset the database to a seed case (1-3)."""
    _require_admin(x_admin_token)
    res = load_case(req.case, mode=req.mode)
    return envelope(res)


@router.post("/demo/inject")
async def demo_inject(
    req: InjectRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Inject a fault (injection, canary_read, salami_split) through the gateway."""
    _require_admin(x_admin_token)
    store = get_store()
    if not store.agents:
        load_case(1, mode="scripted")

    started_at = store.mark_first_malicious().isoformat()

    if req.fault == "canary_read":
        _execute_gateway_step(
            agent_id="support",
            task_id="fault-canary",
            tool="order.read",
            args={"id": "CANARY-0001"},
        )
    elif req.fault == "injection":
        for i in range(1, 6):
            code, _ = _execute_gateway_step(
                agent_id="refund",
                task_id="T-666-inject",
                tool="refund.issue",
                args={"id": f"R-INJ-{i}", "order_id": f"ORD-{100 + i}", "amount_inr": 2000},
            )
            if code == 403:
                break
    elif req.fault == "salami_split":
        for i in range(1, 9):
            task_num = (i + 1) // 2
            code, _ = _execute_gateway_step(
                agent_id="refund",
                task_id=f"salami-inj-{task_num}",
                tool="refund.issue",
                args={"id": f"R-SAL-{i}", "order_id": f"ORD-{100 + i}", "amount_inr": 3500},
            )
            if code == 403:
                break

    return envelope({"fault": req.fault, "started_at": started_at})


@router.post("/demo/tamper")
async def demo_tamper(
    req: TamperRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> JSONResponse:
    """Demo only: mutate a ledger row so /ledger/verify turns red."""
    _require_admin(x_admin_token)
    ok = get_store().tamper_row(req.ledger_idx)
    if not ok:
        return JSONResponse(
            status_code=404,
            content=envelope(
                None,
                success=False,
                error={"code": "not_found", "message": f"ledger_idx {req.ledger_idx} not found"},
            ),
        )
    return JSONResponse(status_code=200, content=envelope(None))


@router.get("/events")
async def stream_events(once: int = Query(default=0, ge=0, le=1)) -> StreamingResponse:
    """SSE stream of TraceEvent objects (not wrapped in the API envelope)."""
    bus = get_trace_bus()

    async def event_gen():
        for ev in bus.history():
            yield f"data: {json.dumps(ev)}\n\n"
        if once:
            return
        q = bus.subscribe()
        try:
            while True:
                try:
                    ev = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"data: {json.dumps(ev)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            bus.unsubscribe(q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

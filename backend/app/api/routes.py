"""Slice 1 API routes: gateway call, ledger, verify, agents, and demo load/tamper."""

from __future__ import annotations

import hmac
import os
import time
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.gateway.executor import ToolExecutionError, execute_tool
from app.gateway.identity import IdentityError, verify_call_identity
from app.ledger.chain import verify_chain
from app.ledger.repository import get_store
from app.seed import load_case

router = APIRouter()


def envelope(
    data: Any = None, *, error: dict[str, str] | None = None, success: bool = True
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


@router.post("/gw/call")
async def gateway_call(req: CallRequest) -> JSONResponse:
    """Verify agent HMAC identity, execute tool, and append to hash-chained ledger."""
    start = time.perf_counter()
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

    store = get_store()
    try:
        outcome = store.execute_and_append(
            agent_id=req.agent_id,
            task_id=req.task_id,
            tool=req.tool,
            args=req.args,
            executor_fn=execute_tool,
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

    ms = round((time.perf_counter() - start) * 1000.0, 3)
    return JSONResponse(
        status_code=200,
        content=envelope(
            {
                "decision": "allow",
                "ledger_idx": outcome["entry"]["idx"],
                "rule_id": None,
                "result": outcome["result"],
                "ms": ms,
            }
        ),
    )


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


@router.post("/demo/load")
async def demo_load(
    req: DemoLoadRequest,
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> dict[str, Any]:
    """Reset the database to a seed case (1-3)."""
    _require_admin(x_admin_token)
    res = load_case(req.case, mode=req.mode)
    return envelope(res)


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

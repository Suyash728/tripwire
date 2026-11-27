"""FastAPI app. Every response, including errors, uses the envelope {success, data, error}."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv

# .env.local (repo root) wins over .env; neither overrides variables already set in the shell.
load_dotenv(Path(__file__).resolve().parents[2] / ".env.local")
load_dotenv()

from fastapi import BackgroundTasks, FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from slowapi import Limiter  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from slowapi.util import get_remote_address  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

from app.agents import graph  # noqa: E402  (imported after load_dotenv)
from app.seed import SAMPLES  # noqa: E402
from app.services import store as store_mod  # noqa: E402
from app.services import trace  # noqa: E402
from app.services.store import RunStore  # noqa: E402

MAX_INPUT_CHARS = int(os.environ.get("MAX_INPUT_CHARS", "4000"))


def _rate_limit() -> str:
    """Per-IP limit on LLM routes, read per request so tests/events can tune it."""
    return os.environ.get("RATE_LIMIT", "20/minute")


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip() and o.strip() != "*"]


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="hackathon-starter")
app.state.limiter = limiter
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],  # authorization: Supabase user JWT
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "frame-ancestors 'none'",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response


def ok(data=None) -> dict:
    return {"success": True, "data": data, "error": None}


def fail(msg: str) -> dict:
    return {"success": False, "data": None, "error": msg}


@app.exception_handler(RequestValidationError)
async def on_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    first = exc.errors()[0] if exc.errors() else {}
    where = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
    msg = f"invalid request: {where}: {first.get('msg', 'validation error')}".strip()
    return JSONResponse(status_code=422, content=fail(msg))


@app.exception_handler(RateLimitExceeded)
async def on_rate_limit(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(status_code=429, content=fail(f"rate limit exceeded: {exc.detail}"))


@app.exception_handler(StarletteHTTPException)
async def on_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=fail(str(exc.detail)))


class RunIn(BaseModel):
    input: str = Field(min_length=1, max_length=MAX_INPUT_CHARS)
    privacy_mode: bool = False


class ResumeIn(BaseModel):
    approve: bool


_results: dict[str, dict] = {}
# Store chosen when each run was created: memory, or the caller's Supabase (JWT-scoped).
_stores: dict[str, RunStore] = {}


def _persist(run_id: str, op: Callable[[RunStore], None]) -> None:
    """Apply op to the run's store; on a Supabase error, use memory for the rest of the run."""
    store = _stores.get(run_id, store_mod.MEMORY)
    try:
        op(store)
    except Exception as exc:
        if store is store_mod.MEMORY:
            raise
        # Error type only: client messages can echo request details; tokens must never reach logs.
        trace.emit(run_id, "store", "memory (supabase unavailable)", error=type(exc).__name__)
        _stores[run_id] = store_mod.MEMORY
        op(store_mod.MEMORY)


def _public_state(out: dict) -> dict:
    return {k: v for k, v in out.items() if k != "__interrupt__"}


@app.get("/health")
def health():
    return ok({"status": "up"})


@app.get("/samples")
def samples():
    return ok(SAMPLES)


def _run(run_id: str, fn, *args) -> None:
    try:
        out = fn(*args)
        _results[run_id] = out
        if "__interrupt__" in out:
            trace.emit(run_id, "approval", "waiting")
            trace.emit(run_id, "graph", "interrupted")
            status = "interrupted"
        else:
            trace.emit(run_id, "graph", "finished", result=out.get("result"))
            trace.close(run_id)
            status = "finished"
        _persist(run_id, lambda s: s.update(run_id, status=status, output=_public_state(out)))
    except Exception as exc:  # surface any graph failure in the trace panel
        trace.emit(run_id, "graph", "error", error=str(exc)[:300])
        trace.close(run_id)
        _persist(run_id, lambda s: s.update(run_id, status="error"))


@app.post("/runs")
@limiter.limit(_rate_limit)
def create_run(request: Request, body: RunIn, bg: BackgroundTasks):
    run_id = str(uuid.uuid4())  # also the primary key of public.runs when Supabase is in use
    trace.open_run(run_id)
    try:
        _stores[run_id] = store_mod.select_store(request.headers.get("authorization"))
    except Exception as exc:  # e.g. invalid SUPABASE_URL: keep serving from memory
        trace.emit(run_id, "store", "memory (supabase unavailable)", error=type(exc).__name__)
        _stores[run_id] = store_mod.MEMORY
    _persist(run_id, lambda s: s.create(run_id, body.input))
    bg.add_task(_run, run_id, graph.start, run_id, body.input, body.privacy_mode)
    return ok({"run_id": run_id})


@app.post("/runs/{run_id}/resume")
@limiter.limit(_rate_limit)
def resume_run(request: Request, run_id: str, body: ResumeIn, bg: BackgroundTasks):
    if run_id not in _results:
        return fail("unknown or still-running run")
    bg.add_task(_run, run_id, graph.resume, run_id, body.approve)
    return ok({"run_id": run_id})


@app.get("/runs/{run_id}")
def get_run(request: Request, run_id: str):
    out = _results.get(run_id)
    if out is None:
        # Not in this process (e.g. restarted): a signed-in caller can read their persisted run.
        try:
            store = store_mod.select_store(request.headers.get("authorization"))
            row = store.get(run_id) if store is not store_mod.MEMORY else None
        except Exception:
            row = None
        out = (row or {}).get("output") or {}
    return ok({"events": trace.events(run_id), "state": _public_state(out)})


@app.get("/runs/{run_id}/events")
async def run_events(run_id: str):
    async def stream():
        while True:
            ev = await asyncio.to_thread(trace.next_event, run_id)
            if ev is None:
                yield ": keepalive\n\n"
            elif trace.is_done(ev):
                yield "event: end\ndata: {}\n\n"
                return
            else:
                yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

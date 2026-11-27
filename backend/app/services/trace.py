"""Per-run trace bus feeding the UI 'Agent trace' panel over SSE."""

from __future__ import annotations

import queue
import threading
import time

_DONE = object()
_lock = threading.Lock()
_runs: dict[str, dict] = {}


def open_run(run_id: str) -> None:
    with _lock:
        _runs[run_id] = {"q": queue.Queue(), "events": []}


def emit(
    run_id: str, node: str, status: str, tier_used: str | None = None, ms: int = 0, **extra
) -> None:
    ev = {
        "node": node,
        "status": status,
        "tier_used": tier_used,
        "ms": ms,
        "ts": time.time(),
        **extra,
    }
    run = _runs.get(run_id)
    if run is not None:
        run["events"].append(ev)
        run["q"].put(ev)


def close(run_id: str) -> None:
    run = _runs.get(run_id)
    if run is not None:
        run["q"].put(_DONE)


def events(run_id: str) -> list[dict]:
    return list(_runs.get(run_id, {}).get("events", []))


def next_event(run_id: str, timeout: float = 15.0):
    """Blocking get; returns None on timeout (send keepalive), _DONE sentinel at end."""
    try:
        return _runs[run_id]["q"].get(timeout=timeout)
    except queue.Empty:
        return None


def is_done(ev) -> bool:
    return ev is _DONE

"""In-memory SSE trace event bus for GET /events."""

from __future__ import annotations

import asyncio
import copy
import threading
from typing import Any

VALID_DECIDERS = frozenset({"rule", "canary", "human"})


class TraceBus:
    """Stores trace events and fans them out to SSE subscribers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()

    def clear(self) -> None:
        with self._lock:
            self._events.clear()

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        if event.get("decider") not in VALID_DECIDERS:
            raise ValueError(f"invalid trace decider: {event.get('decider')}")
        ev = copy.deepcopy(event)
        with self._lock:
            self._events.append(ev)
            subs = list(self._subscribers)
        for q in subs:
            q.put_nowait(ev)
        return ev

    def history(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._events)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._lock:
            self._subscribers.discard(q)


_BUS = TraceBus()


def get_trace_bus() -> TraceBus:
    return _BUS

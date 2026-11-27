"""HMAC-SHA256 agent identity verification with replay and staleness checks."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import UTC, datetime
from typing import Any

MAX_AGE_SECONDS = 30.0
VALID_AGENTS = frozenset({"support", "refund", "inventory", "finance"})

_nonce_lock = threading.Lock()
_used_nonces: set[tuple[str, str]] = set()


class IdentityError(Exception):
    """Raised when signature, timestamp, or nonce verification fails."""


def canonical_json(obj: Any) -> str:
    """Return deterministic compact JSON for signing and hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def reset_nonces() -> None:
    """Clear the in-memory nonce replay cache (called on demo/seed reset)."""
    with _nonce_lock:
        _used_nonces.clear()


def _parse_ts(ts: str) -> float:
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IdentityError("invalid timestamp format") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def verify_call_identity(
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    args: dict[str, Any],
    ts: str,
    nonce: str,
    signature: str,
) -> None:
    """Verify agent HMAC-SHA256 signature, freshness (<=30s), and nonce uniqueness."""
    if agent_id not in VALID_AGENTS:
        raise IdentityError(f"unknown agent_id: {agent_id}")

    secret = os.environ.get(f"AGENT_SECRET_{agent_id.upper()}", "")
    if not secret:
        raise IdentityError(f"missing secret for agent: {agent_id}")

    ts_epoch = _parse_ts(ts)
    now_epoch = time.time()
    if abs(now_epoch - ts_epoch) > MAX_AGE_SECONDS:
        raise IdentityError("stale or future timestamp (>30s)")

    msg = f"{agent_id}|{task_id}|{tool}|{canonical_json(args)}|{ts}|{nonce}".encode()
    expected = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise IdentityError("invalid signature")

    with _nonce_lock:
        key = (agent_id, nonce)
        if key in _used_nonces:
            raise IdentityError("reused nonce")
        _used_nonces.add(key)

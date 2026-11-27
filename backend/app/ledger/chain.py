"""Hash chain computation, external anchor log, and full chain verification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    """Return deterministic compact JSON for ledger hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def compute_entry_hash(prev_hash: str, entry: dict[str, Any]) -> str:
    """Compute SHA-256 over prev_hash + canonical JSON of the ledger entry payload."""
    payload = {
        "idx": entry["idx"],
        "ts": entry["ts"],
        "agent_id": entry["agent_id"],
        "task_id": entry["task_id"],
        "tool": entry["tool"],
        "kind": entry["kind"],
        "decision": entry["decision"],
        "rule_id": entry.get("rule_id"),
        "args": entry["args"],
        "before_image": entry.get("before_image"),
        "after_image": entry.get("after_image"),
        "reads": entry.get("reads", []),
        "writes": entry.get("writes", []),
        "rollback_of": entry.get("rollback_of"),
    }
    raw = (prev_hash + canonical_json(payload)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def anchor_path() -> Path:
    """Return configured anchor file path outside the DB."""
    return Path(os.environ.get("ANCHOR_LOG_PATH", "./anchor.log"))


def clear_anchor() -> None:
    """Reset the external anchor file."""
    path = anchor_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")


def append_anchor(idx: int, entry_hash: str) -> None:
    """Append the latest head hash to the external anchor file."""
    path = anchor_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{idx} {entry_hash}\n")


def read_anchor_head() -> str | None:
    """Return the last recorded head hash from ANCHOR_LOG_PATH, or None if empty."""
    path = anchor_path()
    if not path.exists():
        return None
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if not lines:
        return None
    parts = lines[-1].split()
    return parts[-1] if parts else None


def verify_chain(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Recompute the hash chain from idx=1 and compare head hash with anchor file."""
    if not entries:
        anchor_head = read_anchor_head()
        anchor_ok = anchor_head in (None, GENESIS_HASH)
        return {
            "ok": anchor_ok,
            "first_broken_idx": None,
            "head_hash": GENESIS_HASH,
            "anchor_matches": anchor_ok,
        }

    prev = GENESIS_HASH
    first_broken: int | None = None
    expected_idx = 1

    for entry in entries:
        idx = entry["idx"]
        if idx != expected_idx or entry["prev_hash"] != prev:
            first_broken = idx
            break
        expected_hash = compute_entry_hash(prev, entry)
        if entry["hash"] != expected_hash:
            first_broken = idx
            break
        prev = entry["hash"]
        expected_idx += 1

    head_hash = entries[-1]["hash"] if first_broken is None else prev
    anchor_head = read_anchor_head()
    anchor_matches = anchor_head == head_hash
    ok = first_broken is None and anchor_matches

    return {
        "ok": ok,
        "first_broken_idx": first_broken,
        "head_hash": head_hash,
        "anchor_matches": anchor_matches,
    }

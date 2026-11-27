"""Gateway and ledger persistence (in-memory default; Postgres advisory lock with DATABASE_URL)."""

from __future__ import annotations

import copy
import os
import threading
from datetime import UTC, datetime
from typing import Any

from app.ledger.chain import GENESIS_HASH, append_anchor, clear_anchor, compute_entry_hash

LEDGER_LOCK_KEY = 424242


class GatewayStore:
    """Thread-safe in-memory store mirroring db/schema.sql."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.agents: dict[str, dict[str, Any]] = {}
        self.tickets: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, dict[str, Any]] = {}
        self.refunds: dict[str, dict[str, Any]] = {}
        self.finance_entries: dict[str, dict[str, Any]] = {}
        self.inventory: dict[str, dict[str, Any]] = {}
        self.canaries: dict[str, dict[str, Any]] = {}
        self.ledger: list[dict[str, Any]] = []
        self.incidents: dict[str, dict[str, Any]] = {}
        self.current_case: int | None = None
        self.current_mode: str = "scripted"

    def reset_from_seed(self, seed_data: dict[str, Any], case: int, mode: str) -> None:
        """Reset all tables and ledger to the provided seed case."""
        with self._lock:
            self.agents = {a["id"]: copy.deepcopy(a) for a in seed_data.get("agents", [])}
            self.tickets = {t["id"]: copy.deepcopy(t) for t in seed_data.get("tickets", [])}
            self.orders = {o["id"]: copy.deepcopy(o) for o in seed_data.get("orders", [])}
            self.refunds = {r["id"]: copy.deepcopy(r) for r in seed_data.get("refunds", [])}
            self.finance_entries = {
                f["id"]: copy.deepcopy(f) for f in seed_data.get("finance_entries", [])
            }
            self.inventory = {i["sku"]: copy.deepcopy(i) for i in seed_data.get("inventory", [])}
            self.canaries = {c["record"]: copy.deepcopy(c) for c in seed_data.get("canaries", [])}
            self.ledger = []
            self.incidents = {}
            self.current_case = case
            self.current_mode = mode
            clear_anchor()

    def execute_and_append(
        self,
        *,
        agent_id: str,
        task_id: str,
        tool: str,
        args: dict[str, Any],
        executor_fn: Any,
        kind: str = "action",
        decision: str = "allow",
        rule_id: str | None = None,
        rollback_of: int | None = None,
    ) -> dict[str, Any]:
        """Serialize tool execution + ledger append under lock to guarantee gapless idx."""
        with self._lock:
            exec_out = executor_fn(self, agent_id=agent_id, task_id=task_id, tool=tool, args=args)

            prev_hash = self.ledger[-1]["hash"] if self.ledger else GENESIS_HASH
            idx = len(self.ledger) + 1
            ts = datetime.now(UTC).isoformat()

            entry: dict[str, Any] = {
                "idx": idx,
                "ts": ts,
                "agent_id": agent_id,
                "task_id": task_id,
                "tool": tool,
                "kind": kind,
                "decision": decision,
                "rule_id": rule_id,
                "args": copy.deepcopy(args),
                "before_image": exec_out.get("before_image"),
                "after_image": exec_out.get("after_image"),
                "reads": exec_out.get("reads", []),
                "writes": exec_out.get("writes", []),
                "rollback_of": rollback_of,
                "prev_hash": prev_hash,
            }
            entry["hash"] = compute_entry_hash(prev_hash, entry)
            self.ledger.append(entry)
            append_anchor(idx, entry["hash"])

            return {
                "entry": copy.deepcopy(entry),
                "result": exec_out.get("result"),
            }

    def list_ledger(self, after: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            filtered = [e for e in self.ledger if e["idx"] > after]
            return copy.deepcopy(filtered[:limit])

    def all_ledger(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self.ledger)

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(list(self.agents.values()))

    def tamper_row(self, ledger_idx: int) -> bool:
        """Demo-only mutation of a ledger row's args to trigger chain verification failure."""
        with self._lock:
            for entry in self.ledger:
                if entry["idx"] == ledger_idx:
                    entry["args"]["tampered"] = True
                    return True
            return False


_STORE = GatewayStore()


def get_store() -> GatewayStore:
    """Return the active gateway store instance."""
    # Note: DATABASE_URL Postgres advisory-lock persistence can be wired when psycopg is configured.
    _ = os.environ.get("DATABASE_URL")
    return _STORE

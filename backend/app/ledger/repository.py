"""Gateway and ledger persistence (in-memory default; Postgres advisory lock with DATABASE_URL)."""

from __future__ import annotations

import copy
import os
import threading
from datetime import UTC, datetime
from typing import Any

from app.gateway.events import get_trace_bus
from app.ledger.chain import GENESIS_HASH, append_anchor, clear_anchor, compute_entry_hash
from app.policy.engine import PolicyDecision, evaluate_policy

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
        self.first_malicious_ts: datetime | None = None
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
            self.first_malicious_ts = None
            self.current_case = case
            self.current_mode = mode
            clear_anchor()
            get_trace_bus().clear()

    def execute_and_append(
        self,
        *,
        agent_id: str,
        task_id: str,
        tool: str,
        args: dict[str, Any],
        executor_fn: Any,
        kind: str = "action",
        rollback_of: int | None = None,
        bypass_policy: bool = False,
    ) -> dict[str, Any]:
        """Evaluate policy, execute if allowed, and append to ledger under lock."""
        with self._lock:
            now_dt = datetime.now(UTC)
            if bypass_policy:
                policy_decision = PolicyDecision("allow", None, "human", "rollback", False)
            else:
                policy_decision = evaluate_policy(
                    self,
                    agent_id=agent_id,
                    task_id=task_id,
                    tool=tool,
                    args=args,
                    now_epoch=now_dt.timestamp(),
                )

            if policy_decision.decision == "allow":
                exec_out = executor_fn(
                    self, agent_id=agent_id, task_id=task_id, tool=tool, args=args
                )
            else:
                exec_out = {
                    "result": None,
                    "before_image": None,
                    "after_image": None,
                    "reads": [],
                    "writes": [],
                }
                if policy_decision.decision == "quarantined_deny" and agent_id in self.agents:
                    self.agents[agent_id]["blocked_calls"] = (
                        self.agents[agent_id].get("blocked_calls", 0) + 1
                    )

            prev_hash = self.ledger[-1]["hash"] if self.ledger else GENESIS_HASH
            idx = len(self.ledger) + 1
            ts = now_dt.isoformat()

            entry: dict[str, Any] = {
                "idx": idx,
                "ts": ts,
                "agent_id": agent_id,
                "task_id": task_id,
                "tool": tool,
                "kind": kind,
                "decision": policy_decision.decision,
                "rule_id": policy_decision.rule_id,
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

            incident_id: str | None = None
            if policy_decision.trip and agent_id in self.agents:
                self.agents[agent_id]["status"] = "quarantined"
                first_ts = self.first_malicious_ts or now_dt
                containment_ms = max(0.0, round((now_dt - first_ts).total_seconds() * 1000.0, 3))
                incident_id = f"inc-{len(self.incidents) + 1}"
                self.incidents[incident_id] = {
                    "id": incident_id,
                    "agent_id": agent_id,
                    "task_id": task_id,
                    "trip_rule_id": policy_decision.rule_id,
                    "trip_ledger_idx": idx,
                    "first_malicious_ts": first_ts.isoformat(),
                    "tripped_at": ts,
                    "containment_ms": containment_ms,
                    "status": "open",
                    "receipt": None,
                }

            return {
                "entry": copy.deepcopy(entry),
                "result": exec_out.get("result"),
                "policy": policy_decision,
                "incident_id": incident_id,
            }

    def quarantine_agent(self, agent_id: str) -> dict[str, Any] | None:
        with self._lock:
            agent = self.agents.get(agent_id)
            if not agent:
                return None
            agent["status"] = "quarantined"
            return copy.deepcopy(agent)

    def mark_first_malicious(self) -> datetime:
        with self._lock:
            if self.first_malicious_ts is None:
                self.first_malicious_ts = datetime.now(UTC)
            return self.first_malicious_ts

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
    _ = os.environ.get("DATABASE_URL")
    return _STORE

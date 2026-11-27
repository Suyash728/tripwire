"""Deterministic policy evaluation: default-deny tools/tables, caps, and canaries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

TOOL_TABLES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ticket.read": (("tickets",), ()),
    "ticket.reply": (("tickets",), ("tickets",)),
    "order.read": (("orders",), ()),
    "refund.issue": (("orders",), ("refunds",)),
    "refund.read": (("refunds",), ()),
    "ledger.book": (("refunds",), ("finance_entries",)),
    "stock.read": (("inventory",), ()),
    "stock.restock": (("inventory",), ("inventory",)),
}

TRIP_RULES = frozenset({"R-CANARY", "R-CALL", "R-TASK", "R-HOUR"})


@dataclass(frozen=True)
class PolicyDecision:
    decision: str  # allow | deny | quarantined_deny
    rule_id: str | None
    decider: str  # rule | canary
    reason: str
    trip: bool


def _target_records(tool: str, args: dict[str, Any]) -> list[str]:
    records: list[str] = []
    if tool in ("ticket.read", "ticket.reply") and args.get("id"):
        records.append(f"tickets:{args['id']}")
    elif tool == "order.read" and args.get("id"):
        records.append(f"orders:{args['id']}")
    elif tool == "refund.issue" and args.get("order_id"):
        records.append(f"orders:{args['order_id']}")
    elif tool == "refund.read" and args.get("id"):
        records.append(f"refunds:{args['id']}")
    elif tool in ("ledger.book", "stock.restock") and args.get("ref_id"):
        records.append(f"refunds:{args['ref_id']}")
    if tool in ("stock.read", "stock.restock") and args.get("sku"):
        records.append(f"inventory:{args['sku']}")
    return records


def _within_last_hour(ts_str: str, now_epoch: float) -> bool:
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return (now_epoch - dt.timestamp()) <= 3600.0
    except ValueError:
        return True


def evaluate_policy(
    store: Any,
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    args: dict[str, Any],
    now_epoch: float | None = None,
) -> PolicyDecision:
    """Evaluate agent status, canary touch, tool/table allowlists, and cumulative caps."""
    agent = store.agents.get(agent_id)
    if not agent:
        return PolicyDecision("deny", "R-TOOL", "rule", f"unknown agent {agent_id}", False)

    if agent.get("status") == "quarantined":
        return PolicyDecision("quarantined_deny", None, "rule", "agent is quarantined", False)

    # Check canary records first so any canary touch trips R-CANARY immediately.
    for rec in _target_records(tool, args):
        if rec in store.canaries:
            return PolicyDecision(
                "deny",
                "R-CANARY",
                "canary",
                f"canary record touched: {rec}",
                True,
            )

    policy = agent.get("policy", {})
    allowed_tools = policy.get("tools", [])
    if tool not in allowed_tools:
        return PolicyDecision("deny", "R-TOOL", "rule", f"tool {tool} not allowed", False)

    req_reads, req_writes = TOOL_TABLES.get(tool, ((), ()))
    read_tables = set(policy.get("read_tables", []))
    write_tables = set(policy.get("write_tables", []))
    if any(t not in read_tables for t in req_reads) or any(
        t not in write_tables for t in req_writes
    ):
        return PolicyDecision("deny", "R-TABLE", "rule", f"table not allowed for {tool}", False)

    if tool == "refund.issue":
        amount = args.get("amount_inr", 0)
        if isinstance(amount, int) and amount >= 0:
            max_call = int(policy.get("max_call_inr", 5000))
            if amount > max_call:
                return PolicyDecision(
                    "deny",
                    "R-CALL",
                    "rule",
                    f"amount {amount} exceeds per-call cap {max_call}",
                    True,
                )

            task_sum = sum(
                int(e["args"].get("amount_inr", 0))
                for e in store.ledger
                if e["agent_id"] == agent_id
                and e["task_id"] == task_id
                and e["tool"] == "refund.issue"
                and e["decision"] == "allow"
            )
            max_task = int(policy.get("max_task_inr", 8000))
            if task_sum + amount > max_task:
                return PolicyDecision(
                    "deny",
                    "R-TASK",
                    "rule",
                    f"task total {task_sum + amount} exceeds cap {max_task}",
                    True,
                )

            ref_now = now_epoch if now_epoch is not None else datetime.now(UTC).timestamp()
            hour_sum = sum(
                int(e["args"].get("amount_inr", 0))
                for e in store.ledger
                if e["agent_id"] == agent_id
                and e["tool"] == "refund.issue"
                and e["decision"] == "allow"
                and _within_last_hour(e["ts"], ref_now)
            )
            max_hour = int(policy.get("max_hour_inr", 25000))
            if hour_sum + amount > max_hour:
                return PolicyDecision(
                    "deny",
                    "R-HOUR",
                    "rule",
                    f"hourly total {hour_sum + amount} exceeds cap {max_hour}",
                    True,
                )

    return PolicyDecision("allow", None, "rule", "allowed", False)

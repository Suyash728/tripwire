"""Selective compensating rollback in descending ledger idx and receipt generation."""

from __future__ import annotations

import copy
from typing import Any

from app.gateway.events import get_trace_bus
from app.ledger.chain import verify_chain
from app.provenance.graph import compute_blast_radius

COMPENSATING_TOOLS: dict[str, str] = {
    "refund.issue": "refund.reverse",
    "ledger.book": "ledger.void",
    "stock.restock": "stock.unrestock",
    "ticket.reply": "manual",
}


class AlreadyRolledBackError(Exception):
    """Raised when rollback is applied twice to the same incident."""


def _execute_compensating_tool(
    store: Any,
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    _ = (agent_id, task_id)
    if tool == "refund.reverse":
        rid = args["id"]
        row = store.refunds[rid]
        before = copy.deepcopy(row)
        row["status"] = "reversed"
        row["version"] += 1
        after = copy.deepcopy(row)
        return {
            "result": {"record": after, "version": after["version"]},
            "before_image": before,
            "after_image": after,
            "reads": [{"record": f"refunds:{rid}", "version": before["version"]}],
            "writes": [{"record": f"refunds:{rid}", "version": after["version"]}],
        }

    if tool == "ledger.void":
        fid = args["id"]
        row = store.finance_entries[fid]
        before = copy.deepcopy(row)
        row["status"] = "void"
        row["version"] += 1
        after = copy.deepcopy(row)
        return {
            "result": {"record": after, "version": after["version"]},
            "before_image": before,
            "after_image": after,
            "reads": [{"record": f"finance_entries:{fid}", "version": before["version"]}],
            "writes": [{"record": f"finance_entries:{fid}", "version": after["version"]}],
        }

    if tool == "stock.unrestock":
        sku = args["sku"]
        qty = int(args.get("qty", 1))
        row = store.inventory[sku]
        before = copy.deepcopy(row)
        row["qty"] = max(0, row["qty"] - qty)
        row["version"] += 1
        after = copy.deepcopy(row)
        return {
            "result": {"record": after, "version": after["version"]},
            "before_image": before,
            "after_image": after,
            "reads": [{"record": f"inventory:{sku}", "version": before["version"]}],
            "writes": [{"record": f"inventory:{sku}", "version": after["version"]}],
        }

    raise ValueError(f"unsupported compensating tool: {tool}")


def _compensating_args(entry: dict[str, Any]) -> dict[str, Any]:
    tool = entry["tool"]
    after = entry.get("after_image") or {}
    args = entry.get("args") or {}
    if tool == "refund.issue":
        return {"id": after.get("id") or args.get("id")}
    if tool == "ledger.book":
        return {"id": after.get("id") or args.get("id")}
    if tool == "stock.restock":
        return {"sku": args.get("sku") or after.get("sku"), "qty": int(args.get("qty", 1))}
    return {}


def plan_rollback(store: Any, incident_id: str) -> dict[str, Any] | None:
    """Build selective rollback plan in descending ledger idx without mutating state."""
    blast = compute_blast_radius(store, incident_id, mode="scoped")
    if blast is None:
        return None

    by_idx = {e["idx"]: e for e in store.all_ledger()}
    steps: list[dict[str, Any]] = []
    for order, orig_idx in enumerate(sorted(blast["tainted_idx"], reverse=True), start=1):
        entry = by_idx[orig_idx]
        comp_tool = COMPENSATING_TOOLS.get(entry["tool"], "manual")
        steps.append(
            {
                "order": order,
                "original_idx": orig_idx,
                "compensating_tool": comp_tool,
                "status": "planned",
            }
        )

    return {
        "mode": "plan",
        "steps": steps,
        "applied": False,
        "kept_count": blast["tripwire_kept_count"],
    }


def apply_rollback(store: Any, incident_id: str) -> dict[str, Any] | None:
    """Apply compensating rollback writes in descending ledger idx and store receipt."""
    incident = store.incidents.get(incident_id)
    if incident is None:
        return None
    if incident["status"] == "rolled_back":
        raise AlreadyRolledBackError(f"incident {incident_id} already rolled back")

    blast = compute_blast_radius(store, incident_id, mode="scoped")
    assert blast is not None
    by_idx = {e["idx"]: e for e in store.all_ledger()}

    steps: list[dict[str, Any]] = []
    reversed_items: list[dict[str, Any]] = []

    for order, orig_idx in enumerate(sorted(blast["tainted_idx"], reverse=True), start=1):
        entry = by_idx[orig_idx]
        comp_tool = COMPENSATING_TOOLS.get(entry["tool"], "manual")
        if comp_tool == "manual":
            steps.append(
                {
                    "order": order,
                    "original_idx": orig_idx,
                    "compensating_tool": "manual",
                    "status": "failed",
                }
            )
            continue

        comp_args = _compensating_args(entry)
        outcome = store.execute_and_append(
            agent_id=entry["agent_id"],
            task_id=f"rollback-{incident_id}",
            tool=comp_tool,
            args=comp_args,
            executor_fn=_execute_compensating_tool,
            kind="rollback",
            rollback_of=orig_idx,
            bypass_policy=True,
        )
        rb_entry = outcome["entry"]
        get_trace_bus().publish(
            {
                "ts": rb_entry["ts"],
                "agent": rb_entry["agent_id"],
                "tool": comp_tool,
                "decision": "rollback",
                "decider": "human",
                "rule_id": None,
                "ms": 0.0,
                "ledger_idx": rb_entry["idx"],
                "hash": rb_entry["hash"],
            }
        )
        steps.append(
            {
                "order": order,
                "original_idx": orig_idx,
                "compensating_tool": comp_tool,
                "status": "applied",
            }
        )
        amount = entry.get("args", {}).get("amount_inr")
        reversed_items.append(
            {
                "ledger_idx": orig_idx,
                "tool": comp_tool,
                "amount_inr": int(amount) if isinstance(amount, int) else None,
            }
        )

    incident["status"] = "rolled_back"
    chain_ok = verify_chain(store.all_ledger())["ok"]
    agent = store.agents.get(incident["agent_id"], {})
    blocked_calls = int(agent.get("blocked_calls", 0))
    kept_count = blast["tripwire_kept_count"]

    incident["receipt"] = {
        "incident_id": incident_id,
        "agent_id": incident["agent_id"],
        "tripped_at": incident["tripped_at"],
        "trip_rule_id": incident["trip_rule_id"],
        "containment_ms": incident["containment_ms"],
        "reversed": reversed_items,
        "kept_count": kept_count,
        "blocked_calls": blocked_calls,
        "chain_ok": chain_ok,
        "narrative": (
            f"Agent '{incident['agent_id']}' tripped {incident['trip_rule_id']} "
            f"in {incident['containment_ms']} ms. Reversed {len(reversed_items)} tainted actions, "
            f"preserved {kept_count} legit actions, and blocked {blocked_calls} follow-up calls."
        ),
    }

    return {
        "mode": "apply",
        "steps": steps,
        "applied": True,
        "kept_count": kept_count,
    }


def get_receipt(store: Any, incident_id: str) -> dict[str, Any] | None:
    """Return stored receipt or generate a pre-rollback summary from current DB state."""
    incident = store.incidents.get(incident_id)
    if incident is None:
        return None
    if incident.get("receipt") is not None:
        return copy.deepcopy(incident["receipt"])

    blast = compute_blast_radius(store, incident_id, mode="scoped")
    assert blast is not None
    chain_ok = verify_chain(store.all_ledger())["ok"]
    agent = store.agents.get(incident["agent_id"], {})
    blocked_calls = int(agent.get("blocked_calls", 0))
    kept_count = blast["tripwire_kept_count"]

    return {
        "incident_id": incident_id,
        "agent_id": incident["agent_id"],
        "tripped_at": incident["tripped_at"],
        "trip_rule_id": incident["trip_rule_id"],
        "containment_ms": incident["containment_ms"],
        "reversed": [],
        "kept_count": kept_count,
        "blocked_calls": blocked_calls,
        "chain_ok": chain_ok,
        "narrative": (
            f"Agent '{incident['agent_id']}' tripped {incident['trip_rule_id']} "
            f"in {incident['containment_ms']} ms. Rollback pending; {kept_count} legitimate "
            f"actions remain intact."
        ),
    }

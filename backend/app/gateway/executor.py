"""Tool executor for the Tripwire D2C store tool catalogue (agents/graph.md)."""

from __future__ import annotations

import copy
import uuid
from typing import Any


class ToolExecutionError(Exception):
    """Raised when tool arguments are invalid or a target record is missing."""


def execute_tool(
    store: Any,
    *,
    agent_id: str,
    task_id: str,
    tool: str,
    args: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool against store tables and return images + version stamps."""
    if tool == "ticket.read":
        tid = args.get("id")
        if not tid or tid not in store.tickets:
            raise ToolExecutionError(f"ticket not found: {tid}")
        rec = copy.deepcopy(store.tickets[tid])
        stamp = {"record": f"tickets:{tid}", "version": rec["version"]}
        return {
            "result": {"record": rec, "version": rec["version"]},
            "before_image": None,
            "after_image": None,
            "reads": [stamp],
            "writes": [],
        }

    if tool == "ticket.reply":
        tid = args.get("id")
        if not tid or tid not in store.tickets:
            raise ToolExecutionError(f"ticket not found: {tid}")
        row = store.tickets[tid]
        before = copy.deepcopy(row)
        read_stamp = {"record": f"tickets:{tid}", "version": before["version"]}
        row["replied"] = True
        if "body" in args:
            row["reply_body"] = args["body"]
        row["version"] += 1
        after = copy.deepcopy(row)
        write_stamp = {"record": f"tickets:{tid}", "version": after["version"]}
        return {
            "result": {"record": after, "version": after["version"]},
            "before_image": before,
            "after_image": after,
            "reads": [read_stamp],
            "writes": [write_stamp],
        }

    if tool == "order.read":
        oid = args.get("id")
        if not oid or oid not in store.orders:
            raise ToolExecutionError(f"order not found: {oid}")
        rec = copy.deepcopy(store.orders[oid])
        stamp = {"record": f"orders:{oid}", "version": rec["version"]}
        return {
            "result": {"record": rec, "version": rec["version"]},
            "before_image": None,
            "after_image": None,
            "reads": [stamp],
            "writes": [],
        }

    if tool == "refund.issue":
        oid = args.get("order_id")
        if not oid or oid not in store.orders:
            raise ToolExecutionError(f"order not found: {oid}")
        amount = args.get("amount_inr")
        if not isinstance(amount, int) or amount < 0:
            raise ToolExecutionError("amount_inr must be a non-negative integer")
        order = store.orders[oid]
        read_stamp = {"record": f"orders:{oid}", "version": order["version"]}

        rid = args.get("id") or f"R-{uuid.uuid4().hex[:8]}"
        new_refund = {
            "id": rid,
            "order_id": oid,
            "amount_inr": amount,
            "status": "issued",
            "issued_by": agent_id,
            "task_id": task_id,
            "version": 1,
        }
        store.refunds[rid] = new_refund
        after = copy.deepcopy(new_refund)
        write_stamp = {"record": f"refunds:{rid}", "version": 1}
        return {
            "result": {"record": after, "version": 1},
            "before_image": None,
            "after_image": after,
            "reads": [read_stamp],
            "writes": [write_stamp],
        }

    if tool == "refund.read":
        rid = args.get("id")
        if not rid or rid not in store.refunds:
            raise ToolExecutionError(f"refund not found: {rid}")
        rec = copy.deepcopy(store.refunds[rid])
        stamp = {"record": f"refunds:{rid}", "version": rec["version"]}
        return {
            "result": {"record": rec, "version": rec["version"]},
            "before_image": None,
            "after_image": None,
            "reads": [stamp],
            "writes": [],
        }

    if tool == "ledger.book":
        ref_id = args.get("ref_id")
        if not ref_id or ref_id not in store.refunds:
            raise ToolExecutionError(f"refund not found: {ref_id}")
        refund = store.refunds[ref_id]
        read_stamp = {"record": f"refunds:{ref_id}", "version": refund["version"]}

        fid = args.get("id") or f"F-{uuid.uuid4().hex[:8]}"
        entry_type = args.get("entry_type", "refund_booking")
        amount = args.get("amount_inr", refund["amount_inr"])
        new_entry = {
            "id": fid,
            "ref_id": ref_id,
            "entry_type": entry_type,
            "amount_inr": amount,
            "status": "booked",
            "version": 1,
        }
        store.finance_entries[fid] = new_entry
        after = copy.deepcopy(new_entry)
        write_stamp = {"record": f"finance_entries:{fid}", "version": 1}
        return {
            "result": {"record": after, "version": 1},
            "before_image": None,
            "after_image": after,
            "reads": [read_stamp],
            "writes": [write_stamp],
        }

    if tool == "stock.read":
        sku = args.get("sku")
        if not sku or sku not in store.inventory:
            raise ToolExecutionError(f"inventory sku not found: {sku}")
        rec = copy.deepcopy(store.inventory[sku])
        stamp = {"record": f"inventory:{sku}", "version": rec["version"]}
        return {
            "result": {"record": rec, "version": rec["version"]},
            "before_image": None,
            "after_image": None,
            "reads": [stamp],
            "writes": [],
        }

    if tool == "stock.restock":
        sku = args.get("sku")
        ref_id = args.get("ref_id")
        if not sku or sku not in store.inventory:
            raise ToolExecutionError(f"inventory sku not found: {sku}")
        reads = []
        if ref_id:
            if ref_id not in store.refunds:
                raise ToolExecutionError(f"refund not found: {ref_id}")
            reads.append(
                {"record": f"refunds:{ref_id}", "version": store.refunds[ref_id]["version"]}
            )
        qty = int(args.get("qty", 1))
        row = store.inventory[sku]
        before = copy.deepcopy(row)
        reads.append({"record": f"inventory:{sku}", "version": before["version"]})
        row["qty"] += qty
        row["version"] += 1
        after = copy.deepcopy(row)
        write_stamp = {"record": f"inventory:{sku}", "version": after["version"]}
        return {
            "result": {"record": after, "version": after["version"]},
            "before_image": before,
            "after_image": after,
            "reads": reads,
            "writes": [write_stamp],
        }

    raise ToolExecutionError(f"unknown tool: {tool}")

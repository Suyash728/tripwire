"""Read-stamp tracking, provenance edge construction, and NetworkX blast radius."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import networkx as nx


def _parse_ts(ts: str) -> float:
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.timestamp()


def compute_blast_radius(
    store: Any,
    incident_id: str,
    *,
    mode: str = "scoped",
) -> dict[str, Any] | None:
    """Compute tainted and kept write nodes via NetworkX descendants."""
    incident = store.incidents.get(incident_id)
    if not incident:
        return None

    entries = [e for e in store.all_ledger() if e["kind"] == "action" and e["decision"] == "allow"]

    producers: dict[tuple[str, int], int] = {}
    task_reads: dict[str, list[tuple[str, int]]] = {}
    write_entries: list[dict[str, Any]] = []
    edges: list[dict[str, int]] = []
    seen_edges: set[tuple[int, int]] = set()

    for entry in entries:
        idx = entry["idx"]
        task_id = entry["task_id"]
        reads = [(r["record"], int(r["version"])) for r in entry.get("reads", [])]
        writes = [(w["record"], int(w["version"])) for w in entry.get("writes", [])]

        task_reads.setdefault(task_id, []).extend(reads)

        if writes:
            write_entries.append(entry)
            deps = reads if mode == "scoped" else task_reads.get(task_id, [])
            for rec, ver in deps:
                from_idx = producers.get((rec, ver))
                if from_idx is not None and from_idx < idx and (from_idx, idx) not in seen_edges:
                    seen_edges.add((from_idx, idx))
                    edges.append({"from": from_idx, "to": idx})

            for rec, ver in writes:
                producers[(rec, ver)] = idx

    g = nx.DiGraph()
    for entry in write_entries:
        g.add_node(entry["idx"])
    for edge in edges:
        g.add_edge(edge["from"], edge["to"])

    trip_rule = incident["trip_rule_id"]
    trip_agent = incident["agent_id"]
    trip_task = incident["task_id"]
    trip_family = trip_task.rsplit("-", 1)[0] if "-" in trip_task else trip_task
    tripped_epoch = _parse_ts(incident["tripped_at"])

    seed_nodes: set[int] = set()
    for entry in write_entries:
        if entry["agent_id"] != trip_agent:
            continue
        if trip_rule == "R-HOUR":
            entry_family = (
                entry["task_id"].rsplit("-", 1)[0] if "-" in entry["task_id"] else entry["task_id"]
            )
            if (tripped_epoch - _parse_ts(entry["ts"])) <= 3600.0 and (
                entry["task_id"] == trip_task or entry_family == trip_family
            ):
                seed_nodes.add(entry["idx"])
        elif entry["task_id"] == trip_task:
            seed_nodes.add(entry["idx"])

    tainted_set: set[int] = set(seed_nodes)
    for s in seed_nodes:
        tainted_set.update(nx.descendants(g, s))

    write_indices = [e["idx"] for e in write_entries]
    tainted_idx = sorted(i for i in write_indices if i in tainted_set)
    kept_idx = sorted(i for i in write_indices if i not in tainted_set)

    min_tainted = min(tainted_idx) if tainted_idx else None
    naive_lost_count = (
        sum(1 for i in kept_idx if min_tainted is not None and i >= min_tainted)
        if min_tainted is not None
        else 0
    )

    nodes = [
        {
            "ledger_idx": e["idx"],
            "agent_id": e["agent_id"],
            "tool": e["tool"],
            "tainted": e["idx"] in tainted_set,
        }
        for e in write_entries
    ]

    return {
        "incident_id": incident_id,
        "nodes": nodes,
        "edges": edges,
        "tainted_idx": tainted_idx,
        "kept_idx": kept_idx,
        "naive_lost_count": naive_lost_count,
        "tripwire_reversed_count": len(tainted_idx),
        "tripwire_kept_count": len(kept_idx),
    }

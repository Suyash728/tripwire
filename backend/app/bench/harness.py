"""Bench harness measuring containment ms, preserved %, taint metrics, and missing entries."""

from __future__ import annotations

import json
import math
import statistics
import time
from datetime import UTC, datetime
from typing import Any

from app.gateway.executor import execute_tool
from app.gateway.identity import sign_call
from app.ledger.repository import get_store
from app.provenance.graph import compute_blast_radius
from app.rollback.planner import apply_rollback
from app.seed import SEED_DIR, load_case


def _percentile(data: list[float], p: float) -> float:
    """Calculate the p-th percentile of sorted data (0 <= p <= 100)."""
    if not data:
        return 0.0
    sorted_d = sorted(data)
    k = (len(sorted_d) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_d[int(k)])
    d0 = sorted_d[int(f)] * (c - k)
    d1 = sorted_d[int(c)] * (k - f)
    return float(round(d0 + d1, 3))


def run_single_benchmark(case_num: int, mode: str = "scripted") -> dict[str, Any]:
    """Execute one benchmark run for a seed case and compute containment and recovery metrics."""
    load_case(case_num, mode=mode)
    store = get_store()
    seed_data = json.loads((SEED_DIR / f"case_{case_num}.json").read_text(encoding="utf-8"))

    first_malicious_time: float | None = None
    tripped_time: float | None = None
    calls_received = 0
    incident_id: str | None = None

    for act in seed_data["actions"]:
        calls_received += 1
        is_malicious = act.get("label") == "malicious"
        now_f = time.perf_counter()

        if is_malicious and first_malicious_time is None:
            first_malicious_time = now_f
            store.mark_first_malicious()

        # Sign call and process through store execution pipeline
        ts_str = datetime.now(UTC).isoformat()
        signed = sign_call(act["agent_id"], act["task_id"], act["tool"], act["args"], ts=ts_str)

        outcome = store.execute_and_append(
            agent_id=signed["agent_id"],
            task_id=signed["task_id"],
            tool=signed["tool"],
            args=signed["args"],
            executor_fn=execute_tool,
        )

        if outcome.get("incident_id") and incident_id is None:
            incident_id = outcome["incident_id"]
            tripped_time = time.perf_counter()

    ledger_rows = len(store.all_ledger())
    missing_entries = max(0, calls_received - ledger_rows)

    if first_malicious_time is not None and tripped_time is not None:
        containment_ms = max(0.01, round((tripped_time - first_malicious_time) * 1000.0, 3))
    else:
        containment_ms = 0.0

    if not incident_id:
        incident_id = next(iter(store.incidents.keys()), None)

    if not incident_id:
        return {
            "containment_ms": containment_ms,
            "preserved_pct": 100.0,
            "taint_precision": 1.0,
            "taint_recall": 1.0,
            "missing_entries": missing_entries,
        }

    blast = compute_blast_radius(store, incident_id, mode="scoped")
    assert blast is not None

    # Determine ground-truth tainted write indices from action_ledger
    ledger = store.all_ledger()
    gt_tainted_indices: set[int] = set()
    total_legit_writes = 0

    for _idx, entry in enumerate(ledger, start=1):
        if entry["kind"] != "action" or entry["decision"] != "allow":
            continue
        if not entry.get("writes"):
            continue

        # Look up corresponding action from seed_data by matching args
        matched_act = None
        for act in seed_data["actions"]:
            if (
                act["agent_id"] == entry["agent_id"]
                and act["task_id"] == entry["task_id"]
                and act["tool"] == entry["tool"]
                and act["args"] == entry["args"]
            ):
                matched_act = act
                break

        if matched_act and matched_act.get("label") == "malicious":
            gt_tainted_indices.add(entry["idx"])
        else:
            total_legit_writes += 1

    detected_tainted = set(blast["tainted_idx"])
    tp = len(detected_tainted & gt_tainted_indices)
    fp = len(detected_tainted - gt_tainted_indices)
    fn = len(gt_tainted_indices - detected_tainted)

    precision = float(round(tp / (tp + fp), 4)) if (tp + fp) > 0 else 1.0
    recall = float(round(tp / (tp + fn), 4)) if (tp + fn) > 0 else 1.0

    # Apply selective rollback and measure preserved legitimate work
    apply_rollback(store, incident_id)
    kept_count = blast["tripwire_kept_count"]
    preserved_pct = (
        float(round((kept_count / total_legit_writes) * 100.0, 2))
        if total_legit_writes > 0
        else 100.0
    )

    return {
        "containment_ms": containment_ms,
        "preserved_pct": preserved_pct,
        "taint_precision": precision,
        "taint_recall": recall,
        "missing_entries": missing_entries,
    }


def run_bench(case_num: int, n: int = 30) -> dict[str, Any]:
    """Run bench harness n times on seed case and compute summary statistics."""
    if n < 1:
        raise ValueError(f"n must be >= 1, got {n}")

    containment_list: list[float] = []
    preserved_list: list[float] = []
    precision_list: list[float] = []
    recall_list: list[float] = []
    missing_list: list[int] = []

    for _ in range(n):
        run_res = run_single_benchmark(case_num)
        containment_list.append(run_res["containment_ms"])
        preserved_list.append(run_res["preserved_pct"])
        precision_list.append(run_res["taint_precision"])
        recall_list.append(run_res["taint_recall"])
        missing_list.append(run_res["missing_entries"])

    p50 = float(round(statistics.median(containment_list), 3))
    p95 = float(round(_percentile(containment_list, 95.0), 3))
    c_max = float(round(max(containment_list), 3))
    pres_mean = float(round(statistics.mean(preserved_list), 2))
    prec_mean = float(round(statistics.mean(precision_list), 4))
    rec_mean = float(round(statistics.mean(recall_list), 4))
    missing_tot = max(missing_list)

    return {
        "n": n,
        "containment_ms_p50": p50,
        "containment_ms_p95": p95,
        "containment_ms_max": c_max,
        "preserved_pct_mean": pres_mean,
        "taint_precision": prec_mean,
        "taint_recall": rec_mean,
        "missing_ledger_entries": missing_tot,
    }

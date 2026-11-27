"""Slice 3 tests: provenance, NetworkX blast radius, selective rollback, replay oracle, receipt."""

from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def _run_seed_until_trip(call, case_num: int) -> list[dict]:
    seed_data = json.loads((SEED_DIR / f"case_{case_num}.json").read_text(encoding="utf-8"))
    for act in seed_data["actions"]:
        call(act["agent_id"], act["task_id"], act["tool"], act["args"])
    return seed_data["actions"]


def _active_state(store) -> dict:
    return {
        "refunds": {
            k: {
                "order_id": v["order_id"],
                "amount_inr": v["amount_inr"],
                "status": v["status"],
            }
            for k, v in store.refunds.items()
            if v["status"] == "issued"
        },
        "finance_entries": {
            k: {
                "ref_id": v["ref_id"],
                "amount_inr": v["amount_inr"],
                "status": v["status"],
            }
            for k, v in store.finance_entries.items()
            if v["status"] == "booked"
        },
        "inventory": {k: v["qty"] for k, v in store.inventory.items()},
        "tickets": {k: v["replied"] for k, v in store.tickets.items()},
    }


def test_case1_blast_radius_and_selective_rollback_replay_oracle(client, admin, load_case, call):
    # 1. Replay legit-only actions to get expected oracle state
    load_case(1)
    seed_data = json.loads((SEED_DIR / "case_1.json").read_text(encoding="utf-8"))
    for act in seed_data["actions"]:
        if act["label"] == "legit":
            assert (
                call(act["agent_id"], act["task_id"], act["tool"], act["args"]).status_code == 200
            )

    from app.ledger.repository import get_store

    oracle_state = _active_state(get_store())

    # 2. Run full Case 1 (legit + malicious up to trip)
    load_case(1)
    _run_seed_until_trip(call, 1)

    br = client.get("/incidents/inc-1/blast-radius")
    assert br.status_code == 200
    data = br.json()["data"]
    assert len(data["tainted_idx"]) == 11
    assert data["tripwire_reversed_count"] == 11
    assert data["tripwire_kept_count"] == 37

    # Plan mode
    plan_r = client.post("/incidents/inc-1/rollback", json={"mode": "plan"}, headers=admin)
    assert plan_r.status_code == 200
    assert plan_r.json()["data"]["applied"] is False
    steps = plan_r.json()["data"]["steps"]
    assert len(steps) == 11
    assert [s["original_idx"] for s in steps] == sorted(
        [s["original_idx"] for s in steps], reverse=True
    )

    # Apply mode
    apply_r = client.post("/incidents/inc-1/rollback", json={"mode": "apply"}, headers=admin)
    assert apply_r.status_code == 200
    assert apply_r.json()["data"]["applied"] is True
    assert apply_r.json()["data"]["kept_count"] == 37

    # Double apply returns 409
    dup_r = client.post("/incidents/inc-1/rollback", json={"mode": "apply"}, headers=admin)
    assert dup_r.status_code == 409

    # Final DB state equals legit-only replay oracle
    final_state = _active_state(get_store())
    assert final_state == oracle_state

    # Receipt matches DB
    rec_r = client.get("/incidents/inc-1/receipt")
    assert rec_r.status_code == 200
    rec = rec_r.json()["data"]
    assert rec["incident_id"] == "inc-1"
    assert rec["trip_rule_id"] == "R-TASK"
    assert len(rec["reversed"]) == 11
    assert rec["kept_count"] == 37
    assert rec["chain_ok"] is True


def test_case2_scoped_vs_strict_over_taint(client, load_case, call):
    load_case(2)
    _run_seed_until_trip(call, 2)

    br_scoped = client.get("/incidents/inc-1/blast-radius?mode=scoped").json()["data"]
    br_strict = client.get("/incidents/inc-1/blast-radius?mode=strict").json()["data"]

    assert len(br_scoped["tainted_idx"]) == 11
    assert len(br_strict["tainted_idx"]) == 12


def test_case3_salami_rollback_replay_oracle(client, admin, load_case, call):
    load_case(3)
    seed_data = json.loads((SEED_DIR / "case_3.json").read_text(encoding="utf-8"))
    for act in seed_data["actions"]:
        if act["label"] == "legit":
            assert (
                call(act["agent_id"], act["task_id"], act["tool"], act["args"]).status_code == 200
            )

    from app.ledger.repository import get_store

    oracle_state = _active_state(get_store())

    load_case(3)
    _run_seed_until_trip(call, 3)

    br = client.get("/incidents/inc-1/blast-radius").json()["data"]
    assert len(br["tainted_idx"]) == 12
    assert br["tripwire_kept_count"] == 33

    apply_r = client.post("/incidents/inc-1/rollback", json={"mode": "apply"}, headers=admin)
    assert apply_r.status_code == 200
    assert _active_state(get_store()) == oracle_state

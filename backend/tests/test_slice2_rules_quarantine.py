"""Slice 2 tests: policy rules, canaries, quarantine, inject drill, and SSE trace events."""

from __future__ import annotations

import json
from pathlib import Path

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


def test_r_tool_default_deny(client, load_case, call):
    load_case(1)
    r = call("support", "t-1", "refund.issue", {"order_id": "ORD-1", "amount_inr": 100})
    assert r.status_code == 403
    body = r.json()
    assert body["data"]["decision"] == "deny"
    assert body["data"]["rule_id"] == "R-TOOL"


def test_r_call_denies_over_5000_and_quarantines(client, load_case, call):
    load_case(1)
    r = call("refund", "t-big", "refund.issue", {"order_id": "ORD-1", "amount_inr": 5001})
    assert r.status_code == 403
    assert r.json()["data"]["decision"] == "deny"
    assert r.json()["data"]["rule_id"] == "R-CALL"

    # Subsequent call is quarantined_deny and Support still gets 200
    r2 = call("refund", "t-next", "order.read", {"id": "ORD-1"})
    assert r2.status_code == 403
    assert r2.json()["data"]["decision"] == "quarantined_deny"

    r_sup = call("support", "t-sup", "ticket.read", {"id": "T-1"})
    assert r_sup.status_code == 200
    assert r_sup.json()["data"]["decision"] == "allow"

    agents = {a["id"]: a for a in client.get("/agents").json()["data"]["agents"]}
    assert agents["refund"]["status"] == "quarantined"
    assert agents["refund"]["blocked_calls"] == 1
    assert agents["support"]["status"] == "active"


def test_r_canary_trips_immediately(client, load_case, call):
    load_case(1)
    r = call("support", "t-can", "order.read", {"id": "CANARY-0001"})
    assert r.status_code == 403
    assert r.json()["data"]["decision"] == "deny"
    assert r.json()["data"]["rule_id"] == "R-CANARY"

    agents = {a["id"]: a for a in client.get("/agents").json()["data"]["agents"]}
    assert agents["support"]["status"] == "quarantined"


def test_legit_seed_traffic_never_trips(client, load_case, call):
    for case_num in (1, 2, 3):
        load_case(case_num)
        seed_data = json.loads((SEED_DIR / f"case_{case_num}.json").read_text(encoding="utf-8"))
        for idx, act in enumerate(seed_data["actions"]):
            if act["label"] != "legit":
                continue
            if act["tool"] == "refund.read" and act["args"].get("id") == "R-M1":
                continue
            r = call(act["agent_id"], act["task_id"], act["tool"], act["args"])
            assert r.status_code == 200, f"case {case_num} action {idx} failed: {r.text}"
            assert r.json()["data"]["decision"] == "allow"


def test_case1_trips_r_task_and_isolates_refund(client, load_case, call):
    load_case(1)
    seed_data = json.loads((SEED_DIR / "case_1.json").read_text(encoding="utf-8"))
    tripped = False
    for act in seed_data["actions"]:
        r = call(act["agent_id"], act["task_id"], act["tool"], act["args"])
        if r.status_code == 403:
            assert r.json()["data"]["rule_id"] == "R-TASK"
            tripped = True
            break
        assert r.status_code == 200

    assert tripped is True
    assert call("refund", "t-after", "order.read", {"id": "ORD-1"}).status_code == 403
    assert call("support", "t-after", "ticket.read", {"id": "T-1"}).status_code == 200


def test_case3_trips_r_hour_and_not_r_task(client, load_case, call):
    load_case(3)
    seed_data = json.loads((SEED_DIR / "case_3.json").read_text(encoding="utf-8"))
    tripped_rule = None
    for act in seed_data["actions"]:
        r = call(act["agent_id"], act["task_id"], act["tool"], act["args"])
        if r.status_code == 403:
            tripped_rule = r.json()["data"]["rule_id"]
            break
        assert r.status_code == 200

    assert tripped_rule == "R-HOUR"


def test_manual_quarantine_and_inject_and_sse_events(client, admin, load_case):
    load_case(1)
    r_q = client.post("/agents/inventory/quarantine", headers=admin)
    assert r_q.status_code == 200
    assert r_q.json()["data"]["status"] == "quarantined"

    r_404 = client.post("/agents/unknown/quarantine", headers=admin)
    assert r_404.status_code in (404, 422)

    for fault in ("injection", "canary_read", "salami_split"):
        load_case(1)
        r_inj = client.post("/demo/inject", json={"fault": fault}, headers=admin)
        assert r_inj.status_code == 200
        assert r_inj.json()["data"]["fault"] == fault

    r_sse = client.get("/events?once=1")
    assert r_sse.status_code == 200
    assert "text/event-stream" in r_sse.headers["content-type"]
    lines = [ln for ln in r_sse.text.splitlines() if ln.startswith("data: ")]
    assert len(lines) >= 1
    ev = json.loads(lines[-1].removeprefix("data: "))
    assert ev["decider"] in {"rule", "canary", "human"}

"""Slice 1 tests: HMAC identity, append-only hash-chained ledger, executor, and seed cases."""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor

from tests.conftest import sign_call


def test_unsigned_call_rejected(client):
    r = client.post(
        "/gw/call",
        json={
            "agent_id": "support",
            "task_id": "t-1",
            "tool": "ticket.read",
            "args": {"id": "T-1"},
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["success"] is False
    assert body["error"] is not None


def test_forged_signature_returns_401(client, load_case):
    load_case(1)
    payload = sign_call("support", "t-1", "ticket.read", {"id": "T-1"})
    payload["signature"] = "0" * 64
    r = client.post("/gw/call", json=payload)
    assert r.status_code == 401
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "unauthorized"


def test_stale_timestamp_returns_401(client, load_case):
    load_case(1)
    stale_ts = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() - 60))
    payload = sign_call("support", "t-1", "ticket.read", {"id": "T-1"}, ts=stale_ts)
    r = client.post("/gw/call", json=payload)
    assert r.status_code == 401
    assert r.json()["success"] is False


def test_replayed_nonce_returns_401(client, load_case):
    load_case(1)
    payload = sign_call("support", "t-1", "ticket.read", {"id": "T-1"}, nonce="fixed-nonce-1")
    r1 = client.post("/gw/call", json=payload)
    assert r1.status_code == 200
    assert r1.json()["success"] is True

    r2 = client.post("/gw/call", json=payload)
    assert r2.status_code == 401
    assert r2.json()["success"] is False


def test_signed_call_executes_and_lands_in_verified_ledger(client, load_case, call):
    load_case(1)
    r = call("support", "t-1", "ticket.read", {"id": "T-1"})
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["data"]["decision"] == "allow"
    assert data["data"]["ledger_idx"] == 1
    assert data["data"]["result"]["record"]["id"] == "T-1"
    assert data["data"]["result"]["version"] == 1

    ledger_r = client.get("/ledger?after=0&limit=100")
    assert ledger_r.status_code == 200
    entries = ledger_r.json()["data"]["entries"]
    assert len(entries) == 1
    assert entries[0]["idx"] == 1
    assert entries[0]["prev_hash"] == "0" * 64
    assert len(entries[0]["hash"]) == 64

    verify_r = client.get("/ledger/verify")
    assert verify_r.status_code == 200
    v = verify_r.json()["data"]
    assert v["ok"] is True
    assert v["first_broken_idx"] is None
    assert v["anchor_matches"] is True
    assert v["head_hash"] == entries[0]["hash"]


def test_parallel_calls_produce_gapless_ledger_without_fork(client, load_case):
    load_case(1)
    p1 = sign_call("support", "t-p1", "ticket.read", {"id": "T-1"})
    p2 = sign_call("refund", "t-p2", "order.read", {"id": "ORD-1"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(client.post, "/gw/call", json=p1)
        f2 = pool.submit(client.post, "/gw/call", json=p2)
        r1, r2 = f1.result(), f2.result()

    assert r1.status_code == 200
    assert r2.status_code == 200

    entries = client.get("/ledger").json()["data"]["entries"]
    assert [e["idx"] for e in entries] == [1, 2]
    assert entries[0]["prev_hash"] == "0" * 64
    assert entries[1]["prev_hash"] == entries[0]["hash"]

    v = client.get("/ledger/verify").json()["data"]
    assert v["ok"] is True
    assert v["anchor_matches"] is True


def test_tamper_row_breaks_verify_at_first_broken_idx(client, admin, load_case, call):
    load_case(1)
    assert call("support", "t-1", "ticket.read", {"id": "T-1"}).status_code == 200
    assert call("support", "t-2", "ticket.reply", {"id": "T-1", "body": "ok"}).status_code == 200
    assert call("refund", "t-3", "order.read", {"id": "ORD-1"}).status_code == 200

    t_r = client.post("/demo/tamper", json={"ledger_idx": 2}, headers=admin)
    assert t_r.status_code == 200
    assert t_r.json()["success"] is True

    v = client.get("/ledger/verify").json()["data"]
    assert v["ok"] is False
    assert v["first_broken_idx"] == 2


def test_anchor_mismatch_is_detected(client, load_case, call, monkeypatch, tmp_path):
    anchor_file = tmp_path / "anchor.log"
    monkeypatch.setenv("ANCHOR_LOG_PATH", str(anchor_file))
    load_case(1)
    assert call("support", "t-1", "ticket.read", {"id": "T-1"}).status_code == 200

    # Corrupt anchor file outside DB
    anchor_file.write_text("1 " + ("f" * 64) + "\n")

    v = client.get("/ledger/verify").json()["data"]
    assert v["ok"] is False
    assert v["anchor_matches"] is False


def test_list_agents_and_seed_cases(client, load_case):
    for case_num in (1, 2, 3):
        res = load_case(case_num)
        assert res["case"] == case_num
        agents = client.get("/agents").json()["data"]["agents"]
        ids = {a["id"] for a in agents}
        assert ids == {"support", "refund", "inventory", "finance"}
        assert all(a["status"] == "active" for a in agents)
        assert os.path.exists(f"../seed/case_{case_num}.json") or os.path.exists(
            f"seed/case_{case_num}.json"
        )

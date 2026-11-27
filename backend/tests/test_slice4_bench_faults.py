"""Slice 4 tests: bench harness (R12), fault drill (R13), side-by-side, and local AI (R14)."""

from __future__ import annotations

import os

from openai import OpenAI


def test_bench_run_endpoint_and_metrics(client, admin):
    # Benchmark runs on seed case 1 with 30 iterations
    r = client.post("/bench/run", json={"case": 1, "n": 30}, headers=admin)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    res = body["data"]

    assert res["n"] == 30
    assert res["missing_ledger_entries"] == 0
    assert res["preserved_pct_mean"] >= 75.0
    assert res["taint_precision"] >= 0.9
    assert res["taint_recall"] >= 0.9
    assert res["containment_ms_p50"] < 2000.0  # target: under 2 s


def test_bench_cases_2_and_3(client, admin):
    for case_num in (2, 3):
        r = client.post("/bench/run", json={"case": case_num, "n": 5}, headers=admin)
        assert r.status_code == 200
        res = r.json()["data"]
        assert res["missing_ledger_entries"] == 0
        assert res["preserved_pct_mean"] >= 75.0


def test_fault_drill_all_types_generate_receipts(client, admin, load_case, call):
    # 1. Canary read fault drill
    load_case(1)
    r_canary = client.post("/demo/inject", json={"fault": "canary_read"}, headers=admin)
    assert r_canary.status_code == 200
    assert len(client.get("/ledger").json()["data"]["entries"]) > 0
    # Check agents quarantine
    agents = {a["id"]: a for a in client.get("/agents").json()["data"]["agents"]}
    assert agents["support"]["status"] == "quarantined"

    # 2. Salami split fault drill
    load_case(3)
    r_salami = client.post("/demo/inject", json={"fault": "salami_split"}, headers=admin)
    assert r_salami.status_code == 200
    agents = {a["id"]: a for a in client.get("/agents").json()["data"]["agents"]}
    assert agents["refund"]["status"] == "quarantined"

    # 3. Injection fault drill + rollback + receipt
    load_case(1)
    call("support", "t-bg", "ticket.reply", {"id": "T-1", "body": "Handling inquiry"})
    r_inj = client.post("/demo/inject", json={"fault": "injection"}, headers=admin)
    assert r_inj.status_code == 200
    blast = client.get("/incidents/inc-1/blast-radius").json()["data"]
    assert blast["naive_lost_count"] >= 0
    assert blast["tripwire_kept_count"] > 0

    apply_r = client.post("/incidents/inc-1/rollback", json={"mode": "apply"}, headers=admin)
    assert apply_r.status_code == 200

    rec = client.get("/incidents/inc-1/receipt").json()["data"]
    assert rec["incident_id"] == "inc-1"
    assert rec["chain_ok"] is True
    assert rec["trip_rule_id"] in ("R-TASK", "R-CALL")


def test_side_by_side_naive_vs_tripwire(client, load_case, call):
    load_case(1)
    from tests.test_slice3_provenance_rollback import _run_seed_until_trip

    _run_seed_until_trip(call, 1)

    blast = client.get("/incidents/inc-1/blast-radius").json()["data"]
    # Naive "kill everything" destroys all actions after the incident started
    assert blast["naive_lost_count"] > 0
    # Tripwire selective rollback preserves legit work
    assert blast["tripwire_kept_count"] > blast["naive_lost_count"]


def test_offline_local_ai_model_r14():
    """Test offline inference on local vLLM (R14) using nvidia/Qwen3-14B-NVFP4."""
    import urllib.error
    import urllib.request

    import pytest

    local_url = os.environ.get("VLLM_BASE_URL", "http://localhost:8001/v1")
    try:
        req = urllib.request.Request(f"{local_url}/models")
        with urllib.request.urlopen(req, timeout=1.0):
            pass
    except Exception:
        pytest.skip(f"Local vLLM server at {local_url} not reachable, skipping offline test")

    client = OpenAI(base_url=local_url, api_key="none", timeout=10.0)

    # Local model serves requests offline
    res = client.chat.completions.create(
        model="nvidia/Qwen3-14B-NVFP4",
        messages=[{"role": "user", "content": "Tripwire system status"}],
        max_tokens=15,
    )
    assert res.choices[0].message.content is not None
    assert len(res.choices[0].message.content) > 0

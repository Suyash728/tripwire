"""HTTP contract: envelope on success and errors, validation, CORS, security headers, rate limit."""

import time

import pytest

from app.services import llm

ENVELOPE_KEYS = {"success", "data", "error"}


def test_health_returns_envelope(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"success": True, "data": {"status": "up"}, "error": None}


def test_samples_are_seeded(client):
    body = client.get("/samples").json()
    assert body["success"] and len(body["data"]) >= 1
    assert {"id", "title", "input"} <= set(body["data"][0])


@pytest.mark.parametrize(
    "payload",
    [{}, {"input": ""}, {"input": 123}, {"input": "x" * 4001}],
    ids=["missing", "empty", "wrong-type", "too-long"],
)
def test_invalid_body_returns_422_envelope(client, payload):
    r = client.post("/runs", json=payload)
    assert r.status_code == 422
    body = r.json()
    assert set(body) == ENVELOPE_KEYS
    assert body["success"] is False and body["data"] is None
    assert body["error"].startswith("invalid request")


def test_unknown_route_returns_404_envelope(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.json()["success"] is False


def test_security_headers_present(client):
    h = client.get("/health").headers
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in h["content-security-policy"]
    assert "referrer-policy" in h and "permissions-policy" in h


def test_cors_allows_configured_origin(client):
    r = client.options(
        "/runs",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_allows_authorization_header(client):
    r = client.options(
        "/runs",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert r.status_code == 200
    assert "authorization" in r.headers["access-control-allow-headers"].lower()


def test_cors_rejects_unknown_origin(client):
    r = client.options(
        "/runs",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers
    simple = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in simple.headers


def test_rate_limit_returns_429_envelope(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    for _ in range(2):
        assert client.post("/runs", json={"input": "x"}).status_code == 200
    r = client.post("/runs", json={"input": "x"})
    assert r.status_code == 429
    assert r.json()["success"] is False and "rate limit" in r.json()["error"]


def test_resume_unknown_run_fails_cleanly(client):
    body = client.post("/runs/doesnotexist/resume", json={"approve": True}).json()
    assert body == {"success": False, "data": None, "error": "unknown or still-running run"}


def _wait(client, run_id, done):
    for _ in range(100):
        data = client.get(f"/runs/{run_id}").json()["data"]
        if done(data):
            return data
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} did not finish: {data}")


def test_graph_interrupt_and_resume(client, monkeypatch):
    monkeypatch.setattr(llm, "chat", lambda *a, **k: llm.LLMResult("stub", "stub", "stub", 1))
    run_id = client.post("/runs", json={"input": "x"}).json()["data"]["run_id"]
    data = _wait(client, run_id, lambda d: any(e["status"] == "interrupted" for e in d["events"]))
    assert [e["node"] for e in data["events"]][:4] == ["planner", "planner", "tools", "tools"]
    assert client.post(f"/runs/{run_id}/resume", json={"approve": True}).json()["success"]
    data = _wait(client, run_id, lambda d: d["state"].get("result"))
    assert data["state"]["result"] == "action executed"


def test_graph_reject_cancels_action(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    run_id = client.post("/runs", json={"input": "x"}).json()["data"]["run_id"]
    _wait(client, run_id, lambda d: any(e["status"] == "interrupted" for e in d["events"]))
    client.post(f"/runs/{run_id}/resume", json={"approve": False})
    data = _wait(client, run_id, lambda d: d["state"].get("result"))
    assert data["state"]["result"] == "action cancelled"
    assert {e["tier_used"] for e in data["events"] if e["tier_used"]} == {"mock"}


def test_graph_error_surfaces_in_trace(client, monkeypatch):
    def boom(*_a, **_k):
        raise llm.AllTiersFailed("groq: no GROQ_API_KEY")

    monkeypatch.setattr(llm, "chat", boom)
    run_id = client.post("/runs", json={"input": "x"}).json()["data"]["run_id"]
    data = _wait(client, run_id, lambda d: any(e["status"] == "error" for e in d["events"]))
    err = next(e for e in data["events"] if e["status"] == "error")
    assert err["node"] == "graph" and "no GROQ_API_KEY" in err["error"]

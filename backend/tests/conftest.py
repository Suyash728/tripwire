"""Shared fixtures. Fixtures assume the app exposes `app.main.app` and `app.seed.load_case`."""
import hashlib
import hmac
import json
import os
import time
import uuid

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ADMIN_TOKEN", "test-admin")
os.environ.setdefault("RATE_LIMIT_PER_MIN", "0")
for agent in ("SUPPORT", "REFUND", "INVENTORY", "FINANCE"):
    os.environ.setdefault(f"AGENT_SECRET_{agent}", f"secret-{agent.lower()}")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def sign_call(agent_id: str, task_id: str, tool: str, args: dict, ts: str | None = None, nonce: str | None = None) -> dict:
    ts = ts or time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    nonce = nonce or uuid.uuid4().hex
    secret = os.environ[f"AGENT_SECRET_{agent_id.upper()}"].encode()
    msg = f"{agent_id}|{task_id}|{tool}|{canonical(args)}|{ts}|{nonce}".encode()
    return {
        "agent_id": agent_id,
        "task_id": task_id,
        "tool": tool,
        "args": args,
        "ts": ts,
        "nonce": nonce,
        "signature": hmac.new(secret, msg, hashlib.sha256).hexdigest(),
    }


@pytest.fixture(scope="session")
def client():
    from app.main import app
    return TestClient(app)


@pytest.fixture
def admin():
    return {"X-Admin-Token": os.environ["ADMIN_TOKEN"]}


@pytest.fixture
def load_case(client, admin):
    def _load(case: int, mode: str = "scripted"):
        r = client.post("/demo/load", json={"case": case, "mode": mode}, headers=admin)
        assert r.status_code == 200 and r.json()["success"]
        return r.json()["data"]
    return _load


@pytest.fixture
def call(client):
    def _call(agent_id, task_id, tool, args, **kw):
        return client.post("/gw/call", json=sign_call(agent_id, task_id, tool, args, **kw))
    return _call

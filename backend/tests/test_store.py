"""Run store selection, the Supabase store (mocked client, no network) and the memory fallback."""

import json
import time
from unittest.mock import MagicMock

import pytest

from app.services import store as store_mod

URL = "https://example.supabase.co"
KEY = "sb_publishable_test"
JWT = "header.payload.signature"
AUTH = {"Authorization": f"Bearer {JWT}"}


@pytest.fixture
def supabase_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", KEY)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)


@pytest.fixture(autouse=True)
def _no_supabase_env(monkeypatch):
    for name in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "SUPABASE_ANON_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fake_client(monkeypatch):
    """Swaps the Supabase client factory; records (url, key, jwt), returns a MagicMock client."""
    client = MagicMock(name="supabase_client")
    seen: list[tuple[str, str, str]] = []

    def factory(url, key, jwt):
        seen.append((url, key, jwt))
        return client

    monkeypatch.setattr(store_mod, "_default_client_factory", factory)
    client.seen = seen
    return client


def _select_chain(client):
    """client.table(...).select(...).eq(...).maybe_single() on a MagicMock client."""
    return client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value


def _interrupted(data):
    return any(e["status"] == "interrupted" for e in data["events"])


# ---------- selection ----------


def test_no_env_uses_memory():
    assert store_mod.select_store(f"Bearer {JWT}") is store_mod.MEMORY


def test_env_without_jwt_uses_memory(supabase_env, fake_client):
    assert store_mod.select_store(None) is store_mod.MEMORY
    assert store_mod.select_store("Bearer ") is store_mod.MEMORY
    assert fake_client.seen == []


def test_non_bearer_scheme_is_not_treated_as_a_jwt(supabase_env, fake_client):
    assert store_mod.select_store(f"Basic {JWT}") is store_mod.MEMORY
    assert fake_client.seen == []


def test_env_and_jwt_use_supabase_with_that_jwt(supabase_env, fake_client):
    store = store_mod.select_store(f"Bearer {JWT}")
    assert isinstance(store, store_mod.SupabaseRunStore)
    assert fake_client.seen == [(URL, KEY, JWT)]


def test_legacy_anon_key_name_still_works(monkeypatch, fake_client):
    monkeypatch.setenv("SUPABASE_URL", URL)
    monkeypatch.setenv("SUPABASE_ANON_KEY", "legacy-anon")
    assert isinstance(store_mod.select_store(f"Bearer {JWT}"), store_mod.SupabaseRunStore)
    assert fake_client.seen == [(URL, "legacy-anon", JWT)]


def test_real_client_sends_user_jwt_and_publishable_key():
    """The real supabase-py client (no network) puts the user's JWT on every PostgREST request."""
    client = store_mod._default_client_factory(URL, KEY, JWT)
    headers = client.postgrest.session.headers
    assert headers["Authorization"] == f"Bearer {JWT}"
    assert headers["apikey"] == KEY


# ---------- SupabaseRunStore with a mocked client ----------


def test_supabase_store_insert_update_select():
    client = MagicMock()
    _select_chain(client).execute.return_value.data = {"id": "r1", "status": "finished"}
    store = store_mod.SupabaseRunStore(URL, KEY, JWT, client_factory=lambda *_: client)

    store.create("r1", "hello")
    client.table.assert_called_with("runs")
    client.table.return_value.insert.assert_called_once_with(
        {"id": "r1", "input": "hello", "status": "pending"}
    )

    store.update("r1", status="finished", output={"result": "ok"})
    client.table.return_value.update.assert_called_once_with(
        {"status": "finished", "output": {"result": "ok"}}
    )
    client.table.return_value.update.return_value.eq.assert_called_once_with("id", "r1")

    assert store.get("r1") == {"id": "r1", "status": "finished"}
    client.table.return_value.select.return_value.eq.assert_called_with("id", "r1")


def test_supabase_store_get_missing_row_returns_none():
    client = MagicMock()
    _select_chain(client).execute.return_value = None
    store = store_mod.SupabaseRunStore(URL, KEY, JWT, client_factory=lambda *_: client)
    assert store.get("nope") is None


def test_memory_store_roundtrip():
    s = store_mod.MemoryRunStore()
    s.create("r1", "hi")
    s.update("r1", status="interrupted")
    s.update("r1", status="finished", output={"result": "done"})
    expected = {"id": "r1", "input": "hi", "status": "finished", "output": {"result": "done"}}
    assert s.get("r1") == expected
    assert s.get("missing") is None


# ---------- API wiring (same envelope, no new routes) ----------


def _wait_for(client, run_id, pred):
    for _ in range(100):
        data = client.get(f"/runs/{run_id}").json()["data"]
        if pred(data):
            return data
        time.sleep(0.05)
    raise AssertionError(f"timed out: {data}")


def test_signed_in_run_is_persisted_to_supabase(client, supabase_env, fake_client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    r = client.post("/runs", json={"input": "persist me"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["success"]
    run_id = r.json()["data"]["run_id"]
    _wait_for(client, run_id, _interrupted)

    assert fake_client.seen == [(URL, KEY, JWT)]
    table = fake_client.table.return_value
    table.insert.assert_called_once_with({"id": run_id, "input": "persist me", "status": "pending"})
    update_values = table.update.call_args.args[0]
    assert update_values["status"] == "interrupted"
    assert update_values["output"]["input"] == "persist me"


def test_supabase_error_falls_back_to_memory(client, supabase_env, fake_client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    insert = fake_client.table.return_value.insert.return_value
    insert.execute.side_effect = RuntimeError(f"boom {JWT}")
    r = client.post("/runs", json={"input": "x"}, headers=AUTH)
    assert r.status_code == 200 and r.json()["success"]
    run_id = r.json()["data"]["run_id"]

    data = _wait_for(client, run_id, _interrupted)
    store_events = [e for e in data["events"] if e["node"] == "store"]
    assert store_events and store_events[0]["status"] == "memory (supabase unavailable)"
    assert store_events[0]["error"] == "RuntimeError"
    assert JWT not in json.dumps(data), "the JWT must never appear in trace events"
    assert store_mod.MEMORY.get(run_id)["status"] == "interrupted"


def test_anonymous_run_stays_in_memory(client, supabase_env, fake_client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    run_id = client.post("/runs", json={"input": "anon"}).json()["data"]["run_id"]
    _wait_for(client, run_id, _interrupted)
    assert fake_client.seen == []
    assert store_mod.MEMORY.get(run_id)["input"] == "anon"


def test_get_run_reads_persisted_state_for_signed_in_caller(client, supabase_env, fake_client):
    _select_chain(fake_client).execute.return_value.data = {
        "id": "old-run",
        "output": {"result": "action executed"},
    }
    body = client.get("/runs/old-run", headers=AUTH).json()
    assert body == {
        "success": True,
        "data": {"events": [], "state": {"result": "action executed"}},
        "error": None,
    }

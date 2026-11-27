"""Router behaviour: fallback order, privacy mode, mock mode, TTL cache. All providers mocked."""

import pytest

from app.services import llm
from tests.conftest import rate_limit_error, timeout_error

MSG = [{"role": "user", "content": "hi"}]


def test_tier_order_default_and_privacy():
    assert llm.tier_order() == ("groq", "gemini", "local")
    assert llm.tier_order(privacy_mode=True) == ("local",)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes"])
def test_privacy_mode_env_accepts_truthy_values(monkeypatch, value):
    monkeypatch.setenv("PRIVACY_MODE", value)
    assert llm.tier_order() == ("local",)


def test_groq_answers_first(llm_mock):
    r = llm.chat(MSG)
    assert (r.tier, r.text) == ("groq", "groq ok")
    assert llm_mock.calls == ["groq"]


@pytest.mark.parametrize("error", [timeout_error, rate_limit_error], ids=["timeout", "429"])
def test_falls_back_to_gemini(llm_mock, error):
    llm_mock.behaviour["groq"] = error()
    r = llm.chat(MSG)
    assert r.tier == "gemini"
    assert llm_mock.calls == ["groq", "gemini"]


def test_falls_back_to_local_when_cloud_tiers_fail(llm_mock):
    llm_mock.behaviour.update(groq=rate_limit_error(), gemini=timeout_error())
    assert llm.chat(MSG).tier == "local"
    assert llm_mock.calls == ["groq", "gemini", "local"]


def test_privacy_mode_never_calls_cloud(llm_mock, monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "true")
    assert llm.chat(MSG).tier == "local"
    assert llm_mock.calls == ["local"]


def test_missing_keys_are_skipped_and_reported(llm_mock, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY")
    monkeypatch.delenv("GEMINI_API_KEY")
    llm_mock.behaviour["local"] = timeout_error()
    with pytest.raises(llm.AllTiersFailed) as exc:
        llm.chat(MSG)
    msg = str(exc.value)
    assert "groq: no GROQ_API_KEY" in msg and "gemini: no GEMINI_API_KEY" in msg
    assert "local: APITimeoutError" in msg
    assert llm_mock.calls == ["local"]


def test_mock_mode_makes_no_provider_calls(llm_mock, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "1")
    r = llm.chat(MSG)
    assert r.tier == "mock" and r.text.startswith("[mock]")
    assert llm_mock.calls == []


def test_identical_calls_are_cached(llm_mock):
    llm.chat([{"role": "user", "content": "same  question "}])
    r = llm.chat([{"role": "user", "content": "same question"}])  # whitespace-normalised key
    assert r.text == "groq ok"
    assert llm_mock.calls == ["groq"]


def test_cache_can_be_disabled(llm_mock, monkeypatch):
    monkeypatch.setenv("LLM_CACHE_TTL", "0")
    llm.chat(MSG)
    llm.chat(MSG)
    assert llm_mock.calls == ["groq", "groq"]


def test_failures_are_not_cached(llm_mock):
    llm_mock.behaviour.update(groq=timeout_error(), gemini=timeout_error(), local=timeout_error())
    with pytest.raises(llm.AllTiersFailed):
        llm.chat(MSG)
    llm_mock.behaviour.clear()
    assert llm.chat(MSG).tier == "groq"

"""Shared fixtures. No test may reach a real model provider: env keys are cleared and `llm_mock`
replaces the OpenAI client factory with a scripted fake."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace

import httpx
import openai
import pytest
from fastapi.testclient import TestClient

from app.services import llm

_PROVIDER_ENV = ("GROQ_API_KEY", "GEMINI_API_KEY", "VLLM_API_KEY", "PRIVACY_MODE", "LLM_MOCK")


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    for name in _PROVIDER_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("VLLM_BASE_URL", "http://127.0.0.1:9/v1")  # unroutable if ever reached
    llm.cache_clear()
    yield
    llm.cache_clear()


@pytest.fixture
def client():
    from app.main import app, limiter

    limiter.reset()
    with TestClient(app) as c:
        yield c
    limiter.reset()


def timeout_error() -> openai.APITimeoutError:
    return openai.APITimeoutError(request=httpx.Request("POST", "https://test.invalid"))


def rate_limit_error() -> openai.RateLimitError:
    req = httpx.Request("POST", "https://test.invalid")
    return openai.RateLimitError("429", response=httpx.Response(429, request=req), body=None)


@dataclass
class FakeLLM:
    """Scripted stand-in for provider clients: `behaviour[tier]` is reply text or an exception."""

    behaviour: dict[str, object] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def _tier_for(self, base_url: str) -> str:
        for name, tier in llm._tiers().items():
            if tier.base_url == base_url:
                return name
        raise AssertionError(f"unexpected base_url {base_url}")

    def factory(self, base_url: str, key: str, timeout: float):
        tier = self._tier_for(base_url)

        def create(**_kwargs):
            self.calls.append(tier)
            outcome = self.behaviour.get(tier, f"{tier} ok")
            if isinstance(outcome, Exception):
                raise outcome
            message = SimpleNamespace(content=outcome, tool_calls=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


@pytest.fixture
def llm_mock(monkeypatch) -> FakeLLM:
    fake = FakeLLM()
    monkeypatch.setattr(llm, "_client", fake.factory)
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    return fake

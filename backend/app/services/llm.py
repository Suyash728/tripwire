"""3-tier LLM router. EVERY model call in this repo goes through `chat()`.

Tier 1 Groq (3 s timeout) -> on 429/timeout/error -> Tier 2 Gemini Flash-Lite
-> on failure, no network, or privacy_mode -> Tier 3 local vLLM.
All three speak the OpenAI chat format, so one client class covers them.

Env switches:
  PRIVACY_MODE=1|true  local tier only        LLM_MOCK=1|true  canned replies, no network (tests/CI)
  LLM_CACHE_TTL=300    seconds to cache identical calls (0 disables)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from functools import cache

from openai import OpenAI, OpenAIError

_TRUE = {"1", "true", "yes", "on"}


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in _TRUE


@dataclass(frozen=True)
class Tier:
    name: str
    base_url: str
    key_env: str
    model: str
    timeout: float


def _tiers() -> dict[str, Tier]:
    e = os.environ.get
    return {
        "groq": Tier(
            "groq",
            "https://api.groq.com/openai/v1",
            "GROQ_API_KEY",
            e("GROQ_MODEL", "openai/gpt-oss-120b"),
            float(e("GROQ_TIMEOUT", "3")),
        ),
        "gemini": Tier(
            "gemini",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            "GEMINI_API_KEY",
            e("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            20.0,
        ),
        # vLLM on this desktop listens on :8001 (SGLang owns :8000).
        "local": Tier(
            "local",
            e("VLLM_BASE_URL", "http://localhost:8001/v1"),
            "VLLM_API_KEY",
            e("VLLM_MODEL", "nvidia/Qwen3-14B-NVFP4"),
            120.0,
        ),
    }


# Hero call only (20 req/day free): pass model=HERO_MODEL with tiers=("gemini",).
HERO_MODEL = os.environ.get("GEMINI_HERO_MODEL", "gemini-3.8-flash")


@cache
def _client(base_url: str, key: str, timeout: float) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=key, timeout=timeout, max_retries=0)


@dataclass
class LLMResult:
    text: str
    tier: str
    model: str
    ms: int
    message: object = None  # raw message (tool_calls etc.)


class AllTiersFailed(RuntimeError):
    pass


def tier_order(privacy_mode: bool = False) -> tuple[str, ...]:
    if privacy_mode or env_flag("PRIVACY_MODE"):
        return ("local",)
    return ("groq", "gemini", "local")


# ---------- TTL cache (identical calls within LLM_CACHE_TTL seconds reuse the answer) ----------
_CACHE_MAX = 256
_cache: OrderedDict[str, tuple[float, LLMResult]] = OrderedDict()
_cache_lock = threading.Lock()


def _cache_key(
    messages: list[dict], order: tuple[str, ...], model: str | None, kwargs: dict
) -> str:
    norm = [{**m, "content": " ".join(str(m.get("content", "")).split())} for m in messages]
    blob = json.dumps([norm, order, model, kwargs], sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def _cache_get(key: str) -> LLMResult | None:
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        expires, result = hit
        if expires < time.monotonic():
            del _cache[key]
            return None
        _cache.move_to_end(key)
        return result


def _cache_put(key: str, result: LLMResult, ttl: float) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic() + ttl, result)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


def cache_clear() -> None:
    with _cache_lock:
        _cache.clear()


def chat(
    messages: list[dict],
    *,
    privacy_mode: bool = False,
    tiers: tuple[str, ...] | None = None,
    model: str | None = None,
    **kwargs,
) -> LLMResult:
    """Return the first successful completion. kwargs pass through (tools, temperature...)."""
    if env_flag("LLM_MOCK"):
        last = str(messages[-1].get("content", "")) if messages else ""
        return LLMResult(f"[mock] {last[:80]}", "mock", "mock", 0)

    order = tiers or tier_order(privacy_mode)
    ttl = float(os.environ.get("LLM_CACHE_TTL", "300"))
    key = _cache_key(messages, order, model, kwargs) if ttl > 0 else ""
    if key and (hit := _cache_get(key)) is not None:
        return hit

    errors: list[str] = []
    all_tiers = _tiers()
    for name in order:
        t = all_tiers[name]
        api_key = os.environ.get(t.key_env) or ("EMPTY" if name == "local" else "")
        if not api_key:
            errors.append(f"{name}: no {t.key_env}")
            continue
        call_kwargs = dict(kwargs)
        if name == "local" and not env_flag("LOCAL_THINKING"):
            # Qwen3 thinks by default (~10 s/call); off = demo-speed answers.
            call_kwargs.setdefault(
                "extra_body", {"chat_template_kwargs": {"enable_thinking": False}}
            )
        start = time.perf_counter()
        try:
            resp = _client(t.base_url, api_key, t.timeout).chat.completions.create(
                model=model or t.model, messages=messages, **call_kwargs
            )
        except OpenAIError as exc:  # 429, timeout, DNS, refused, 5xx -> next tier
            errors.append(f"{name}: {type(exc).__name__}: {exc}"[:200])
            continue
        msg = resp.choices[0].message
        result = LLMResult(
            msg.content or "",
            name,
            model or t.model,
            int((time.perf_counter() - start) * 1000),
            msg,
        )
        if key:
            _cache_put(key, result, ttl)
        return result
    raise AllTiersFailed("; ".join(errors))

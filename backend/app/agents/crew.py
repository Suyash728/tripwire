"""Optional CrewAI crew (install with `uv sync --extra crew`). Use ONLY when distinct
roles are the demo story. Wrapped as one function so a LangGraph node or a route calls it.

LLM selection mirrors services/llm.py: Groq if GROQ_API_KEY is set and privacy mode is
off, otherwise the local vLLM tier.
"""

from __future__ import annotations

import os
import time


def _llm(privacy_mode: bool):
    from crewai import LLM

    if os.environ.get("GROQ_API_KEY") and not privacy_mode:
        return LLM(model="groq/openai/gpt-oss-20b", temperature=0.2)
    return LLM(
        model="hosted_vllm/" + os.environ.get("VLLM_MODEL", "nvidia/Qwen3-14B-NVFP4"),
        base_url=os.environ.get("VLLM_BASE_URL", "http://localhost:8001/v1"),
        api_key="EMPTY",
        temperature=0.2,
        max_tokens=512,
        context_window_size=int(os.environ.get("VLLM_CONTEXT", "12288")),
        # Qwen3 thinking off: faster, and no <think> text in crew output.
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def run_crew(topic: str, privacy_mode: bool = False) -> dict:
    from crewai import Agent, Crew, Process, Task

    llm = _llm(privacy_mode)
    analyst = Agent(
        role="Analyst",
        goal="Extract the 3 key facts",
        llm=llm,
        max_iter=2,
        backstory="Terse domain analyst.",
        verbose=False,
    )
    critic = Agent(
        role="Critic",
        goal="Find the single biggest flaw",
        llm=llm,
        max_iter=2,
        backstory="Skeptical reviewer.",
        verbose=False,
    )
    t1 = Task(
        description=f"Topic: {topic}. List 3 key facts.",
        agent=analyst,
        expected_output="3 bullet points",
    )
    t2 = Task(
        description="Critique the facts; name the biggest flaw in one sentence.",
        agent=critic,
        expected_output="one sentence",
        context=[t1],
    )
    t0 = time.perf_counter()
    out = Crew(agents=[analyst, critic], tasks=[t1, t2], process=Process.sequential).kickoff()
    return {
        "result": str(out),
        "seconds": round(time.perf_counter() - t0, 1),
        "tokens": getattr(out, "token_usage", None) and out.token_usage.total_tokens,
    }


if __name__ == "__main__":
    import sys

    print(run_crew(" ".join(sys.argv[1:]) or "solar microgrids in rural India", True))

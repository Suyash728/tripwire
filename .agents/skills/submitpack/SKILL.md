---
name: submitpack
description: Generate submission artefacts
argument-hint: "[video-minutes] [post]"
disable-model-invocation: true
---
Read AGENTS.md, openapi.yaml, agents/graph.md, docs/traceability.md and `git log --oneline`.
Never read .env; never print secrets. Grep the code to confirm every claim.

1. README.md sections:
   - Pitch (one line) and target user.
   - Gap table: existing alternatives | what they miss | what we do.
   - Mermaid architecture diagram (frontend -> FastAPI -> agent graph -> 3-tier LLM router).
   - Quickstart with exact commands; env var NAMES only.
   - Traceability: requirement ID | feature | test | status.
   - Quality evidence (keep what /harden wrote; refresh numbers).
   - Privacy Mode: what runs locally (Tier 3 vLLM) and what never leaves the machine.
   - Link to AI_DISCLOSURE.md.
2. Demo video script (${ARGUMENTS:-2} minutes) as a table: screen | voiceover.
3. 8 hardest judge Q&As with 2-sentence answers, including "How is this different from <closest competitor>?"
4. AI_DISCLOSURE.md: every tool, model, API and dataset actually used.
5. Only if asked ("post" in arguments): a build-in-public post draft (<= 120 words, one image idea, no secrets).

# AI Disclosure

| Category | Name | Used for |
|---|---|---|
| Coding assistant | Claude Code | scaffolding, slices, debugging |
| LLM (cloud) | Groq `openai/gpt-oss-120b` | agent reasoning, tool calls |
| LLM (cloud) | Google `gemini-3.5-flash-lite` / `gemini-3.8-flash` | fallback / long-context call |
| LLM (local) | `nvidia/Qwen3-14B-NVFP4` via vLLM | offline + Privacy Mode |
| Embeddings | <gemini-embedding-2 / BAAI/bge-m3> | retrieval |
| Frameworks | LangGraph <, CrewAI, n8n> | orchestration |
| APIs | <Tavily / Exa / ...> | research |
| Datasets | <name + link + licence> | demo data |

All code in this repository was written during the event window; see commit history.

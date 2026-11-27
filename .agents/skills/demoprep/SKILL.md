---
name: demoprep
description: Make the demo bulletproof
disable-model-invocation: true
---
Paste raw output for every command.

1. Seed data: backend/app/seed.py has 2-3 realistic cases; "Load sample case" works from a fresh browser profile.
2. Demo path: run the Playwright demo-path spec (`cd frontend && npx playwright test --grep @demo`).
   If none exists, use the demo-tester subagent to click the 90-second path and screenshot each step.
3. Privacy Mode run: `bash scripts/vllm-up.sh coding`, then `PRIVACY_MODE=true bash scripts/smoke_demo.sh --privacy`.
   Every trace event must show tier_used=local.
4. Cloud run: `bash scripts/smoke_demo.sh` with keys set; note which tier answered.
5. Deployed: `curl -fsS <render-url>/health`; open the Vercel URL; open the Supabase dashboard (free projects pause).
6. Print the online judging-day checklist:
   - Deployed URL + /health green 30 min before; Supabase project awake.
   - vLLM model loaded before the call; no model swaps during the demo.
   - OBS 1080p, one window shared, browser zoom 125%, notifications off, .env files closed.
   - Sample case loaded in a fresh tab; backup video on USB + phone + uploaded link.
   - Stable network + phone hotspot fallback; mic and camera tested.

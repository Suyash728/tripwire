# Supabase (optional persistence)

Without Supabase the template keeps runs in memory. With it, `POST /runs` from a **signed-in** user persists
to `public.runs` under Row Level Security (`backend/app/services/store.py`). No new API routes.

## Set up a project (per event)
1. Create a project at supabase.com; copy the URL and the **publishable** key (`sb_publishable_...`).
2. Link and push the migration (CLI v3; `npx supabase@3 ...` works without installing):
   ```bash
   supabase login
   supabase link --project-ref <project-ref>
   supabase db push --remote          # applies supabase/migrations/*_runs.sql
   ```
3. Set `SUPABASE_URL` and `SUPABASE_PUBLISHABLE_KEY` in the backend env (local `.env`, Render dashboard).
   Never use the secret / service_role key on request paths: it bypasses RLS.

## Test the RLS policies (local, needs Docker; not in CI)
```bash
supabase start            # first run pulls several GB of images
supabase test db          # runs supabase/tests/rls_runs.test.sql (pgTAP)
supabase stop
```
It checks that anon gets nothing, a user can't read/change another user's runs, and owners can.

## Passing the user JWT (left to each event)
The backend uses Supabase only when a request carries `Authorization: Bearer <access_token>`. In the
frontend, sign the user in with `@supabase/supabase-js`, then add the header to API calls:
`headers: { authorization: \`Bearer ${session.access_token}\` }`. CORS already allows it.
Anonymous calls keep working (in-memory). If Supabase errors, the run falls back to memory and the
trace shows `store: memory (supabase unavailable)`.

## Agents (per-event MCP)
`bash scripts/event-mcp.sh <project-ref> [--read-only]` adds the Supabase MCP (OAuth, feature-limited)
to Claude Code, Antigravity and opencode for this repo only. Use `--read-only` near real user data.

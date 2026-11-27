-- Agent runs, owned by the signed-in user. Written by backend/app/services/store.py (SupabaseRunStore)
-- with the caller's JWT, so every statement below runs under Row Level Security.

create table public.runs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users on delete cascade,
  input text not null check (char_length(input) <= 4000),
  output jsonb,
  status text not null default 'pending',
  created_at timestamptz not null default now()
);

create index runs_user_id_created_at_idx on public.runs (user_id, created_at desc);

alter table public.runs enable row level security;

-- Grants: signed-out visitors (anon) get nothing; signed-in users get CRUD, filtered by the policies below.
revoke all on table public.runs from anon, authenticated;
grant select, insert, update, delete on table public.runs to authenticated;

-- Owner-only policies. `(select auth.uid())` is evaluated once per statement (initPlan), per Supabase's
-- RLS performance guidance. No policy targets anon.
create policy "runs_select_own" on public.runs
  for select to authenticated
  using ((select auth.uid()) = user_id);

create policy "runs_insert_own" on public.runs
  for insert to authenticated
  with check ((select auth.uid()) = user_id);

create policy "runs_update_own" on public.runs
  for update to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy "runs_delete_own" on public.runs
  for delete to authenticated
  using ((select auth.uid()) = user_id);

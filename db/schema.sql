-- Tripwire schema for Supabase Postgres. Apply as a migration. Table names are a contract.
-- Synthetic data only. Payments are mocked.

create table if not exists agents (
  id text primary key,
  name text not null,
  status text not null default 'active' check (status in ('active', 'quarantined')),
  policy jsonb not null default '{}'::jsonb
);

create table if not exists tickets (
  id text primary key,
  customer_id text not null,
  body text not null,
  replied boolean not null default false,
  version integer not null default 1,
  created_at timestamptz not null default now()
);

create table if not exists orders (
  id text primary key,
  customer_id text not null,
  sku text not null,
  qty integer not null default 1,
  amount_inr integer not null check (amount_inr >= 0),
  version integer not null default 1
);

create table if not exists refunds (
  id text primary key,
  order_id text not null references orders (id),
  amount_inr integer not null check (amount_inr >= 0),
  status text not null default 'issued' check (status in ('issued', 'reversed')),
  issued_by text not null,
  task_id text not null,
  version integer not null default 1
);

create table if not exists finance_entries (
  id text primary key,
  ref_id text not null,
  entry_type text not null check (entry_type in ('refund_booking', 'settlement')),
  amount_inr integer not null,
  status text not null default 'booked' check (status in ('booked', 'void')),
  version integer not null default 1
);

create table if not exists inventory (
  sku text primary key,
  qty integer not null check (qty >= 0),
  version integer not null default 1
);

create table if not exists canaries (
  record text primary key,   -- for example 'orders:CANARY-0001'
  note text
);

-- Append-only ledger. idx is assigned by the gateway under an advisory lock (gapless, starts at 1).
create table if not exists action_ledger (
  idx bigint primary key,
  ts timestamptz not null default now(),
  agent_id text not null,
  task_id text not null,
  tool text not null,
  kind text not null default 'action' check (kind in ('action', 'rollback')),
  decision text not null,
  rule_id text,
  args jsonb not null,
  before_image jsonb,
  after_image jsonb,
  reads jsonb not null default '[]'::jsonb,   -- [{record, version}]
  writes jsonb not null default '[]'::jsonb,  -- [{record, version}]
  rollback_of bigint references action_ledger (idx),
  prev_hash text not null,
  hash text not null
);

create index if not exists action_ledger_agent_ts on action_ledger (agent_id, ts);
create index if not exists action_ledger_task on action_ledger (task_id);

create table if not exists provenance_edges (
  id bigserial primary key,
  from_idx bigint not null references action_ledger (idx),  -- producer write
  to_idx bigint not null references action_ledger (idx),    -- dependent write
  record text not null,
  version integer not null
);

create index if not exists provenance_from on provenance_edges (from_idx);
create index if not exists provenance_to on provenance_edges (to_idx);

create table if not exists incidents (
  id text primary key,
  agent_id text not null,
  task_id text not null,
  trip_rule_id text not null,
  trip_ledger_idx bigint not null references action_ledger (idx),
  first_malicious_ts timestamptz not null,
  tripped_at timestamptz not null,
  containment_ms numeric not null,
  status text not null default 'open' check (status in ('open', 'rolled_back')),
  receipt jsonb
);

-- Block edits to the ledger (tamper-evident, not tamper-proof; see SECURITY.md).
create or replace function forbid_ledger_mutation() returns trigger
language plpgsql as $$
begin
  raise exception 'action_ledger is append-only';
end;
$$;

drop trigger if exists action_ledger_no_update on action_ledger;
create trigger action_ledger_no_update
  before update or delete on action_ledger
  for each row execute function forbid_ledger_mutation();

drop trigger if exists action_ledger_no_truncate on action_ledger;
create trigger action_ledger_no_truncate
  before truncate on action_ledger
  for each statement execute function forbid_ledger_mutation();

-- DEMO ONLY: edit a row to show that the hash chain turns red. Remove before any real use.
create or replace function demo_tamper_row(p_idx bigint) returns void
language plpgsql security definer as $$
begin
  alter table action_ledger disable trigger action_ledger_no_update;
  update action_ledger set args = jsonb_set(args, '{tampered}', 'true'::jsonb) where idx = p_idx;
  alter table action_ledger enable trigger action_ledger_no_update;
end;
$$;

revoke all on function demo_tamper_row(bigint) from public, anon, authenticated;

-- Row level security: the console (anon key) can read; only the gateway (service role) can write.
do $$
declare t text;
begin
  foreach t in array array[
    'agents', 'tickets', 'orders', 'refunds', 'finance_entries', 'inventory',
    'canaries', 'action_ledger', 'provenance_edges', 'incidents'
  ] loop
    execute format('alter table %I enable row level security', t);
    execute format('drop policy if exists console_read on %I', t);
    execute format('create policy console_read on %I for select to anon, authenticated using (true)', t);
  end loop;
end;
$$;

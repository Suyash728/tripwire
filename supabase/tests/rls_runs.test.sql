-- RLS tests for public.runs. Run locally: `supabase start` then `supabase test db` (needs Docker; not in CI).
-- Each file runs in one transaction that is rolled back, so test data never persists.
begin;
create extension if not exists pgtap with schema extensions;
select plan(12);

insert into auth.users (id, email) values
  ('11111111-1111-1111-1111-111111111111', 'a@example.com'),
  ('22222222-2222-2222-2222-222222222222', 'b@example.com');

-- Seed one row per user as the table owner (bypasses RLS).
insert into public.runs (id, user_id, input, status) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 'A input', 'pending'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', 'B input', 'pending');

-- anon: no grant, so every statement is refused before any policy runs.
set local role anon;
select throws_ok($$select * from public.runs$$, '42501', null, 'anon cannot read runs');
select throws_ok($$insert into public.runs (input) values ('x')$$, '42501', null, 'anon cannot create runs');

-- user A: sees and changes only their own row.
set local role authenticated;
set local request.jwt.claim.sub = '11111111-1111-1111-1111-111111111111';
select results_eq($$select input from public.runs$$, array['A input'], 'A sees only their own run');
select results_eq(
  $$insert into public.runs (input) values ('A second') returning user_id$$,
  array['11111111-1111-1111-1111-111111111111'::uuid],
  'A creates a run; user_id defaults to auth.uid()'
);
select throws_ok(
  $$insert into public.runs (input, user_id) values ('spoof', '22222222-2222-2222-2222-222222222222')$$,
  '42501', null, 'A cannot create a run owned by B'
);
select is_empty(
  $$select 1 from public.runs where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'$$,
  'A cannot read B''s run'
);
select is_empty(
  $$update public.runs set status = 'hacked' where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' returning 1$$,
  'A cannot update B''s run'
);
select is_empty(
  $$delete from public.runs where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb' returning 1$$,
  'A cannot delete B''s run'
);
select results_eq(
  $$update public.runs set status = 'finished' where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' returning status$$,
  array['finished'],
  'A updates their own run'
);

-- user B: their row survived A's denied writes.
set local request.jwt.claim.sub = '22222222-2222-2222-2222-222222222222';
select results_eq(
  $$select status from public.runs where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'$$,
  array['pending'],
  'B''s run is intact after A''s denied update and delete'
);
select results_eq($$select count(*) from public.runs$$, array[1::bigint], 'B sees only their own run');
select throws_ok(
  $$update public.runs set user_id = '11111111-1111-1111-1111-111111111111' where id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'$$,
  '42501', null, 'B cannot hand their run to A (with check on update)'
);

select * from finish();
rollback;

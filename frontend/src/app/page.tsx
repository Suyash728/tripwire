"use client";

import { useCallback, useEffect, useState } from "react";
import TracePanel, { type TraceEvent } from "@/components/TracePanel";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";
const INCIDENT_ID = "inc-1";

type ApiError = string | { code: string; message: string } | null;
type Envelope<T> = { success: boolean; data: T | null; error: ApiError };

type AgentId = "support" | "refund" | "inventory" | "finance";
type Agent = {
  id: AgentId;
  name: string;
  status: "active" | "quarantined";
  blocked_calls?: number;
};

type RecordVersion = { record: string; version: number };
type LedgerEntry = {
  idx: number;
  ts: string;
  agent_id: AgentId;
  task_id: string;
  tool: string;
  kind: "action" | "rollback";
  decision: string;
  rule_id?: string | null;
  args?: Record<string, unknown>;
  reads?: RecordVersion[];
  writes?: RecordVersion[];
  rollback_of?: number | null;
  prev_hash: string;
  hash: string;
};

type VerifyResult = {
  ok: boolean;
  first_broken_idx: number | null;
  head_hash: string;
  anchor_matches: boolean;
};

type BlastNode = { ledger_idx: number; agent_id: AgentId; tool: string; tainted: boolean };
type BlastRadius = {
  incident_id: string;
  nodes: BlastNode[];
  edges: { from: number; to: number }[];
  tainted_idx: number[];
  kept_idx: number[];
  naive_lost_count: number;
  tripwire_reversed_count: number;
  tripwire_kept_count: number;
};

type Receipt = {
  incident_id: string;
  agent_id: AgentId;
  tripped_at: string;
  trip_rule_id: string;
  containment_ms: number;
  reversed: { ledger_idx: number; tool: string; amount_inr: number | null }[];
  kept_count: number;
  blocked_calls: number;
  chain_ok: boolean;
  narrative?: string | null;
};

const FALLBACK_AGENTS: Agent[] = [
  { id: "support", name: "Support Agent", status: "active", blocked_calls: 0 },
  { id: "refund", name: "Refund Agent", status: "active", blocked_calls: 0 },
  { id: "inventory", name: "Inventory Agent", status: "active", blocked_calls: 0 },
  { id: "finance", name: "Finance Agent", status: "active", blocked_calls: 0 },
];

const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN ?? "";

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (ADMIN_TOKEN && !headers.has("x-admin-token")) {
    headers.set("x-admin-token", ADMIN_TOKEN);
  }
  const res = await fetch(`${API}${path}`, { ...init, headers });
  const body = (await res.json()) as Envelope<T>;
  if (!body.success) {
    const message = typeof body.error === "string" ? body.error : body.error?.message;
    throw new Error(message ?? `HTTP ${res.status}`);
  }
  return body.data as T;
}

const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

const errorText = (err: unknown): string => (err instanceof Error ? err.message : String(err));

const formatMs = (ms: number | undefined): string =>
  ms === undefined || !Number.isFinite(ms) ? "0 ms" : `${ms} ms`;

const cardClass = "rounded-lg border border-slate-300 bg-white p-4 shadow-sm";
const mutedClass = "text-sm text-slate-700";

export default function Home() {
  const [agents, setAgents] = useState<Agent[]>(FALLBACK_AGENTS);
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [verify, setVerify] = useState<VerifyResult | null>(null);
  const [blast, setBlast] = useState<BlastRadius | null>(null);
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [mode, setMode] = useState("SCRIPTED");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const run = useCallback(async (label: string, fn: () => Promise<void>) => {
    setError(null);
    setBusy(label);
    try {
      await fn();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }, []);

  const refreshAll = useCallback(async () => {
    const [agentList, ledger, chain, radius, incidentReceipt] = await Promise.all([
      api<{ agents: Agent[] }>("/agents"),
      api<{ entries: LedgerEntry[] }>("/ledger?limit=500"),
      api<VerifyResult>("/ledger/verify"),
      api<BlastRadius>(`/incidents/${INCIDENT_ID}/blast-radius`).catch(() => null),
      api<Receipt>(`/incidents/${INCIDENT_ID}/receipt`).catch(() => null),
    ]);
    if (agentList.agents.length > 0) setAgents(agentList.agents);
    setEntries(ledger.entries);
    setVerify(chain);
    setBlast(radius);
    setReceipt(incidentReceipt);
  }, []);

  useEffect(() => {
    // Initial REST snapshot: external data, not state derived in the effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refreshAll().catch((err: unknown) => setError(errorText(err)));
  }, [refreshAll]);

  useEffect(() => {
    if (typeof EventSource === "undefined") return;
    const source = new EventSource(`${API}/events`);
    source.onmessage = (message: MessageEvent<string>) => {
      let event: TraceEvent;
      try {
        event = JSON.parse(message.data) as TraceEvent;
      } catch {
        return;
      }
      setEvents((prev) => {
        const duplicate = prev.some(
          (existing) =>
            existing.ts === event.ts &&
            existing.agent === event.agent &&
            existing.tool === event.tool &&
            existing.decision === event.decision &&
            existing.ledger_idx === event.ledger_idx,
        );
        return duplicate ? prev : [...prev, event];
      });
    };
    return () => source.close();
  }, []);

  const loadSample = () =>
    run("Loading incident", async () => {
      const loaded = await api<{ case: number; mode: string }>("/demo/load", postJson({ case: 1 }));
      setMode(loaded.mode.toUpperCase());
      setEvents([]);
      await api("/demo/inject", postJson({ fault: "injection" }));
      await refreshAll();
    });

  const applyRollback = () =>
    run("Applying rollback", async () => {
      await api(`/incidents/${INCIDENT_ID}/rollback`, postJson({ mode: "apply" }));
      await refreshAll();
    });

  const injectFault = () =>
    run("Injecting fault", async () => {
      await api("/demo/inject", postJson({ fault: "injection" }));
      await refreshAll();
    });

  const tamperRow = () =>
    run("Tampering with a row", async () => {
      // The demo contract names this field `idx`; the API validates `ledger_idx`.
      await api("/demo/tamper", postJson({ idx: 1, ledger_idx: 1 }));
      const [chain, ledger] = await Promise.all([
        api<VerifyResult>("/ledger/verify"),
        api<{ entries: LedgerEntry[] }>("/ledger?limit=500"),
      ]);
      setVerify(chain);
      setEntries(ledger.entries);
      setReceipt((prev) => (prev === null ? prev : { ...prev, chain_ok: chain.ok }));
    });

  const buttonClass =
    "rounded border border-slate-400 bg-white px-3 py-2 text-sm font-medium text-slate-900 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-slate-900";

  const agentById = new Map(agents.map((agent) => [agent.id, agent]));
  const agentCards = FALLBACK_AGENTS.map((fallback) => agentById.get(fallback.id) ?? fallback);

  const rulesFor = (id: AgentId): string[] => {
    const rules: string[] = [];
    if (receipt !== null && receipt.agent_id === id && receipt.trip_rule_id) {
      rules.push(receipt.trip_rule_id);
    }
    for (const event of events) {
      if (event.agent === id && event.rule_id) rules.push(event.rule_id);
    }
    for (const entry of entries) {
      if (entry.agent_id === id && entry.rule_id) rules.push(entry.rule_id);
    }
    return Array.from(new Set(rules));
  };

  const chainValid = verify === null ? (receipt?.chain_ok ?? true) : verify.ok;
  const chainLabel = chainValid ? "verified" : "tampered";
  const taintedCount = blast === null ? 0 : blast.tainted_idx.length;
  const preservedCount = blast === null ? 0 : blast.tripwire_kept_count;

  return (
    <main
      aria-labelledby="page-title"
      className="mx-auto max-w-6xl space-y-6 p-4 text-slate-900 md:p-6"
    >
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-300 pb-4">
        <div>
          <h1 id="page-title" className="text-2xl font-bold">
            Tripwire Gateway Console
          </h1>
          <p className="mt-1 text-sm text-slate-700">
            Containment, selective rollback and proof for the four-agent demo network.
          </p>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-sm font-semibold text-amber-900">
          {mode}
        </span>
      </header>

      <section aria-labelledby="controls-title" className="space-y-3">
        <h2 id="controls-title" className="text-lg font-semibold">
          Demo controls
        </h2>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            aria-busy={busy === "Loading incident"}
            onClick={loadSample}
            className={buttonClass}
          >
            Load sample incident
          </button>
          <button
            type="button"
            aria-busy={busy === "Applying rollback"}
            onClick={applyRollback}
            className={buttonClass}
          >
            Apply rollback
          </button>
          <button
            type="button"
            aria-busy={busy === "Injecting fault"}
            onClick={injectFault}
            className={buttonClass}
          >
            Inject fault
          </button>
          <button
            type="button"
            aria-busy={busy === "Tampering with a row"}
            onClick={tamperRow}
            className={buttonClass}
          >
            Tamper with a row
          </button>
        </div>
        <div role="status" aria-live="polite" className="sr-only">
          {busy === null ? "" : `${busy}…`}
        </div>
        {error !== null && (
          <p
            role="alert"
            className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-900"
          >
            {error}
          </p>
        )}
      </section>

      <section aria-labelledby="status-title" className={`${cardClass} grid gap-4 sm:grid-cols-2`}>
        <h2 id="status-title" className="sr-only">
          Incident status
        </h2>
        <div data-testid="stopwatch">
          <p className="text-sm font-medium text-slate-700">Containment time</p>
          <p className="mt-1 text-3xl font-semibold tabular-nums">
            {formatMs(receipt?.containment_ms)}
          </p>
        </div>
        <div>
          <p className="text-sm font-medium text-slate-700">Ledger chain</p>
          <span
            data-testid="chain-status"
            className={`mt-1 inline-block rounded px-2 py-1 text-sm font-semibold ${
              chainValid ? "bg-emerald-100 text-emerald-900" : "bg-red-100 text-red-900"
            }`}
          >
            {chainLabel}
          </span>
          {verify !== null && verify.first_broken_idx !== null && (
            <p className="mt-1 text-sm text-slate-700">
              First broken index: {verify.first_broken_idx}
            </p>
          )}
        </div>
      </section>

      <section aria-labelledby="agents-title" className="space-y-3">
        <h2 id="agents-title" className="text-lg font-semibold">
          Agent network
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {agentCards.map((agent) => {
            const rules = rulesFor(agent.id);
            const quarantined = agent.status === "quarantined";
            return (
              <section
                key={agent.id}
                data-testid={`agent-${agent.id}`}
                aria-labelledby={`agent-${agent.id}-name`}
                className={cardClass}
              >
                <h3 id={`agent-${agent.id}-name`} className="font-semibold">
                  {agent.name}
                </h3>
                <p className={`mt-2 ${mutedClass}`}>
                  Status:{" "}
                  <span
                    className={`rounded px-2 py-0.5 font-semibold ${
                      quarantined ? "bg-red-100 text-red-900" : "bg-emerald-100 text-emerald-900"
                    }`}
                  >
                    {quarantined ? "quarantined" : "active"}
                  </span>
                </p>
                <p className={`mt-2 ${mutedClass}`}>
                  Tripped rules:{" "}
                  <span className="font-mono text-slate-900">
                    {rules.length > 0 ? rules.join(", ") : "none"}
                  </span>
                </p>
                <p className={`mt-1 ${mutedClass}`}>
                  Blocked calls:{" "}
                  <span className="font-semibold text-slate-900">{agent.blocked_calls ?? 0}</span>
                </p>
              </section>
            );
          })}
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section data-testid="blast-graph" aria-labelledby="blast-title" className={cardClass}>
          <h2 id="blast-title" className="text-lg font-semibold">
            Blast graph
          </h2>
          <p className="mt-2 text-sm text-slate-700">
            Incident data is scoped to <span className="font-mono">{INCIDENT_ID}</span>.
          </p>
          <div className="mt-3 flex flex-wrap gap-6">
            <p className="text-sm text-slate-700">
              <span className="mr-2 rounded bg-red-100 px-2 py-1 font-semibold text-red-900">
                {taintedCount}
              </span>
              tainted actions
            </p>
            <p className="text-sm text-slate-700">
              <span className="mr-2 rounded bg-emerald-100 px-2 py-1 font-semibold text-emerald-900">
                {preservedCount}
              </span>
              preserved actions
            </p>
          </div>
          <div className="mt-4 space-y-2">
            <h3 className="text-sm font-semibold">Nodes</h3>
            {blast !== null && blast.nodes.length > 0 ? (
              <ul className="max-h-72 space-y-1 overflow-y-auto">
                {blast.nodes.map((node) => (
                  <li
                    key={node.ledger_idx}
                    className="flex flex-wrap items-center justify-between gap-2 rounded bg-slate-100 px-2 py-1 text-sm text-slate-900"
                  >
                    <span className="font-mono">
                      #{node.ledger_idx} · {node.agent_id} · {node.tool}
                    </span>
                    <span
                      className={
                        node.tainted
                          ? "rounded bg-red-100 px-2 py-0.5 font-semibold text-red-900"
                          : "rounded bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-900"
                      }
                    >
                      {node.tainted ? "tainted" : "preserved"}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-700">
                No incident data yet. Load a sample incident.
              </p>
            )}
          </div>
        </section>

        <section aria-labelledby="compare-title" className={cardClass}>
          <h2 id="compare-title" className="text-lg font-semibold">
            Naive vs Tripwire
          </h2>
          <table
            data-testid="compare-table"
            className="mt-3 w-full border-collapse text-left text-sm"
          >
            <caption className="sr-only">
              Legit actions lost by a naive full rollback compared with actions kept by Tripwire
            </caption>
            <thead>
              <tr className="border-b border-slate-300">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Strategy
                </th>
                <th scope="col" className="py-2 font-semibold">
                  Legit actions
                </th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-slate-200">
                <th scope="row" className="py-2 pr-3 font-medium">
                  Naive rollback (naive_lost_count)
                </th>
                <td className="py-2 text-slate-800">{blast?.naive_lost_count ?? 0} lost</td>
              </tr>
              <tr>
                <th scope="row" className="py-2 pr-3 font-medium">
                  Tripwire selective (tripwire_kept_count)
                </th>
                <td className="py-2 text-slate-800">{blast?.tripwire_kept_count ?? 0} kept</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>

      <section data-testid="receipt" aria-labelledby="receipt-title" className={cardClass}>
        <h2 id="receipt-title" className="text-lg font-semibold">
          Incident receipt
        </h2>
        <dl className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="text-sm text-slate-700">Incident ID (incident_id)</dt>
            <dd className="mt-1 font-mono text-slate-900">{receipt?.incident_id ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-700">Trip rule (trip_rule_id)</dt>
            <dd className="mt-1 font-mono text-slate-900">{receipt?.trip_rule_id ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-700">Containment (containment_ms)</dt>
            <dd className="mt-1 font-mono text-slate-900">{formatMs(receipt?.containment_ms)}</dd>
          </div>
          <div>
            <dt className="text-sm text-slate-700">Chain OK (chain_ok)</dt>
            <dd className="mt-1 font-mono text-slate-900">
              {receipt === null ? "—" : String(receipt.chain_ok)}
            </dd>
          </div>
        </dl>
        {receipt !== null && receipt.narrative && (
          <p className="mt-3 text-sm text-slate-700">{receipt.narrative}</p>
        )}
      </section>

      <section aria-labelledby="ledger-title" className={cardClass}>
        <h2 id="ledger-title" className="text-lg font-semibold">
          Ledger live feed
        </h2>
        {entries.length === 0 ? (
          <p className="mt-2 text-sm text-slate-700">No ledger entries yet.</p>
        ) : (
          <ol className="mt-3 max-h-96 space-y-2 overflow-y-auto">
            {entries.map((entry) => (
              <li
                key={entry.idx}
                data-testid={`ledger-row-${entry.idx}`}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded bg-slate-100 px-2 py-1 text-sm text-slate-900"
              >
                <span className="font-mono font-semibold">#{entry.idx}</span>
                <span>{entry.agent_id}</span>
                <span className="font-mono">{entry.tool}</span>
                <span className="rounded bg-slate-200 px-2 py-0.5 font-semibold">
                  {entry.decision}
                </span>
                {entry.rule_id && <span className="font-mono">rule: {entry.rule_id}</span>}
                <span className="font-mono text-slate-700">{entry.hash.slice(0, 12)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <TracePanel events={events} />
    </main>
  );
}

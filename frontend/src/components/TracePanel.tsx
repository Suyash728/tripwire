"use client";

export type TraceEvent = {
  ts: string;
  agent: "support" | "refund" | "inventory" | "finance";
  tool: string;
  decision: "allow" | "deny" | "quarantined_deny" | "hold" | "quarantine" | "rollback";
  decider: "rule" | "canary" | "human";
  rule_id?: string | null;
  ms: number;
  ledger_idx: number;
  hash?: string;
};

const decisionClass: Record<TraceEvent["decision"], string> = {
  allow: "bg-emerald-100 text-emerald-900",
  deny: "bg-red-100 text-red-900",
  quarantined_deny: "bg-red-100 text-red-900",
  hold: "bg-amber-100 text-amber-900",
  quarantine: "bg-amber-100 text-amber-900",
  rollback: "bg-blue-100 text-blue-900",
};

function formatTime(ts: string): string {
  const date = new Date(ts);
  return Number.isNaN(date.getTime()) ? ts : date.toLocaleTimeString();
}

export default function TracePanel({ events }: { events: TraceEvent[] }) {
  return (
    <aside
      aria-labelledby="trace-title"
      className="w-full shrink-0 rounded-lg border border-slate-300 bg-white p-4 shadow-sm text-sm"
    >
      <h2 id="trace-title" className="mb-2 font-semibold text-slate-900">
        Agent trace
      </h2>
      {events.length === 0 && <p className="text-slate-700">No run yet.</p>}
      <ol
        aria-live="polite"
        aria-relevant="additions"
        className="max-h-96 space-y-1 overflow-y-auto"
      >
        {events.map((event, index) => (
          <li
            key={`${event.ts}-${event.ledger_idx}-${index}`}
            className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-slate-200 py-1 last:border-0"
          >
            <span className="font-mono text-slate-700">{formatTime(event.ts)}</span>
            <span className="font-semibold text-slate-900">{event.agent}</span>
            <span className="font-mono text-slate-900">{event.tool}</span>
            <span
              className={`rounded px-1.5 py-0.5 font-semibold ${decisionClass[event.decision]}`}
            >
              {event.decision}
            </span>
            <span className="text-slate-700">decider: {event.decider}</span>
            {event.rule_id && <span className="font-mono text-slate-900">{event.rule_id}</span>}
            <span className="ml-auto text-slate-700">{event.ms} ms</span>
          </li>
        ))}
      </ol>
    </aside>
  );
}

"use client";

export type TraceEvent = {
  node: string;
  status: string;
  tier_used: string | null;
  ms: number;
  tool?: string;
  error?: string;
};

const tierColor: Record<string, string> = {
  groq: "bg-orange-100 text-orange-800",
  gemini: "bg-blue-100 text-blue-800",
  local: "bg-green-100 text-green-800",
};

export default function TracePanel({ events }: { events: TraceEvent[] }) {
  return (
    <aside
      aria-labelledby="trace-title"
      className="w-full shrink-0 rounded-lg border p-3 text-sm md:w-80"
    >
      <h2 id="trace-title" className="mb-2 font-semibold">
        Agent trace
      </h2>
      {events.length === 0 && <p className="text-gray-600">No run yet.</p>}
      <ol aria-live="polite" aria-relevant="additions" className="space-y-1 font-mono">
        {events.map((e, i) => (
          <li key={i} className="flex items-center gap-2">
            <span className="w-20 truncate">{e.node}</span>
            <span className={e.status === "error" ? "text-red-700" : "text-gray-700"}>
              {e.status}
            </span>
            {e.tool && <span className="text-purple-700">{e.tool}</span>}
            {e.tier_used && (
              <span className={`rounded px-1 ${tierColor[e.tier_used] ?? "bg-gray-100"}`}>
                {e.tier_used}
              </span>
            )}
            {e.ms > 0 && <span className="ml-auto text-gray-600">{e.ms} ms</span>}
            {e.error && <span className="sr-only">: {e.error}</span>}
          </li>
        ))}
      </ol>
    </aside>
  );
}

"use client";

import { useRef, useState } from "react";
import TracePanel, { type TraceEvent } from "@/components/TracePanel";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8787";

type Envelope<T> = { success: boolean; data: T | null; error: string | null };
type Sample = { id: string; title: string; input: string };

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  const body = (await res.json()) as Envelope<T>;
  if (!body.success || body.data === null) throw new Error(body.error ?? `HTTP ${res.status}`);
  return body.data;
}

const postJson = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

export default function Home() {
  const [input, setInput] = useState("");
  const [privacy, setPrivacy] = useState(false);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [runId, setRunId] = useState<string | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const es = useRef<EventSource | null>(null);

  async function guarded(fn: () => Promise<void>) {
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const loadSample = () =>
    guarded(async () => {
      const samples = await api<Sample[]>("/samples");
      if (samples[0]) setInput(samples[0].input);
    });

  function listen(id: string) {
    es.current?.close();
    const src = new EventSource(`${API}/runs/${id}/events`);
    src.onmessage = (m) => {
      const ev: TraceEvent & { result?: string } = JSON.parse(m.data);
      setEvents((prev) => [...prev, ev]);
      if (ev.node === "approval" && ev.status === "waiting") setWaiting(true);
      if (ev.result) setResult(ev.result);
    };
    src.addEventListener("end", () => src.close());
    es.current = src;
  }

  const run = () =>
    guarded(async () => {
      setEvents([]);
      setResult(null);
      setWaiting(false);
      const { run_id } = await api<{ run_id: string }>(
        "/runs",
        postJson({ input, privacy_mode: privacy }),
      );
      setRunId(run_id);
      listen(run_id);
    });

  const decide = (approve: boolean) =>
    guarded(async () => {
      setWaiting(false);
      await api<{ run_id: string }>(`/runs/${runId}/resume`, postJson({ approve }));
    });

  return (
    <main
      aria-labelledby="page-title"
      className="mx-auto flex max-w-5xl flex-col gap-4 p-4 md:flex-row"
    >
      <section className="flex-1 space-y-3">
        <h1 id="page-title" className="text-2xl font-bold">
          Hackathon starter
        </h1>
        <label htmlFor="case-input" className="block text-sm font-medium">
          Case description
        </label>
        <textarea
          id="case-input"
          className="h-32 w-full rounded border p-2"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe the case..."
          maxLength={4000}
        />
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className="rounded border px-3 py-1" onClick={loadSample}>
            Load sample case
          </button>
          <button
            type="button"
            className="rounded bg-black px-3 py-1 text-white disabled:opacity-40"
            onClick={run}
            disabled={!input.trim()}
          >
            Run agent
          </button>
          <label className="flex items-center gap-1 text-sm">
            <input
              type="checkbox"
              checked={privacy}
              onChange={(e) => setPrivacy(e.target.checked)}
            />
            Privacy Mode (local GPU only)
          </label>
        </div>
        {error && (
          <p role="alert" className="rounded border border-red-300 bg-red-50 p-3 text-red-800">
            {error}
          </p>
        )}
        {waiting && (
          <div
            role="group"
            aria-labelledby="approval-q"
            className="rounded border border-amber-400 bg-amber-50 p-3"
          >
            <p id="approval-q" className="mb-2 font-medium">
              The agent wants to act. Approve?
            </p>
            <button
              type="button"
              className="mr-2 rounded bg-green-700 px-3 py-1 text-white"
              onClick={() => decide(true)}
            >
              Approve
            </button>
            <button
              type="button"
              className="rounded bg-red-700 px-3 py-1 text-white"
              onClick={() => decide(false)}
            >
              Reject
            </button>
          </div>
        )}
        <div role="status" aria-live="polite">
          {result && <p className="rounded bg-gray-100 p-3">Result: {result}</p>}
        </div>
      </section>
      <TracePanel events={events} />
    </main>
  );
}

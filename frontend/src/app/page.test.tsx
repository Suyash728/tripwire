import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

afterEach(() => vi.unstubAllGlobals());

const envelope = (data: unknown, success = true, error: unknown = null) => ({
  success,
  data,
  error,
});

const response = (body: unknown, status = 200) => ({ status, json: async () => body });

type Override = { body: unknown; status?: number };

function stubApi(overrides: Record<string, Override> = {}) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    const match = Object.keys(overrides).find((key) => url.includes(key));
    if (match) return response(overrides[match].body, overrides[match].status ?? 200);

    if (url.includes("/agents")) return response(envelope({ agents: [] }));
    if (url.includes("/ledger/verify")) {
      return response(
        envelope({ ok: true, first_broken_idx: null, head_hash: "abc", anchor_matches: true }),
      );
    }
    if (url.includes("/ledger")) return response(envelope({ entries: [] }));
    if (url.includes("/blast-radius") || url.includes("/receipt")) {
      return response(envelope(null, false, { code: "not_found", message: "not found" }), 404);
    }
    if (url.includes("/demo/")) return response(envelope({ case: 1, mode: "scripted" }));
    if (url.includes("/rollback")) {
      return response(envelope({ mode: "apply", steps: [], applied: true, kept_count: 0 }));
    }
    return response(envelope(null));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const controls = ["Load sample incident", "Apply rollback", "Inject fault", "Tamper with a row"];

describe("Tripwire console", () => {
  it("renders the labelled main landmark, scripted badge and all console widgets", async () => {
    stubApi();
    render(<Home />);

    expect(screen.getByRole("main", { name: "Tripwire Gateway Console" })).toBeInTheDocument();
    expect(screen.getByText("SCRIPTED")).toBeVisible();
    for (const name of controls) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
    for (const id of ["support", "refund", "inventory", "finance"]) {
      expect(screen.getByTestId(`agent-${id}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("stopwatch")).toBeVisible();
    expect(screen.getByTestId("chain-status")).toBeVisible();
    expect(screen.getByTestId("blast-graph")).toBeVisible();
    expect(screen.getByTestId("compare-table")).toBeVisible();
    expect(screen.getByTestId("receipt")).toBeVisible();

    await waitFor(() => expect(screen.getByTestId("chain-status")).toHaveTextContent(/verified/i));
  });

  it("posts the exact payloads for all four demo actions", async () => {
    const fetchMock = stubApi();
    render(<Home />);

    await userEvent.click(screen.getByRole("button", { name: "Load sample incident" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/demo/load"),
        expect.objectContaining({ method: "POST", body: JSON.stringify({ case: 1 }) }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Apply rollback" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/incidents/inc-1/rollback"),
        expect.objectContaining({ method: "POST", body: JSON.stringify({ mode: "apply" }) }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Inject fault" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/demo/inject"),
        expect.objectContaining({ method: "POST", body: JSON.stringify({ fault: "injection" }) }),
      ),
    );

    await userEvent.click(screen.getByRole("button", { name: "Tamper with a row" }));
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/demo/tamper"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({ idx: 1, ledger_idx: 1 }),
        }),
      ),
    );
  });

  it("shows quarantined status, tripped rules and blocked calls from the API", async () => {
    stubApi({
      "/agents": {
        body: envelope({
          agents: [
            { id: "support", name: "Support Agent", status: "active", blocked_calls: 0 },
            { id: "refund", name: "Refund Agent", status: "quarantined", blocked_calls: 3 },
            { id: "inventory", name: "Inventory Agent", status: "active", blocked_calls: 0 },
            { id: "finance", name: "Finance Agent", status: "active", blocked_calls: 0 },
          ],
        }),
      },
      "/receipt": {
        body: envelope({
          incident_id: "inc-1",
          agent_id: "refund",
          tripped_at: "2026-11-28T10:00:00Z",
          trip_rule_id: "R-TASK",
          containment_ms: 12.5,
          reversed: [],
          kept_count: 37,
          blocked_calls: 3,
          chain_ok: true,
        }),
      },
    });
    render(<Home />);

    await waitFor(() =>
      expect(screen.getByTestId("agent-refund")).toHaveTextContent(/quarantined/i),
    );
    const refund = screen.getByTestId("agent-refund");
    expect(refund).toHaveTextContent(/R-TASK/);
    expect(refund).toHaveTextContent(/Blocked calls: 3/);
    expect(screen.getByTestId("agent-support")).toHaveTextContent(/active/i);
    expect(screen.getByTestId("stopwatch")).toHaveTextContent(/12\.5 ms/);
  });

  it("shows an alert when an API call fails", async () => {
    stubApi({
      "/demo/load": {
        body: envelope(null, false, { code: "rate_limit", message: "rate limit exceeded" }),
        status: 429,
      },
    });
    render(<Home />);

    await userEvent.click(screen.getByRole("button", { name: "Load sample incident" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("rate limit exceeded");
  });

  it("reports a broken chain after tampering", async () => {
    const fetchMock = stubApi();
    let verifyOk = true;
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/demo/tamper")) return response(envelope(null));
      if (url.includes("/ledger/verify")) {
        return response(
          envelope({
            ok: verifyOk,
            first_broken_idx: verifyOk ? null : 1,
            head_hash: "x",
            anchor_matches: verifyOk,
          }),
        );
      }
      if (url.includes("/agents")) return response(envelope({ agents: [] }));
      if (url.includes("/ledger")) return response(envelope({ entries: [] }));
      if (url.includes("/blast-radius") || url.includes("/receipt")) {
        return response(envelope(null, false, { code: "not_found", message: "not found" }), 404);
      }
      return response(envelope(null));
    });

    render(<Home />);
    await waitFor(() => expect(screen.getByTestId("chain-status")).toHaveTextContent(/verified/i));

    verifyOk = false;
    await userEvent.click(screen.getByRole("button", { name: "Tamper with a row" }));
    await waitFor(() =>
      expect(screen.getByTestId("chain-status")).toHaveTextContent(/tampered|broken/i),
    );
  });
});

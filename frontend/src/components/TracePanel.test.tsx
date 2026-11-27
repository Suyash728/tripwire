import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TracePanel, { type TraceEvent } from "./TracePanel";

describe("TracePanel", () => {
  it("shows an empty state inside a labelled complementary landmark", () => {
    render(<TracePanel events={[]} />);
    const panel = screen.getByRole("complementary", { name: "Agent trace" });
    expect(within(panel).getByText("No run yet.")).toBeInTheDocument();
  });

  it("renders one live list item per trace event with rule, decider and timing", () => {
    const events: TraceEvent[] = [
      {
        ts: "2026-11-28T10:00:00Z",
        agent: "refund",
        tool: "refund.issue",
        decision: "quarantined_deny",
        decider: "rule",
        rule_id: "R-TASK",
        ms: 4,
        ledger_idx: 7,
      },
      {
        ts: "2026-11-28T10:00:01Z",
        agent: "support",
        tool: "ticket.reply",
        decision: "allow",
        decider: "rule",
        rule_id: null,
        ms: 12,
        ledger_idx: 8,
      },
    ];
    render(<TracePanel events={events} />);

    const list = screen.getByRole("list");
    expect(list).toHaveAttribute("aria-live", "polite");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(/refund.*refund\.issue.*quarantined_deny.*R-TASK/);
    expect(items[0]).toHaveTextContent(/decider: rule/);
    expect(items[1]).toHaveTextContent(/allow.*12 ms/);
  });
});

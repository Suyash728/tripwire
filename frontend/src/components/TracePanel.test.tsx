import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TracePanel, { type TraceEvent } from "./TracePanel";

describe("TracePanel", () => {
  it("shows an empty state inside a labelled complementary landmark", () => {
    render(<TracePanel events={[]} />);
    const panel = screen.getByRole("complementary", { name: "Agent trace" });
    expect(within(panel).getByText("No run yet.")).toBeInTheDocument();
  });

  it("renders one live list item per event with tier and timing", () => {
    const events: TraceEvent[] = [
      { node: "planner", status: "done", tier_used: "groq", ms: 120 },
      { node: "graph", status: "error", tier_used: null, ms: 0, error: "all tiers failed" },
    ];
    render(<TracePanel events={events} />);
    const list = screen.getByRole("list");
    expect(list).toHaveAttribute("aria-live", "polite");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent(/planner.*done.*groq.*120 ms/);
    expect(items[1]).toHaveTextContent("all tiers failed");
  });
});

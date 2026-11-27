import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Home from "./page";

afterEach(() => vi.unstubAllGlobals());

describe("Home page", () => {
  it("has a labelled main landmark and a labelled case input", () => {
    render(<Home />);
    expect(screen.getByRole("main", { name: "Hackathon starter" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Case description" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run agent" })).toBeDisabled();
  });

  it("loads the sample case into the input", async () => {
    const sample = { id: "c1", title: "Case", input: "Leaf curl on tomatoes" };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 200,
        json: async () => ({ success: true, data: [sample], error: null }),
      }),
    );
    render(<Home />);
    await userEvent.click(screen.getByRole("button", { name: "Load sample case" }));
    expect(await screen.findByDisplayValue(sample.input)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run agent" })).toBeEnabled();
  });

  it("shows API errors in an alert instead of failing silently", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        status: 429,
        json: async () => ({ success: false, data: null, error: "rate limit exceeded" }),
      }),
    );
    render(<Home />);
    await userEvent.click(screen.getByRole("button", { name: "Load sample case" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("rate limit exceeded");
  });
});

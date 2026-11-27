import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function expectNoSeriousA11yViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  const blocking = violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.impact}: ${v.id} (${v.nodes.length}) ${v.helpUrl}`);
  expect(blocking, blocking.join("\n")).toEqual([]);
}

test("console loads with labelled landmarks and no serious accessibility issues", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Tripwire Gateway Console" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tripwire Gateway Console" })).toBeVisible();
  await expect(page.getByText("SCRIPTED")).toBeVisible();
  await expect(page.getByRole("button", { name: "Load sample incident" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Agent trace" })).toBeVisible();
  await expectNoSeriousA11yViolations(page);

  await page.getByRole("button", { name: "Load sample incident" }).click();
  await expect(page.getByTestId("chain-status")).toContainText(/ok|verified/i);
  await expectNoSeriousA11yViolations(page);
});

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

test("demo path: load sample, run agent, approve, see result — axe clean", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("main", { name: "Hackathon starter" })).toBeVisible();
  await expectNoSeriousA11yViolations(page);

  const loadSample = page.getByRole("button", { name: "Load sample case" });
  if (await loadSample.isVisible()) {
    await loadSample.click();
    await expect(page.getByRole("textbox", { name: "Case description" })).not.toHaveValue("");
  } else {
    await page.getByRole("textbox", { name: "Case description" }).fill("Demo input");
  }

  await page.getByRole("button", { name: "Run agent" }).click();
  const approve = page.getByRole("button", { name: "Approve" });
  await expect(approve).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("complementary", { name: "Agent trace" })).toContainText("planner");
  await expectNoSeriousA11yViolations(page);

  await approve.click();
  await expect(page.getByRole("status")).toContainText("action executed", { timeout: 20_000 });
  await expectNoSeriousA11yViolations(page);
});

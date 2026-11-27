import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

// Demo path. Test IDs are a contract (see AGENTS.md).
test('load incident, quarantine, rollback, receipt, tamper', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Load sample incident' }).click();
  await expect(page.getByTestId('agent-refund')).toContainText(/quarantined/i, { timeout: 15_000 });
  await expect(page.getByTestId('agent-support')).toContainText(/active/i);
  await expect(page.getByTestId('stopwatch')).toBeVisible();

  await page.getByRole('button', { name: 'Apply rollback' }).click();
  await expect(page.getByTestId('receipt')).toBeVisible();
  await expect(page.getByTestId('compare-table')).toBeVisible();
  await expect(page.getByTestId('chain-status')).toContainText(/ok|verified/i);

  const results = await new AxeBuilder({ page }).analyze();
  const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical');
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

  await page.getByRole('button', { name: 'Tamper with a row' }).click();
  await expect(page.getByTestId('chain-status')).toContainText(/broken|tampered/i);
});

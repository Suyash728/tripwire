import { defineConfig, devices } from "@playwright/test";

// Dedicated ports so e2e never reuses a dev server that has real LLM keys loaded.
const API_PORT = Number(process.env.E2E_API_PORT ?? 8788);
const UI_PORT = Number(process.env.E2E_UI_PORT ?? 3100);
const API_URL = `http://localhost:${API_PORT}`;
const UI_URL = `http://localhost:${UI_PORT}`;
const CI = !!process.env.CI;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: CI,
  retries: CI ? 1 : 0,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: UI_URL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: `uv run uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      url: `${API_URL}/health`,
      env: { LLM_MOCK: "1", CORS_ORIGINS: UI_URL, RATE_LIMIT: "1000/minute" },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: CI ? `npm run build && npx next start -p ${UI_PORT}` : `npx next dev -p ${UI_PORT}`,
      url: UI_URL,
      env: { NEXT_PUBLIC_API_URL: API_URL },
      reuseExistingServer: false,
      timeout: 180_000,
    },
  ],
});

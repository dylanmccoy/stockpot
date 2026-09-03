import { defineConfig, devices } from "@playwright/test";
import { E2E_REGISTRATION_CODE } from "./e2e/integration.env";

/**
 * Integration E2E: the real SPA driving the **real FastAPI backend** through the
 * dev proxy. Every `*.integration.spec.ts` file runs here —
 * `auth.integration.spec.ts` (ticket 14 / plan Phase 2 gate),
 * `recipes.integration.spec.ts` (ticket 15 / plan Phase 3 gate).
 *
 * Kept separate from `playwright.config.ts` (the visual suite) so a plain
 * `npm run test:e2e` never boots a backend or needs `uv`. Everything here runs
 * on **dedicated ports** and an **isolated throwaway database**, so it cannot
 * touch — or be confused by — a normal `localhost:8000` / `localhost:5173` dev
 * stack a developer already has running:
 *
 *   - backend  → `:8971`, `RECIPE_DATABASE_URL=sqlite:///./e2e-integration.db`
 *   - Vite dev → `:5273`, proxying `/api` at the `:8971` backend, with
 *     `VITE_ENABLE_REGISTER=1` so the flagged sign-up form is exercised too.
 *
 * The "no sign-up UI when the flag is unset" half of the ticket is a build-time
 * concern locked by `src/pages/Login.test.tsx`.
 */

const BACKEND_PORT = 8971;
const FRONTEND_PORT = 5273;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /\.integration\.spec\.ts$/,
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "integration", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      // Isolated backend: its own port + a throwaway DB file wiped per run
      // (never the developer's `backend/recipe.db`). Registration is opened
      // behind a code so the specs can seed users and drive sign-up.
      command: `rm -f e2e-integration.db && uv run uvicorn app.main:app --port ${BACKEND_PORT}`,
      cwd: "../backend",
      url: `http://localhost:${BACKEND_PORT}/api/health`,
      env: {
        RECIPE_DATABASE_URL: "sqlite:///./e2e-integration.db",
        RECIPE_ALLOW_REGISTRATION: "1",
        RECIPE_REGISTRATION_CODE: E2E_REGISTRATION_CODE,
      },
      reuseExistingServer: !process.env.CI,
      stdout: "pipe",
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      env: {
        VITE_ENABLE_REGISTER: "1",
        VITE_API_PROXY_TARGET: `http://localhost:${BACKEND_PORT}`,
      },
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
});

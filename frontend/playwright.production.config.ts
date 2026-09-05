import { defineConfig, devices } from "@playwright/test";
import {
  PROD_REGISTRATION_CODE,
  PROD_SEED_PASSWORD,
  PROD_SEED_USERNAME,
} from "./e2e/production.env";

/**
 * Production-serving smoke E2E (private-household-deployment ticket 01a):
 * the *built* frontend served by the FastAPI app itself under one origin —
 * `npm run build`'s output, no Vite dev server, no dev proxy — driving a real
 * backend process against a disposable file-backed SQLite database.
 *
 * This is the seam `docs/spec.md`'s "Primary seam: the deployed application
 * origin" testing decision names: the current dev-proxy integration suite
 * (`playwright.integration.config.ts`) passing does not establish
 * production-serving correctness, because it never exercises
 * `RECIPE_FRONTEND_DIST` or the single-origin static/API routing at all.
 *
 * `webServer.command` is the wrapper script `e2e/production-server.mjs`, not
 * `uvicorn` directly: it boots the backend once, on a separate throwaway
 * port, with registration open to seed the one household account this
 * scenario needs (the production build has no sign-up UI); stops it; then
 * re-launches it on the real port with registration closed and
 * `RECIPE_FRONTEND_DIST` set — the actual server under test — against the
 * same database. See that script for why two ports matter, and why the seed
 * step has to live inside the command Playwright waits on rather than a
 * `globalSetup` (Playwright starts `webServer` before running any
 * `globalSetup`).
 *
 * `reuseExistingServer: false` unconditionally: a reused server would already
 * either have the seeded account or be mid-way through the wrong phase, and
 * every retry needs the same disposable-and-reseeded starting state anyway.
 *
 * Local start command: `npm run build && npm run test:e2e:production`.
 */

const PORT = 8972;
/** Throwaway port for the registration-open seed pass — must differ from
 *  `PORT` (see `e2e/production-server.mjs`). */
const SEED_PORT = 8973;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /\.production\.spec\.ts$/,
  // One server, one shared disposable database — scenarios run in sequence so
  // the recipe-write/read case's data isn't raced by another spec's writes.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "production", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node e2e/production-server.mjs",
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
    timeout: 120_000,
    env: {
      PROD_PORT: String(PORT),
      PROD_SEED_PORT: String(SEED_PORT),
      PROD_REGISTRATION_CODE,
      PROD_SEED_USERNAME,
      PROD_SEED_PASSWORD,
    },
  },
});

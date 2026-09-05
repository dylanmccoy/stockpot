import { defineConfig, devices } from "@playwright/test";
import {
  DEPLOY_REGISTRATION_CODE,
  DEPLOY_SEED_PASSWORD,
  DEPLOY_SEED_RECIPE_TITLE,
  DEPLOY_SEED_USERNAME,
} from "./e2e/deployment.env";

/**
 * Household-deployment E2E (private-household-deployment ticket 04a): the app
 * installed and started through the real `deploy/` scripts, carrying an
 * existing household database in.
 *
 * `e2e/deployment-server.mjs` seeds a throwaway "prior dev" database (one
 * account + one recipe) on a separate port, runs `deploy/install.sh
 * --adopt-from` to snapshot-copy it into the deployment database on
 * persistent storage outside the checkout, then `deploy/control.sh start`
 * from an unrelated working directory. The server under test is the built
 * frontend + API on one origin with registration closed — the actual shape
 * of the household deployment.
 *
 * Distinct from the `production` project (`playwright.production.config.ts`),
 * which seeds its account directly into a fresh database via its own wrapper:
 * this project's database provenance is *adoption through the deploy scripts*,
 * which is the behaviour 04a adds.
 *
 * Local: `npm run build && npm run test:e2e:deployment`.
 */

const PORT = 8974;
const SEED_PORT = 8975;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /\.deployment\.spec\.ts$/,
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "deployment", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node e2e/deployment-server.mjs",
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
    timeout: 120_000,
    env: {
      DEPLOY_PORT: String(PORT),
      DEPLOY_SEED_PORT: String(SEED_PORT),
      DEPLOY_REGISTRATION_CODE,
      DEPLOY_SEED_USERNAME,
      DEPLOY_SEED_PASSWORD,
      DEPLOY_SEED_RECIPE_TITLE,
    },
  },
});

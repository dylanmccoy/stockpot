import { defineConfig, devices } from "@playwright/test";
import {
  UPDATE_HANDOFF_FILE,
  UPDATE_REGISTRATION_CODE,
  UPDATE_SEED_PASSWORD,
  UPDATE_SEED_RECIPE_TITLE,
  UPDATE_SEED_USERNAME,
} from "./e2e/update.env";

/**
 * Schema-preserving application update E2E (private-household-deployment ticket
 * 04b): the deployment installed and started through the real `deploy/` scripts,
 * then switched to a replacement build with `deploy/update.sh` while the test is
 * running.
 *
 * `e2e/update-server.mjs` seeds a throwaway "prior dev" database (one account +
 * one recipe), runs `deploy/install.sh --adopt-from` to snapshot-copy it into
 * the deployment database, and starts it with a BACKGROUNDED `deploy/control.sh
 * start` (unlike the `deployment` project's foreground `control.sh run`) so the
 * update procedure's stop/start controls work. `smoke.update.spec.ts` then
 * invokes `deploy/update.sh --staging-dir <prebuilt>` itself and checks that
 * the carried-over records — and writes made against the first build — survive
 * the replacement build, and that later writes still persist.
 *
 * Serialised, single worker: the one deployment is mutated in place by the run.
 */

const PORT = 8976;
const SEED_PORT = 8977;

export default defineConfig({
  testDir: "./e2e",
  testMatch: /\.update\.spec\.ts$/,
  globalTeardown: "./e2e/update-teardown.ts",
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
  },
  projects: [{ name: "update", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node e2e/update-server.mjs",
    url: `http://localhost:${PORT}/api/health`,
    reuseExistingServer: false,
    stdout: "pipe",
    stderr: "pipe",
    timeout: 120_000,
    env: {
      UPDATE_PORT: String(PORT),
      UPDATE_SEED_PORT: String(SEED_PORT),
      UPDATE_HANDOFF_FILE,
      UPDATE_REGISTRATION_CODE,
      UPDATE_SEED_USERNAME,
      UPDATE_SEED_PASSWORD,
      UPDATE_SEED_RECIPE_TITLE,
    },
  },
});

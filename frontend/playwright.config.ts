import { defineConfig, devices } from "@playwright/test";

/**
 * Headless-browser pass of the dev component gallery (`/dev/components`) in both
 * themes — the manual check that CLAUDE.md / the Phase 1 review flagged as
 * impossible without browser tooling.
 *
 * `light` / `dark` projects set `prefers-color-scheme`; `app/theme.tsx` defaults
 * to the `"system"` preference, so each project resolves the whole document
 * (`<html data-theme>`) to its palette. Baselines are per-platform (font stacks
 * differ across OSes) — regenerate with `npm run test:e2e:update` on the same
 * base image CI uses.
 */
export default defineConfig({
  testDir: "./e2e",
  snapshotDir: "./e2e/__snapshots__",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  expect: {
    // Small tolerance for sub-pixel AA differences between runs.
    toHaveScreenshot: { maxDiffPixelRatio: 0.01 },
  },
  projects: [
    {
      name: "light",
      use: { ...devices["Desktop Chrome"], colorScheme: "light" },
    },
    {
      name: "dark",
      use: { ...devices["Desktop Chrome"], colorScheme: "dark" },
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});

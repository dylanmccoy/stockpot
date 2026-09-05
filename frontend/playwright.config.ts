import { defineConfig, devices } from "@playwright/test";

/**
 * Visual E2E: headless snapshot passes of `/dev/components` in a forced
 * `light` / `dark` colour scheme. These need only the Vite dev server.
 *
 * The auth-vs-real-backend integration suite lives in its own config
 * (`playwright.integration.config.ts`, `npm run test:integration`) so a
 * visual-only run never has to boot the backend or depend on `uv`.
 *
 * `light` / `dark` set `prefers-color-scheme`; `app/theme.tsx` defaults to the
 * `"system"` preference, so each project resolves the whole document
 * (`<html data-theme>`) to its palette. Baselines are per-platform (font stacks
 * differ across OSes) — regenerate with `npm run test:e2e:update` on the same
 * base image CI uses.
 */
export default defineConfig({
  testDir: "./e2e",
  snapshotDir: "./e2e/__snapshots__",
  testIgnore: [/\.integration\.spec\.ts$/, /\.deployment\.spec\.ts$/],
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

#!/usr/bin/env node
// Boots the backend TWICE against the same disposable, file-backed SQLite
// database (private-household-deployment ticket 01a):
//
//   1. Registration briefly open, on a SEPARATE throwaway port — long enough
//      to seed the one household account this smoke scenario needs through
//      the real API. The production build carries no sign-up UI, so this is
//      the only way in. A separate port matters: Playwright's `webServer.url`
//      check is satisfied by *any* HTTP response on the target port, even a
//      404 — if this phase reused the real port, Playwright would declare the
//      server "ready" the moment this phase answers, and tests would start
//      running against it mid-seed, before phase 2 ever starts.
//   2. Registration closed, on the real port, `RECIPE_FRONTEND_DIST` pointing
//      at the built frontend — this is the actual production-mode process
//      under test, and the only one `playwright.production.config.ts`'s
//      `webServer.url` can observe.
//
// Plain Node (no TS loader) because it runs as a `webServer.command`, not
// through Playwright's own TS transform. `playwright.production.config.ts`
// imports `./production.env.ts` and passes the constants down as env vars, so
// that file stays the single source of truth for the seeded credentials.
//
// Playwright starts this exactly once per run (`reuseExistingServer: false`,
// see the config) — reusing a previous run's server would skip the seed pass
// against a database that already has (or lacks) the expected account.

import { spawn } from "node:child_process";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const backendDir = path.resolve(__dirname, "../../backend");
const distDir = path.resolve(__dirname, "../dist");
const dbFile = "e2e-production.db";

const PORT = process.env.PROD_PORT ?? "8972";
const SEED_PORT = process.env.PROD_SEED_PORT ?? String(Number(PORT) + 1);
const REGISTRATION_CODE = process.env.PROD_REGISTRATION_CODE;
const SEED_USERNAME = process.env.PROD_SEED_USERNAME;
const SEED_PASSWORD = process.env.PROD_SEED_PASSWORD;

function log(...args) {
  console.log("[production-server]", ...args);
}

/** The currently-running backend child, if any — signal handlers below kill
 *  whichever one is live so a Playwright-issued SIGTERM never leaks a process
 *  holding a port for the next run. */
let currentChild = null;

for (const signal of ["SIGTERM", "SIGINT"]) {
  process.on(signal, () => {
    currentChild?.kill(signal);
  });
}

function spawnBackend(port, env) {
  const child = spawn(
    "uv",
    ["run", "uvicorn", "app.main:app", "--port", port],
    {
      cwd: backendDir,
      env: { ...process.env, ...env },
      stdio: "inherit",
    },
  );
  currentChild = child; // tracked for the SIGTERM/SIGINT handlers above
  return child;
}

async function waitForHealth(port, timeoutMs) {
  const healthUrl = `http://127.0.0.1:${port}/api/health`;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(healthUrl);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`backend did not become healthy at ${healthUrl}`);
}

function waitForExit(child) {
  return new Promise((resolve) => child.once("exit", (code) => resolve(code)));
}

async function stopAndWait(child) {
  // A SIGTERM/SIGINT arriving mid-seed can race this with the top-level signal
  // handler above — both may call `.kill()` on the same child. Harmless: a
  // second `kill()` on an already-exiting process is a no-op, and only one
  // `waitForExit` is ever awaited (this one).
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await waitForExit(child);
}

async function seedOneAccount() {
  log(`starting seed backend on :${SEED_PORT} (registration open)...`);
  const seedChild = spawnBackend(SEED_PORT, {
    RECIPE_DATABASE_URL: `sqlite:///${dbFile}`,
    RECIPE_ALLOW_REGISTRATION: "1",
    RECIPE_REGISTRATION_CODE: REGISTRATION_CODE,
  });
  try {
    await waitForHealth(SEED_PORT, 30_000);
    const res = await fetch(`http://127.0.0.1:${SEED_PORT}/api/auth/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: SEED_USERNAME,
        password: SEED_PASSWORD,
        code: REGISTRATION_CODE,
      }),
    });
    if (res.status !== 201) {
      throw new Error(
        `seed registration failed: ${res.status} ${await res.text()}`,
      );
    }
    log(`seeded account ${SEED_USERNAME}`);
  } finally {
    await stopAndWait(seedChild);
  }
}

async function main() {
  if (!existsSync(path.join(distDir, "index.html"))) {
    throw new Error(
      `frontend build not found at ${distDir} — run \`npm run build\` first`,
    );
  }
  rmSync(path.join(backendDir, dbFile), { force: true });

  await seedOneAccount();

  log(`starting production backend on :${PORT} (registration closed)...`);
  const prodChild = spawnBackend(PORT, {
    RECIPE_DATABASE_URL: `sqlite:///${dbFile}`,
    RECIPE_FRONTEND_DIST: distDir,
  });
  const code = await waitForExit(prodChild);
  process.exit(code ?? 0);
}

main().catch((err) => {
  console.error("[production-server]", err);
  process.exit(1);
});

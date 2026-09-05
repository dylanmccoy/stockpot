#!/usr/bin/env node
// Boots the household deployment through the real `deploy/` scripts
// (private-household-deployment ticket 04a), the way an operator installs it:
//
//   1. Seed a throwaway "prior dev" SQLite database on a SEPARATE port with
//      registration briefly open — register the household account and create
//      one recipe through the real API, then stop that backend.
//   2. Run `deploy/install.sh --adopt-from <that db>`: it takes a live
//      snapshot and copies it into the deployment database on persistent
//      storage outside the checkout. Registration is never opened here.
//   3. Run `deploy/control.sh run` FROM AN UNRELATED WORKING DIRECTORY — the
//      deployment must use its one explicit absolute database regardless.
//
// `control.sh run` execs uvicorn in the foreground, so it stays a child of
// this process (and of Playwright's webServer process group) and is torn down
// with it — unlike `control.sh start`, which deliberately detaches. The
// backgrounded start/stop/status path is covered by `backend/tests/test_deploy.py`.
//
// The deployed server (built frontend + API, one origin, registration closed)
// is what `playwright.deployment.config.ts`'s `webServer.url` observes.
//
// Plain Node (no TS loader): it runs as a `webServer.command`. Seeded
// credentials come from `./deployment.env.ts` via the config's env passthrough.

import { execFileSync, spawn } from "node:child_process";
import { existsSync, mkdtempSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..");
const backendDir = path.join(repoRoot, "backend");
const distDir = path.join(frontendDir, "dist");

const PORT = process.env.DEPLOY_PORT ?? "8974";
const SEED_PORT = process.env.DEPLOY_SEED_PORT ?? String(Number(PORT) + 1);
const REGISTRATION_CODE = process.env.DEPLOY_REGISTRATION_CODE;
const SEED_USERNAME = process.env.DEPLOY_SEED_USERNAME;
const SEED_PASSWORD = process.env.DEPLOY_SEED_PASSWORD;
const SEED_RECIPE_TITLE = process.env.DEPLOY_SEED_RECIPE_TITLE;

// A disposable deployment layout: the "prior dev" DB, the persistent data dir
// the scripts install into, and the pidfile/log all live under here. Sweep any
// left by a previous run first (Playwright SIGKILLs the webServer at teardown,
// so our own cleanup does not always get to run).
const PREFIX = "recipe-deploy-e2e-";
for (const entry of readdirSync(tmpdir())) {
  if (entry.startsWith(PREFIX)) {
    rmSync(path.join(tmpdir(), entry), { recursive: true, force: true });
  }
}
const workDir = mkdtempSync(path.join(tmpdir(), PREFIX));
const devDb = path.join(workDir, "dev.db");
const dataDir = path.join(workDir, "data");

const deployEnv = {
  ...process.env,
  RECIPE_DEPLOY_CHECKOUT: repoRoot,
  RECIPE_DEPLOY_DATA_DIR: dataDir,
  RECIPE_DEPLOY_FRONTEND_DIST: distDir,
  RECIPE_DEPLOY_PORT: PORT,
  RECIPE_DEPLOY_ENV_FILE: path.join(workDir, "no-such.env"),
};

function log(...args) {
  console.log("[deployment-server]", ...args);
}

let currentChild = null;
let cleaned = false;

function cleanup() {
  if (cleaned) return;
  cleaned = true;
  // The deployment runs as `control.sh run` — a foreground child in this
  // process group, with no pidfile — so killing the child is the whole stop.
  currentChild?.kill("SIGTERM");
  rmSync(workDir, { recursive: true, force: true });
}

for (const signal of ["SIGTERM", "SIGINT", "SIGHUP"]) {
  process.on(signal, () => {
    cleanup();
    process.exit(0);
  });
}
process.on("exit", cleanup);

function spawnBackend(port, env) {
  const child = spawn(
    "uv",
    ["run", "uvicorn", "app.main:app", "--port", port],
    { cwd: backendDir, env: { ...process.env, ...env }, stdio: "inherit" },
  );
  currentChild = child;
  return child;
}

async function waitForHealth(port, timeoutMs) {
  const url = `http://127.0.0.1:${port}/api/health`;
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`backend did not become healthy at ${url}`);
}

function waitForExit(child) {
  return new Promise((resolve) => child.once("exit", (code) => resolve(code)));
}

async function stopAndWait(child) {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await waitForExit(child);
}

async function seedPriorDatabase() {
  log(`seeding prior dev database on :${SEED_PORT} (registration open)`);
  const seed = spawnBackend(SEED_PORT, {
    RECIPE_DATABASE_URL: `sqlite:///${devDb}`,
    RECIPE_ALLOW_REGISTRATION: "1",
    RECIPE_REGISTRATION_CODE: REGISTRATION_CODE,
  });
  try {
    await waitForHealth(SEED_PORT, 30_000);
    const base = `http://127.0.0.1:${SEED_PORT}`;
    const reg = await fetch(`${base}/api/auth/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        username: SEED_USERNAME,
        password: SEED_PASSWORD,
        code: REGISTRATION_CODE,
      }),
    });
    if (reg.status !== 201) {
      throw new Error(
        `seed registration failed: ${reg.status} ${await reg.text()}`,
      );
    }
    const { token } = await reg.json();
    const recipe = await fetch(`${base}/api/recipes`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ title: SEED_RECIPE_TITLE }),
    });
    if (recipe.status !== 201) {
      throw new Error(
        `seed recipe failed: ${recipe.status} ${await recipe.text()}`,
      );
    }
    log(`seeded account ${SEED_USERNAME} + recipe "${SEED_RECIPE_TITLE}"`);
  } finally {
    await stopAndWait(seed);
  }
}

async function main() {
  if (!existsSync(path.join(distDir, "index.html"))) {
    throw new Error(
      `frontend build not found at ${distDir} — run \`npm run build\` first`,
    );
  }

  await seedPriorDatabase();

  // Adopt the seeded data.
  log(`install.sh --adopt-from ${devDb}`);
  execFileSync(
    "bash",
    [
      path.join(repoRoot, "deploy", "install.sh"),
      "--skip-build",
      "--adopt-from",
      devDb,
    ],
    { cwd: repoRoot, env: deployEnv, stdio: "inherit" },
  );

  // Serve it, foreground, from a directory that is neither the checkout nor
  // the data dir — the explicit absolute database must be used regardless.
  log("control.sh run  (cwd: os.tmpdir())");
  const deployChild = spawn(
    "bash",
    [path.join(repoRoot, "deploy", "control.sh"), "run"],
    { cwd: tmpdir(), env: deployEnv, stdio: "inherit" },
  );
  currentChild = deployChild;

  await waitForHealth(PORT, 30_000);
  log(`deployment is serving on :${PORT}`);

  const code = await waitForExit(deployChild);
  process.exit(code ?? 0);
}

main().catch((err) => {
  console.error("[deployment-server]", err);
  cleanup();
  process.exit(1);
});

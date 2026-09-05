#!/usr/bin/env node
// Boots the household deployment through the real `deploy/` scripts and leaves
// it running under a backgrounded `deploy/control.sh start`, so
// `smoke.update.spec.ts` can drive `deploy/update.sh` against it
// (private-household-deployment ticket 04b):
//
//   1. Seed a throwaway "prior dev" SQLite database on a SEPARATE port with
//      registration briefly open — register the household account and one
//      recipe through the real API, then stop that backend.
//   2. `deploy/install.sh --adopt-from <that db>` snapshot-copies it into the
//      deployment database on persistent storage outside the checkout.
//   3. `deploy/control.sh start` — BACKGROUNDED (setsid + pidfile), the way an
//      operator runs it, so `deploy/update.sh` can later `control.sh stop` it,
//      swap the build, and `control.sh start` again. (The `deployment` project
//      uses `control.sh run` in the foreground; this one can't, because the
//      update procedure needs the stop/start controls.)
//
// This process then stays alive purely as a supervisor: Playwright keeps the
// `webServer.command` running for the session and SIGTERMs it at teardown, at
// which point we `control.sh stop` the detached deployment so no uvicorn is
// left holding the port.
//
// The resolved deployment layout is written to a fixed handoff file (see
// `update.env.ts`) for the spec to read.

import { execFileSync, spawn } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendDir, "..");
const backendDir = path.join(repoRoot, "backend");
const distDir = path.join(frontendDir, "dist");
const installSh = path.join(repoRoot, "deploy", "install.sh");
const controlSh = path.join(repoRoot, "deploy", "control.sh");

const PORT = process.env.UPDATE_PORT ?? "8976";
const SEED_PORT = process.env.UPDATE_SEED_PORT ?? String(Number(PORT) + 1);
const REGISTRATION_CODE = process.env.UPDATE_REGISTRATION_CODE;
const SEED_USERNAME = process.env.UPDATE_SEED_USERNAME;
const SEED_PASSWORD = process.env.UPDATE_SEED_PASSWORD;
const SEED_RECIPE_TITLE = process.env.UPDATE_SEED_RECIPE_TITLE;
const HANDOFF_FILE = process.env.UPDATE_HANDOFF_FILE;
const MARKER_TOKEN = `updated-build-${Date.now()}`;

// A fixed work root (not mkdtemp) so a startup sweep can reliably stop a
// deployment leaked by a previous run that Playwright SIGKILLed.
const workRoot = path.join(tmpdir(), "recipe-deploy-update-e2e");
const dataDir = path.join(workRoot, "data");
const liveDist = path.join(workRoot, "live-dist");
const nextDist = path.join(workRoot, "next-dist");
const devDb = path.join(workRoot, "dev.db");

const deployEnv = {
  ...process.env,
  RECIPE_DEPLOY_CHECKOUT: repoRoot,
  RECIPE_DEPLOY_DATA_DIR: dataDir,
  RECIPE_DEPLOY_FRONTEND_DIST: liveDist,
  RECIPE_DEPLOY_PORT: PORT,
  RECIPE_DEPLOY_ENV_FILE: path.join(workRoot, "no-such.env"),
};

function log(...args) {
  console.log("[update-server]", ...args);
}

let currentChild = null;
let cleaned = false;

function stopDeployment() {
  try {
    execFileSync("bash", [controlSh, "stop"], {
      env: deployEnv,
      stdio: "inherit",
    });
  } catch {
    // best effort — nothing to stop, or already gone
  }
}

function cleanup() {
  if (cleaned) return;
  cleaned = true;
  currentChild?.kill("SIGTERM");
  stopDeployment();
  rmSync(workRoot, { recursive: true, force: true });
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
    {
      cwd: backendDir,
      env: { ...process.env, ...env },
      stdio: "inherit",
    },
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

  // Fresh work root; stop anything a SIGKILLed previous run left detached.
  if (existsSync(workRoot)) {
    stopDeployment();
    rmSync(workRoot, { recursive: true, force: true });
  }
  for (const entry of readdirSync(tmpdir())) {
    if (entry.startsWith("recipe-deploy-update-e2e")) {
      rmSync(path.join(tmpdir(), entry), { recursive: true, force: true });
    }
  }
  mkdirSync(dataDir, { recursive: true });

  // The served build lives under the work root (not the checkout's dist/), so
  // update.sh's dist / dist.prev / dist.staging swap never touches the repo.
  execFileSync("cp", ["-a", distDir, liveDist], { stdio: "inherit" });
  // The "next" build: the same assets plus a uniquely identifiable marker, so
  // the spec can confirm through HTTP that the replacement build is the one
  // being served after update.sh runs.
  execFileSync("cp", ["-a", distDir, nextDist], { stdio: "inherit" });
  writeFileSync(
    path.join(nextDist, "assets", "deploy-update-marker.txt"),
    MARKER_TOKEN,
  );

  await seedPriorDatabase();

  log(`install.sh --adopt-from ${devDb}`);
  execFileSync("bash", [installSh, "--skip-build", "--adopt-from", devDb], {
    cwd: repoRoot,
    env: deployEnv,
    stdio: "inherit",
  });

  log("control.sh start  (backgrounded)");
  execFileSync("bash", [controlSh, "start"], {
    cwd: tmpdir(),
    env: deployEnv,
    stdio: "inherit",
  });
  await waitForHealth(PORT, 30_000);

  mkdirSync(path.dirname(HANDOFF_FILE), { recursive: true });
  writeFileSync(
    HANDOFF_FILE,
    JSON.stringify(
      { repoRoot, deployEnv, nextDist, markerToken: MARKER_TOKEN },
      null,
      2,
    ),
  );
  log(`deployment serving on :${PORT}; handoff written to ${HANDOFF_FILE}`);

  // Stay alive as the webServer process; teardown runs cleanup().
  setInterval(() => {}, 1 << 30);
}

main().catch((err) => {
  console.error("[update-server]", err);
  cleanup();
  process.exit(1);
});

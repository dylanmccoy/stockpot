import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  UPDATE_HANDOFF_FILE,
  UPDATE_SEED_PASSWORD,
  UPDATE_SEED_RECIPE_TITLE,
  UPDATE_SEED_USERNAME,
} from "./update.env";

/**
 * Private-household-deployment tickets 04b (deploy a schema-preserving update)
 * and 04c (return to a previous compatible build on demand).
 *
 * The harness (`playwright.update.config.ts` → `e2e/update-server.mjs`) has
 * installed the deployment from a prior database (one account + one recipe) and
 * started it backgrounded. The two tests run in order against that one
 * deployment (single worker, mutated in place):
 *
 *   1. 04b — sign in as the adopted account, see the carried-over recipe, write
 *      a recipe against the CURRENT build, run `deploy/update.sh --staging-dir`
 *      (validate build → pre-maintenance snapshot → stop → switch → restart on
 *      the same explicit database), then confirm the replacement build is
 *      served, every record survives, and a further write persists.
 *   2. 04c — with the updated build now live, write another record, run
 *      `deploy/rollback.sh` (no args → the build update.sh retained), and
 *      confirm the pre-update build is served again, a pre-maintenance snapshot
 *      was taken, the database was untouched, and every record — including the
 *      one written against the updated build — is still readable and editable.
 */

const TOKEN_KEY = "recipe.token";

type Handoff = {
  repoRoot: string;
  deployEnv: Record<string, string>;
  nextDist: string;
  markerToken: string;
};

// Written by `e2e/update-server.mjs` once the deployment is up — read lazily,
// not at import time (Playwright collects specs before the webServer starts).
let handoff: Handoff;
test.beforeAll(() => {
  handoff = JSON.parse(readFileSync(UPDATE_HANDOFF_FILE, "utf8")) as Handoff;
});

async function logIn(page: import("@playwright/test").Page) {
  await page.getByLabel("Username").fill(UPDATE_SEED_USERNAME);
  await page.getByLabel("Password").fill(UPDATE_SEED_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();
}

async function addRecipe(page: import("@playwright/test").Page, title: string) {
  await page.getByRole("link", { name: "Add recipe" }).click();
  await page.getByLabel(/^Title/).fill(title);
  await page.getByRole("button", { name: "Save recipe" }).click();
  await expect(
    page.getByRole("heading", { name: title, level: 1 }),
  ).toBeVisible();
}

test("records and later writes survive a schema-preserving replacement build", async ({
  page,
  request,
}) => {
  const preUpdateTitle = `Written Before Update ${Date.now()}`;

  await page.goto("/");
  await logIn(page);
  await expect(
    page.getByRole("heading", { name: UPDATE_SEED_RECIPE_TITLE, level: 2 }),
  ).toBeVisible();
  await addRecipe(page, preUpdateTitle);

  // The replacement build's marker asset is not served by the current build.
  expect((await request.get("/assets/deploy-update-marker.txt")).status()).toBe(
    404,
  );

  const backupsDir = path.join(
    handoff.deployEnv.RECIPE_DEPLOY_DATA_DIR,
    "backups",
  );
  const snapshotsBefore = readdirSync(backupsDir).filter((f) =>
    /^recipe-.*\.db$/.test(f),
  ).length;

  // Run the real update procedure against the running deployment.
  const out = execFileSync(
    "bash",
    [
      path.join(handoff.repoRoot, "deploy", "update.sh"),
      "--staging-dir",
      handoff.nextDist,
    ],
    { env: handoff.deployEnv, encoding: "utf8" },
  );
  expect(out).toContain("update complete");

  // update.sh took a pre-maintenance snapshot before switching.
  const snapshotsAfter = readdirSync(backupsDir).filter((f) =>
    /^recipe-.*\.db$/.test(f),
  ).length;
  expect(snapshotsAfter).toBe(snapshotsBefore + 1);

  // The deployment restarted; wait for it to answer again.
  await expect
    .poll(async () => (await request.get("/api/health")).status(), {
      timeout: 30_000,
    })
    .toBe(200);

  // The replacement build is the one now served.
  const marker = await request.get("/assets/deploy-update-marker.txt");
  expect(marker.status()).toBe(200);
  expect((await marker.text()).trim()).toBe(handoff.markerToken);

  // Every earlier record is still present through a fresh session on the new
  // build, and a further write persists across a reload.
  const postUpdateTitle = `Written After Update ${Date.now()}`;
  await page.evaluate((key) => localStorage.removeItem(key), TOKEN_KEY);
  await page.goto("/");
  await logIn(page);
  await addRecipe(page, postUpdateTitle);

  await page.goto("/");
  for (const title of [
    UPDATE_SEED_RECIPE_TITLE,
    preUpdateTitle,
    postUpdateTitle,
  ]) {
    await expect(
      page.getByRole("heading", { name: title, level: 2 }),
    ).toBeVisible();
  }
});

test("returns to the previous compatible build on demand, household records intact", async ({
  page,
  request,
}) => {
  // Runs after the update test above: the replacement build (marker asset) is
  // the one currently served.
  const onUpdatedBuildTitle = `Written On The Updated Build ${Date.now()}`;

  await page.goto("/");
  await logIn(page);
  expect((await request.get("/assets/deploy-update-marker.txt")).status()).toBe(
    200,
  );
  await addRecipe(page, onUpdatedBuildTitle);

  const backupsDir = path.join(
    handoff.deployEnv.RECIPE_DEPLOY_DATA_DIR,
    "backups",
  );
  const snapshotsBefore = readdirSync(backupsDir).filter((f) =>
    /^recipe-.*\.db$/.test(f),
  ).length;

  // The deliberate operator command to step back to the retained build.
  const out = execFileSync(
    "bash",
    [path.join(handoff.repoRoot, "deploy", "rollback.sh")],
    { env: handoff.deployEnv, encoding: "utf8" },
  );
  expect(out).toContain("rollback complete");

  // rollback.sh took its own pre-maintenance snapshot before switching.
  const snapshotsAfter = readdirSync(backupsDir).filter((f) =>
    /^recipe-.*\.db$/.test(f),
  ).length;
  expect(snapshotsAfter).toBe(snapshotsBefore + 1);

  await expect
    .poll(async () => (await request.get("/api/health")).status(), {
      timeout: 30_000,
    })
    .toBe(200);

  // The pre-update build is the one served again — its assets do not include
  // the updated build's marker.
  expect((await request.get("/assets/deploy-update-marker.txt")).status()).toBe(
    404,
  );

  // Every record is still readable through a fresh session on the rolled-back
  // build, and a further write persists across a reload (editable).
  const afterRollbackTitle = `Written After Rollback ${Date.now()}`;
  await page.evaluate((key) => localStorage.removeItem(key), TOKEN_KEY);
  await page.goto("/");
  await logIn(page);
  await addRecipe(page, afterRollbackTitle);

  await page.goto("/");
  for (const title of [
    UPDATE_SEED_RECIPE_TITLE,
    onUpdatedBuildTitle,
    afterRollbackTitle,
  ]) {
    await expect(
      page.getByRole("heading", { name: title, level: 2 }),
    ).toBeVisible();
  }
});

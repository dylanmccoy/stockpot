import { tmpdir } from "node:os";
import path from "node:path";

/**
 * Shared seam values for the `update` Playwright project (private-household-
 * deployment ticket 04b). Imported by `playwright.update.config.ts` (passed
 * through as env vars to `e2e/update-server.mjs`) and by
 * `e2e/smoke.update.spec.ts` (to drive the login form and locate the
 * deployment the harness installed).
 *
 * The account and the recipe below are created in a throwaway "prior dev"
 * database which `deploy/install.sh` adopts into the deployment database via a
 * live snapshot. The test then runs `deploy/update.sh` to switch the served
 * build and checks that those records — plus writes made against the first
 * build — survive the replacement build.
 */

export const UPDATE_REGISTRATION_CODE = "e2e-update-registration-code";

export const UPDATE_SEED_USERNAME = "household-update";
export const UPDATE_SEED_PASSWORD = "carried-through-the-update";
export const UPDATE_SEED_RECIPE_TITLE = "Recipe From Before The Update";

/**
 * `e2e/update-server.mjs` writes the resolved deployment layout (the `deploy/`
 * env vars, the prebuilt "next" build directory, and its marker asset token)
 * here so `smoke.update.spec.ts` can invoke `deploy/update.sh` against the same
 * deployment. A fixed path (not a per-run temp dir) so the spec can find it
 * without the config passing it through.
 */
export const UPDATE_HANDOFF_FILE = path.join(
  tmpdir(),
  "recipe-deploy-update-e2e",
  "handoff.json",
);

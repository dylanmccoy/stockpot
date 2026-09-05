/**
 * Shared seam values for the `deployment` Playwright project (private-household-
 * deployment ticket 04a). Imported by `playwright.deployment.config.ts` (passed
 * through as env vars to `e2e/deployment-server.mjs`) and by
 * `e2e/smoke.deployment.spec.ts` (to drive the login form).
 *
 * The account and the recipe below are created in a throwaway "prior dev"
 * database which `deploy/install.sh` then adopts into the deployment database
 * via a live snapshot — so seeing them through the deployed app is the proof
 * that existing household records were carried in.
 */

/** Registration code the one-shot seed backend is booted with. Never reaches
 *  the deployed server — that runs with registration closed. */
export const DEPLOY_REGISTRATION_CODE = "e2e-deployment-registration-code";

/** The household account seeded into the pre-existing database. */
export const DEPLOY_SEED_USERNAME = "household-adopt";
export const DEPLOY_SEED_PASSWORD = "carried-over-horse-battery";

/** A recipe seeded into the pre-existing database, expected to survive
 *  adoption and be visible through the deployed app. */
export const DEPLOY_SEED_RECIPE_TITLE = "Adopted Household Recipe";

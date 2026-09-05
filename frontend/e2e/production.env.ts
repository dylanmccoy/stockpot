/**
 * Shared seam values for the `production` Playwright project (deployment
 * ticket 01a). Imported by `playwright.production.config.ts` (which passes
 * them through as env vars to `e2e/production-server.mjs`, the wrapper that
 * seeds the account and then boots the real production-mode server) and by
 * `e2e/smoke.production.spec.ts` (to drive the login form with them).
 */

/** Registration code the one-shot seed pass is booted with. Never reaches the
 *  server under test — that server runs with registration closed. */
export const PROD_REGISTRATION_CODE = "e2e-production-registration-code";

/** The one household account seeded before registration closes. */
export const PROD_SEED_USERNAME = "household-e2e";
export const PROD_SEED_PASSWORD = "correct-horse-battery-prod";

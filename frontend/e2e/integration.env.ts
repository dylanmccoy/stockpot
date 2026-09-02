/**
 * Shared seam values for the `integration` Playwright project. Imported by both
 * `playwright.config.ts` (to boot the backend) and the `*.integration.spec.ts`
 * files (to talk to it), so the registration code lives in exactly one place.
 */

/** Registration code the integration backend is booted with. */
export const E2E_REGISTRATION_CODE = "e2e-registration-code";

import { expect, test } from "@playwright/test";
import {
  PROD_REGISTRATION_CODE,
  PROD_SEED_PASSWORD,
  PROD_SEED_USERNAME,
} from "./production.env";

/**
 * Deployment ticket 01a: "a household member can open the production entry
 * address, sign in, and save a recipe through the real API without
 * development servers." `playwright.production.config.ts` boots the built
 * frontend behind a real FastAPI process (`e2e/production-server.mjs`) with
 * an isolated, file-backed SQLite database, one seeded household account, and
 * registration closed — the actual shape of a household deployment.
 *
 * Covered (ticket 01a bullet 3 + spec.md "Serving and authentication cases"):
 *  - the entry document loads the real build and a household member signs in
 *  - a wrong password is rejected inline
 *  - logout ends the session
 *  - a recipe write/read round-trips through the real API and survives reload
 *  - an unauthenticated API request is refused
 *  - registration stays closed: no sign-up UI in the shipped build, and the
 *    API itself refuses a direct registration request
 *
 * No `VITE_ENABLE_REGISTER` build flag here (unlike
 * `playwright.integration.config.ts`'s dev server) — this is deliberately the
 * plain `npm run build` output a household actually gets.
 */

const TOKEN_KEY = "recipe.token";

async function logIn(
  page: import("@playwright/test").Page,
  password = PROD_SEED_PASSWORD,
) {
  await page.getByLabel("Username").fill(PROD_SEED_USERNAME);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

test.describe("production smoke · built frontend + real backend", () => {
  test("signs in from the entry page and reaches the app", async ({ page }) => {
    await page.goto("/");
    await logIn(page);

    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();
    expect(
      await page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY),
    ).not.toBeNull();
  });

  test("a wrong password is rejected inline", async ({ page }) => {
    await page.goto("/");
    await logIn(page, "not-the-password");

    await expect(page.getByRole("alert")).toHaveText(
      "invalid username or password",
    );
    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
    expect(
      await page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY),
    ).toBeNull();
  });

  test("logout ends the session", async ({ page }) => {
    await page.goto("/");
    await logIn(page);
    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();

    await page
      .getByRole("button", { name: PROD_SEED_USERNAME, exact: true })
      .click();
    await page.getByRole("button", { name: "Log out" }).click();

    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
    expect(
      await page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY),
    ).toBeNull();
  });

  test("a recipe write/read round-trips through the deployed app", async ({
    page,
  }) => {
    await page.goto("/");
    await logIn(page);
    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();

    const title = `Production Smoke ${Date.now()}`;
    await page.getByRole("link", { name: "Add recipe" }).click();
    await page.getByLabel(/^Title/).fill(title);
    await page.getByRole("button", { name: "Save recipe" }).click();

    await expect(
      page.getByRole("heading", { name: title, level: 1 }),
    ).toBeVisible();

    // Prove the write persisted server-side: a fresh full navigation to the
    // entry document ("/", the address a household member actually opens)
    // reads it back from the real API. Reloading the nested detail URL
    // directly isn't supported until ticket 01b.
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: title, level: 2 }),
    ).toBeVisible();
  });

  test("an unauthenticated API request is refused", async ({ request }) => {
    const res = await request.get("/api/recipes");
    expect(res.status()).toBe(401);
  });

  test("registration stays closed: no sign-up UI and the API refuses it", async ({
    page,
    request,
  }) => {
    await page.goto("/");
    await expect(
      page.getByRole("button", { name: "Create account" }),
    ).toHaveCount(0);

    const res = await request.post("/api/auth/register", {
      data: {
        username: `nope-${Date.now()}`,
        password: "irrelevant-password",
        code: PROD_REGISTRATION_CODE,
      },
    });
    expect(res.status()).toBe(403);
  });
});

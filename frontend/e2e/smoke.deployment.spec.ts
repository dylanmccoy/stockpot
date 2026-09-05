import { expect, test } from "@playwright/test";
import {
  DEPLOY_REGISTRATION_CODE,
  DEPLOY_SEED_PASSWORD,
  DEPLOY_SEED_RECIPE_TITLE,
  DEPLOY_SEED_USERNAME,
} from "./deployment.env";

/**
 * Private-household-deployment ticket 04a: "the owner can install and run the
 * production app in WSL while retaining their existing household records."
 *
 * The harness (`playwright.deployment.config.ts` → `e2e/deployment-server.mjs`)
 * installs the app through `deploy/install.sh --adopt-from <prior db>` and
 * starts it with `deploy/control.sh`. The prior database holds one account and
 * one recipe; both must be reachable through the deployed origin, and new
 * writes against the deployment must persist.
 */

const TOKEN_KEY = "recipe.token";

async function logIn(
  page: import("@playwright/test").Page,
  password = DEPLOY_SEED_PASSWORD,
) {
  await page.getByLabel("Username").fill(DEPLOY_SEED_USERNAME);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in" }).click();
}

test.describe("household deployment · adopted data", () => {
  test("the adopted account signs in and its carried-over recipe is there", async ({
    page,
  }) => {
    await page.goto("/");
    await logIn(page);

    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();
    await expect(
      page.getByRole("heading", { name: DEPLOY_SEED_RECIPE_TITLE, level: 2 }),
    ).toBeVisible();
    expect(
      await page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY),
    ).not.toBeNull();
  });

  test("a new record saved against the deployment persists on reload", async ({
    page,
  }) => {
    await page.goto("/");
    await logIn(page);
    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();

    const title = `Deployment Write ${Date.now()}`;
    await page.getByRole("link", { name: "Add recipe" }).click();
    await page.getByLabel(/^Title/).fill(title);
    await page.getByRole("button", { name: "Save recipe" }).click();
    await expect(
      page.getByRole("heading", { name: title, level: 1 }),
    ).toBeVisible();

    await page.goto("/");
    // The adopted recipe and the new one are both read back from the real API.
    await expect(
      page.getByRole("heading", { name: DEPLOY_SEED_RECIPE_TITLE, level: 2 }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { name: title, level: 2 }),
    ).toBeVisible();
  });

  test("the deployed app runs with registration closed", async ({
    request,
  }) => {
    expect((await request.get("/api/recipes")).status()).toBe(401);

    const res = await request.post("/api/auth/register", {
      data: {
        username: `nope-${Date.now()}`,
        password: "irrelevant-password",
        code: DEPLOY_REGISTRATION_CODE,
      },
    });
    expect(res.status()).toBe(403);
  });
});

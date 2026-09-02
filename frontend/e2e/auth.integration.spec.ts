import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { E2E_REGISTRATION_CODE } from "./integration.env";

/**
 * Auth against the **real backend** (frontend ticket 14 / plan Phase 2 gate).
 *
 * `playwright.integration.config.ts` boots an isolated backend (`uv run
 * uvicorn`, own port, throwaway DB) next to a throwaway Vite dev server, and
 * every request below travels the real dev proxy. This is the end-to-end
 * counterpart of `src/app/auth.flow.test.tsx`, which runs the same scenarios
 * against MSW:
 *
 *  - login success → redirect to `?next`
 *  - login failure (`401`) → inline banner, no token
 *  - a rejected token on load → silent redirect to `/login?next=` (the five
 *    `get_current_user` failure shapes all collapse to one real
 *    `401 {"detail":"not authenticated"}`, so one real case stands in for the
 *    5-way enumeration that stays in `auth.flow.test.tsx`)
 *  - logout → token cleared, back to `/login`
 *  - `GET /api/auth/me` rehydrates the session across a reload
 *  - the flagged registration form surfaces a real backend refusal inline
 *    (via `403 "invalid registration code"` — same status + inline-banner
 *    surface as `"registration disabled"` per spec §6; that exact string is
 *    locked in `src/pages/Login.test.tsx`), and a valid registration signs in
 *
 * The dev server runs with `VITE_ENABLE_REGISTER=1`, so the sign-up form is
 * present here; the "no sign-up UI when the flag is unset" half of the ticket
 * is a build-time concern locked by `src/pages/Login.test.tsx`.
 */

const PASSWORD = "correct-horse-battery";
/** localStorage key owned by `src/api/client.ts` (`TOKEN_KEY`). Hardcoded here
 *  because the spec reads it from the browser, across the process boundary. */
const TOKEN_KEY = "recipe.token";

/** Unique per test so specs stay independent and survive a reused backend. */
const freshUsername = () =>
  `e2e_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;

async function seedUser(
  request: APIRequestContext,
  username: string,
): Promise<void> {
  const res = await request.post("/api/auth/register", {
    data: { username, password: PASSWORD, code: E2E_REGISTRATION_CODE },
  });
  expect(res.status(), await res.text()).toBe(201);
}

const readToken = (page: Page) =>
  page.evaluate((key) => localStorage.getItem(key), TOKEN_KEY);

/** The `<form>` containing the button named `label` — scoped so the login and
 *  registration forms' identically-labelled "Username" / "Password" fields
 *  don't clash. */
const formWithButton = (page: Page, label: string) =>
  page.locator("form", { has: page.getByRole("button", { name: label }) });

const loginForm = (page: Page) => formWithButton(page, "Log in");
const registerForm = (page: Page) => formWithButton(page, "Create account");

/** Drive the login form to submission. Mirrors `seedUser` for the UI path. */
async function logIn(page: Page, username: string, password = PASSWORD) {
  await loginForm(page).getByLabel("Username").fill(username);
  await loginForm(page).getByLabel("Password").fill(password);
  await loginForm(page).getByRole("button", { name: "Log in" }).click();
}

test.describe("auth · real backend", () => {
  test("logs in, redirects to ?next, and survives a reload via /api/auth/me", async ({
    page,
    request,
  }) => {
    const username = freshUsername();
    await seedUser(request, username);

    await page.goto("/login?next=/inventory");
    await logIn(page, username);

    await expect(
      page.getByRole("heading", { name: "Inventory" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/inventory$/);
    expect(await readToken(page)).not.toBeNull();

    // Reload: the stored token is re-verified through GET /api/auth/me.
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Inventory" }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/inventory$/);
    expect(await readToken(page)).not.toBeNull();
  });

  test("a wrong password shows the inline rejection and stores no token", async ({
    page,
    request,
  }) => {
    const username = freshUsername();
    await seedUser(request, username);

    await page.goto("/login?next=/inventory");
    await logIn(page, username, "not-the-password");

    await expect(loginForm(page).getByRole("alert")).toHaveText(
      "invalid username or password",
    );
    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
    expect(await readToken(page)).toBeNull();
  });

  test("a rejected token on load bounces to /login?next= and is cleared", async ({
    page,
  }) => {
    // Need an app origin before touching localStorage.
    await page.goto("/login");
    await page.evaluate(
      (key) => localStorage.setItem(key, "definitely-not-a-real-token"),
      TOKEN_KEY,
    );

    await page.goto("/inventory");

    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/login\?next=%2Finventory$/);
    expect(await readToken(page)).toBeNull();
  });

  test("logout clears the token and returns to /login", async ({
    page,
    request,
  }) => {
    const username = freshUsername();
    await seedUser(request, username);

    await page.goto("/login");
    await logIn(page, username);

    await expect(page.getByRole("heading", { name: "Recipes" })).toBeVisible();

    await page.getByRole("button", { name: username, exact: true }).click();
    await page.getByRole("button", { name: "Log out" }).click();

    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
    expect(await readToken(page)).toBeNull();
  });

  test("the registration form surfaces a real backend refusal inline", async ({
    page,
  }) => {
    await page.goto("/login");
    const form = registerForm(page);

    await form.getByLabel("Username").fill(freshUsername());
    await form.getByLabel("Password").fill(PASSWORD);
    // Registration code left blank → backend 403. "invalid registration code"
    // and "registration disabled" share this status + inline-banner surface;
    // the exact strings are locked in src/pages/Login.test.tsx against MSW.
    await form.getByRole("button", { name: "Create account" }).click();

    await expect(form.getByRole("alert")).toHaveText(
      "invalid registration code",
    );
    await expect(
      page.getByRole("heading", { name: "Log in", level: 1 }),
    ).toBeVisible();
  });

  test("a valid registration through the form signs the new user in", async ({
    page,
  }) => {
    await page.goto("/login?next=/inventory");
    const form = registerForm(page);

    await form.getByLabel("Username").fill(freshUsername());
    await form.getByLabel("Password").fill(PASSWORD);
    await form.getByLabel("Registration code").fill(E2E_REGISTRATION_CODE);
    await form.getByRole("button", { name: "Create account" }).click();

    await expect(
      page.getByRole("heading", { name: "Inventory" }),
    ).toBeVisible();
    expect(await readToken(page)).not.toBeNull();
  });
});

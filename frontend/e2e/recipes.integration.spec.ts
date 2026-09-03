import {
  expect,
  test,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { E2E_REGISTRATION_CODE } from "./integration.env";

/**
 * Recipes against the **real backend** (frontend ticket 15 / plan Phase 3 gate).
 *
 * `playwright.integration.config.ts` boots an isolated FastAPI backend (`uv run
 * uvicorn`, own port, throwaway DB) beside a throwaway Vite dev server; every
 * request below travels the real dev proxy. This is the end-to-end counterpart
 * of the RecipeList / RecipeForm / RecipeDetail suites, which run the same
 * screens against MSW.
 *
 * Covered:
 *  - RecipeList renders the real `GET /api/recipes`, newest first
 *  - RecipeForm create: a mixed pasted-string + structured-object ingredient
 *    body round-trips — the pasted row keeps `raw_text` and is re-parsed
 *    server-side, the object row is stored structured, units are lower-cased
 *    and NOT singularized
 *  - RecipeForm edit / PUT full-replace: a removed row is gone after the real
 *    PUT + refetch, and the server-side ingredient-id churn doesn't break the
 *    table
 *  - a `loc`-mapped `422` lands on the ingredient row that produced it — the
 *    real backend union-tags the path
 *    (`["body","ingredients",N,"RecipeIngredientIn","item"]` + a `…,N,"str"`
 *    sibling); `lib/apiError.ts` `normalizeLoc` collapses it
 *  - RecipeDetail body: ingredients + steps render and the multiplier rescales
 *    a displayed quantity
 */

const PASSWORD = "correct-horse-battery";
/** localStorage key owned by `src/api/client.ts` (`TOKEN_KEY`). */
const TOKEN_KEY = "recipe.token";

const freshUsername = () =>
  `e2e_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 7)}`;

/** Register a fresh user through the real API and seed its bearer token into
 *  localStorage before the first navigation, so every spec starts signed in
 *  without driving the login form (that path is ticket 14's). */
async function signIn(page: Page, request: APIRequestContext): Promise<void> {
  const username = freshUsername();
  const res = await request.post("/api/auth/register", {
    data: { username, password: PASSWORD, code: E2E_REGISTRATION_CODE },
  });
  expect(res.status(), await res.text()).toBe(201);
  const { token } = (await res.json()) as { token: string };
  await page.addInitScript(
    ([key, value]) => window.localStorage.setItem(key, value),
    [TOKEN_KEY, token] as const,
  );
}

/** POST a recipe straight through the API — fixture setup for the read/edit
 *  specs. Returns the created `id`. */
async function createRecipe(
  request: APIRequestContext,
  page: Page,
  body: Record<string, unknown>,
): Promise<number> {
  const token = await page.evaluate(
    (key) => window.localStorage.getItem(key),
    TOKEN_KEY,
  );
  const res = await request.post("/api/recipes", {
    headers: { authorization: `Bearer ${token}` },
    data: body,
  });
  expect(res.status(), await res.text()).toBe(201);
  return ((await res.json()) as { id: number }).id;
}

const row = (page: Page, n: number) => ({
  quantity: page.getByLabel(`Quantity for ingredient ${n}`),
  unit: page.getByLabel(`Unit for ingredient ${n}`),
  item: page.getByLabel(`Item for ingredient ${n}`),
  note: page.getByLabel(`Note for ingredient ${n}`),
});

/** The RecipeDetail ingredients list, scoped away from the availability table
 *  below it (which repeats ingredient names and amounts in its own cells). */
const ingredientsList = (page: Page) =>
  page.getByRole("region", { name: "Ingredients" });
const stepsList = (page: Page) => page.getByRole("region", { name: "Steps" });

test.describe("recipes · real backend", () => {
  test("RecipeList renders the real recipe index, newest first", async ({
    page,
    request,
  }) => {
    await signIn(page, request);
    await page.goto("/");
    // Unique titles — the integration DB is shared across the parallel specs, so
    // assert the relative order of *these two* rows, not an absolute position.
    const tag = Math.random().toString(36).slice(2, 8);
    const older = `Older Bake ${tag}`;
    const newer = `Newer Roast ${tag}`;
    await createRecipe(request, page, { title: older });
    await createRecipe(request, page, { title: newer });
    await page.reload();

    const titles = page.getByRole("heading", { level: 2 });
    await expect(titles.filter({ hasText: older })).toBeVisible();
    await expect(titles.filter({ hasText: newer })).toBeVisible();
    // newest first: the "Newer Roast" row sits above its "Older Bake" sibling
    const names = await titles.allInnerTexts();
    expect(names.indexOf(newer)).toBeLessThan(names.indexOf(older));
    expect(names.indexOf(newer)).toBeGreaterThanOrEqual(0);
  });

  test("create round-trips a mixed pasted + structured ingredient body", async ({
    page,
    request,
  }) => {
    await signIn(page, request);
    await page.goto("/recipes/new");

    await page.getByLabel(/^Title/).fill("Sheet Pan Chicken");

    // row 1 — a hand-entered structured row; "Tbsp." must persist as "tbsp"
    await row(page, 1).quantity.fill("1.5");
    await row(page, 1).unit.fill("Tbsp.");
    await row(page, 1).item.fill("olive oil");

    // rows 2-3 — pasted, left untouched, so they cross as bare strings
    await page.getByRole("button", { name: "Paste ingredients" }).click();
    const dialog = page.getByRole("dialog", { name: "Paste ingredients" });
    await dialog
      .getByLabel("Ingredient lines")
      .fill("2 cups flour\nsalt to taste");
    await dialog.getByRole("button", { name: /^Add \d+ rows?$/ }).click();

    await page.getByRole("button", { name: "Save recipe" }).click();

    // landed on the new recipe's detail page
    await expect(
      page.getByRole("heading", { name: "Sheet Pan Chicken", level: 1 }),
    ).toBeVisible();
    const shown = ingredientsList(page);
    await expect(shown.getByText("olive oil")).toBeVisible();
    await expect(shown.getByText("flour")).toBeVisible();
    await expect(shown.getByText("salt", { exact: true })).toBeVisible();

    // the API row is what really matters — assert the persisted shape
    const id = Number(page.url().split("/recipes/")[1]);
    const token = await page.evaluate(
      (key) => window.localStorage.getItem(key),
      TOKEN_KEY,
    );
    const fetched = await request.get(`/api/recipes/${id}`, {
      headers: { authorization: `Bearer ${token}` },
    });
    const recipe = (await fetched.json()) as {
      ingredients: {
        item: string;
        unit: string | null;
        quantity: number | null;
        raw_text: string | null;
      }[];
    };
    expect(recipe.ingredients).toEqual([
      // structured row: unit lower-cased, trailing "." stripped, NOT singular
      {
        item: "olive oil",
        unit: "tbsp",
        quantity: 1.5,
        raw_text: null,
        id: expect.any(Number),
        position: 0,
        note: null,
        normalized_name: "olive oil",
      },
      // pasted row: server kept the raw line and re-parsed it ("cups" stays)
      {
        item: "flour",
        unit: "cups",
        quantity: 2,
        raw_text: "2 cups flour",
        id: expect.any(Number),
        position: 1,
        note: null,
        normalized_name: "flour",
      },
      {
        item: "salt",
        unit: null,
        quantity: null,
        raw_text: "salt to taste",
        id: expect.any(Number),
        position: 2,
        note: expect.anything(),
        normalized_name: "salt",
      },
    ]);
  });

  test("PUT full-replace drops a removed row and survives the id churn", async ({
    page,
    request,
  }) => {
    await signIn(page, request);
    await page.goto("/");
    const id = await createRecipe(request, page, {
      title: "Three Ingredients",
      ingredients: [
        { item: "flour", quantity: 200, unit: "g" },
        { item: "butter", quantity: 100, unit: "g" },
        { item: "sugar", quantity: 50, unit: "g" },
      ],
    });

    await page.goto(`/recipes/${id}/edit`);
    await expect(row(page, 1).item).toHaveValue("flour");

    // remove the middle row, then save the full replace
    await page
      .getByRole("button", { name: "Remove ingredient 2" })
      .click();
    await page.getByRole("button", { name: "Save changes" }).click();

    // back on detail — butter is gone, the other two remain
    await expect(
      page.getByRole("heading", { name: "Three Ingredients", level: 1 }),
    ).toBeVisible();
    const shown = ingredientsList(page);
    await expect(shown.getByText("flour")).toBeVisible();
    await expect(shown.getByText("sugar")).toBeVisible();
    await expect(shown.getByText("butter")).toHaveCount(0);

    // re-open the editor: it reseeds from the PUT response, no stale row,
    // no crash from the churned server ids
    await page.goto(`/recipes/${id}/edit`);
    await expect(row(page, 1).item).toHaveValue("flour");
    await expect(row(page, 2).item).toHaveValue("sugar");
    await expect(row(page, 3).item).toHaveCount(0);
  });

  test("a loc-mapped 422 lands on the offending ingredient row", async ({
    page,
    request,
  }) => {
    await signIn(page, request);
    await page.goto("/recipes/new");

    await page.getByLabel(/^Title/).fill("Bad Row");
    await row(page, 1).item.fill("good");
    await page.getByRole("button", { name: "Add ingredient" }).click();
    // 201 chars — past the object element's Pydantic max_length (not truncated),
    // and past the form's own client guard (which only checks for a non-empty
    // item). The backend answers with a union-tagged `loc`.
    await row(page, 2).item.fill("x".repeat(201));
    await page.getByRole("button", { name: "Save recipe" }).click();

    // the row-2 item cell carries the error; row 1 is clean; no navigation
    await expect(row(page, 2).item).toHaveAttribute("aria-invalid", "true");
    await expect(row(page, 1).item).not.toHaveAttribute("aria-invalid", "true");
    await expect(
      page.getByText("String should have at most 200 characters"),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/recipes\/new$/);
    // the "Input should be a valid string" losing-branch sibling stays hidden
    await expect(
      page.getByText("Input should be a valid string"),
    ).toHaveCount(0);
  });

  test("RecipeDetail body renders and the multiplier rescales quantities", async ({
    page,
    request,
  }) => {
    await signIn(page, request);
    await page.goto("/");
    const id = await createRecipe(request, page, {
      title: "Scalable Loaf",
      steps: ["Mix", "Bake"],
      ingredients: [{ item: "flour", quantity: 200, unit: "g" }],
    });

    await page.goto(`/recipes/${id}`);
    await expect(
      page.getByRole("heading", { name: "Scalable Loaf", level: 1 }),
    ).toBeVisible();
    const shown = ingredientsList(page);
    await expect(shown.getByText("200 g")).toBeVisible();
    await expect(
      stepsList(page).getByRole("listitem").filter({ hasText: "Mix" }),
    ).toBeVisible();

    // multiplier preset ×2 → the ingredient line rescales to 400 g
    await page
      .getByRole("group", { name: "Multiplier" })
      .getByRole("button", { name: "2", exact: true })
      .click();
    await expect(shown.getByText("400 g")).toBeVisible();
    await expect(shown.getByText("200 g")).toHaveCount(0);
  });
});

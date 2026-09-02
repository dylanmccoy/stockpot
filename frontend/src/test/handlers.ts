// Happy-path MSW handlers — one per docs/spec.md §5 route. These are the
// "backend" for every test and for mock-first development until each screen is
// wired to real calls. Error/edge cases are layered per-test via
// `server.use(...)` from `./errorHandlers`.

import { http, HttpResponse } from "msw";
import type {
  AvailabilityReport,
  CookLogList,
  CookLogRead,
  GroceryListItemRead,
  GroceryListRead,
  InventoryItemRead,
  RecipeRead,
  TokenResponse,
  UserMini,
  UserRead,
} from "../types";

const NOW = "2026-09-01T12:00:00+00:00";

const userMini: UserMini = { id: 1, username: "cook" };
const userRead: UserRead = { id: 1, username: "cook", created_at: NOW };
const tokenResponse: TokenResponse = { token: "test-token", user: userRead };

export const sampleRecipe: RecipeRead = {
  id: 1,
  title: "Buttermilk Pancakes",
  notes: "",
  prep_time: 5,
  cook_time: 10,
  servings: 4,
  cuisine: "American",
  source_url: null,
  tags: ["breakfast"],
  steps: ["Whisk the dry ingredients", "Fold in the wet", "Griddle"],
  created_at: NOW,
  updated_at: NOW,
  photo_path: null,
  created_by: userMini,
  ingredients: [
    {
      id: 10,
      position: 0,
      quantity: 2,
      unit: "cups",
      item: "flour",
      note: null,
      normalized_name: "flour",
      raw_text: null,
    },
    {
      id: 11,
      position: 1,
      quantity: null,
      unit: null,
      item: "salt",
      note: "to taste",
      normalized_name: "salt",
      raw_text: null,
    },
  ],
};

export const sampleAvailability: AvailabilityReport = {
  recipe_id: 1,
  multiplier: 1,
  all_available: true,
  lines: [],
};

export const sampleCookLog: CookLogRead = {
  id: 1,
  recipe_id: 1,
  recipe_title: "Buttermilk Pancakes",
  multiplier: 1,
  deducted: false,
  cooked_at: NOW,
  cooked_by: userMini,
  deductions: [],
};

const sampleCookLogList: CookLogList = {
  items: [sampleCookLog],
  total: 1,
  limit: 50,
  offset: 0,
};

export const sampleInventoryItem: InventoryItemRead = {
  id: 1,
  item: "Flour",
  normalized_name: "flour",
  match_name: "flour",
  unit_bucket: "mass",
  quantity_base: 1000,
  display_unit: "g",
  display_quantity: 1000,
  updated_at: NOW,
};

export const sampleGroceryItem: GroceryListItemRead = {
  id: 1,
  item: "flour",
  normalized_name: "flour",
  quantity: 250,
  unit: "g",
  checked: false,
  checked_at: null,
  submitted_at: null,
  source: "generated",
  nettable: true,
  added_to_inventory: false,
  applied_quantity: null,
  applied_unit: null,
};

export const sampleGroceryList: GroceryListRead = {
  id: 1,
  name: "Groceries 2026-09-01",
  status: "active",
  source_recipe_ids: [1],
  created_at: NOW,
  created_by: userMini,
  items: [sampleGroceryItem],
};

const noContent = () => new HttpResponse(null, { status: 204 });

export const handlers = [
  // health
  http.get("/api/health", () => HttpResponse.json({ status: "ok" })),

  // auth
  http.post("/api/auth/register", () =>
    HttpResponse.json(tokenResponse, { status: 201 }),
  ),
  http.post("/api/auth/login", () => HttpResponse.json(tokenResponse)),
  http.post("/api/auth/logout", noContent),
  http.get("/api/auth/me", () => HttpResponse.json(userRead)),
  http.post("/api/auth/change-password", () =>
    HttpResponse.json(tokenResponse),
  ),

  // recipes
  http.post("/api/recipes", () =>
    HttpResponse.json(sampleRecipe, { status: 201 }),
  ),
  http.get("/api/recipes", () => HttpResponse.json([sampleRecipe])),
  http.get("/api/recipes/:id", () => HttpResponse.json(sampleRecipe)),
  http.put("/api/recipes/:id", () => HttpResponse.json(sampleRecipe)),
  http.delete("/api/recipes/:id", noContent),
  http.get("/api/recipes/:id/availability", () =>
    HttpResponse.json(sampleAvailability),
  ),
  http.post("/api/recipes/:id/cook", () =>
    HttpResponse.json(sampleCookLog, { status: 201 }),
  ),
  http.get("/api/recipes/:id/cook-logs", () =>
    HttpResponse.json([sampleCookLog]),
  ),

  // cook-logs (global)
  http.get("/api/cook-logs", () => HttpResponse.json(sampleCookLogList)),
  http.get("/api/cook-logs/:logId", () => HttpResponse.json(sampleCookLog)),

  // inventory
  http.get("/api/inventory", () => HttpResponse.json([sampleInventoryItem])),
  http.post("/api/inventory", () =>
    HttpResponse.json(sampleInventoryItem, { status: 201 }),
  ),
  http.patch("/api/inventory/:id", () =>
    HttpResponse.json(sampleInventoryItem),
  ),
  http.delete("/api/inventory/:id", noContent),

  // grocery
  http.post("/api/grocery", () =>
    HttpResponse.json(sampleGroceryList, { status: 201 }),
  ),
  http.get("/api/grocery", () => HttpResponse.json([sampleGroceryList])),
  http.get("/api/grocery/:id", () => HttpResponse.json(sampleGroceryList)),
  http.delete("/api/grocery/:id", noContent),
  http.post("/api/grocery/:id/items", () =>
    HttpResponse.json(sampleGroceryItem, { status: 201 }),
  ),
  http.patch("/api/grocery/:id/items/:itemId", () =>
    HttpResponse.json(sampleGroceryItem),
  ),
  http.delete("/api/grocery/:id/items/:itemId", noContent),
  http.post("/api/grocery/:id/submit", () =>
    HttpResponse.json(sampleGroceryList),
  ),
  http.post("/api/grocery/:id/archive", () =>
    HttpResponse.json({ ...sampleGroceryList, status: "archived" }),
  ),
];

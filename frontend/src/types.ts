// Hand-maintained mirror of ../../docs/spec.md §5 (the backend API contract) and
// docs/frontend/spec.md §5. NOT generated (R-1). When docs/spec.md changes,
// update this file and docs/frontend/spec.md §5 together, then diff both against
// the backend section that moved.
//
// Last diffed against docs/spec.md §0, §5 on 2026-09-02 (backend Phase 2 merged).
// §5.2 (Recipes CRUD) re-diffed against the merged backend on 2026-09-03
// (frontend ticket 15 / plan Phase 3 gate): request + response shapes match
// field-for-field, no drift. The one integration gap was error *shape*, not a
// type: Pydantic wraps a bad `ingredients` object element's `loc` with the
// union branch tag (`["body","ingredients",N,"RecipeIngredientIn","item"]`) —
// reconciled in lib/apiError.ts (`normalizeLoc`), not here.
// §5.3 (availability) + §5.5 (inventory) re-diffed 2026-09-03 against backend
// Phase 4 as merged (ticket 16).

// ── Shared ──────────────────────────────────────────────────────────────────

/** tz-aware UTC ISO 8601, e.g. "2026-09-01T12:34:56+00:00". */
export type ISODateTime = string;

export interface UserMini {
  id: number;
  username: string;
}

export interface UserRead {
  id: number;
  username: string;
  created_at: ISODateTime;
}

export interface TokenResponse {
  token: string;
  user: UserRead;
}

/** A single FastAPI validation error entry (`detail` array element). */
export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

/**
 * The normalized error shape. `api/client.ts` throws an `ApiError` instance (an
 * `Error` subclass) that structurally satisfies this interface.
 */
export interface ApiError {
  status: number;
  detail: string | ValidationIssue[];
}

// ── Auth — /api/auth ────────────────────────────────────────────────────────

export interface RegisterRequest {
  username: string; // ^[A-Za-z0-9_.-]{3,50}$
  password: string; // 8..128
  code?: string | null; // required iff the server has a registration code set
}

export interface LoginRequest {
  username: string;
  password: string;
}

// docs/spec.md §5.1 also defines POST /api/auth/change-password
// (ChangePasswordRequest). No v1 screen surfaces it, so it is intentionally
// not mirrored here — matching docs/frontend/spec.md §5, which omits it too
// (R-1: this file and §5 stay in lockstep).

// ── Recipes — /api/recipes ─────────────────────────────────────────────────

export interface RecipeIngredientIn {
  quantity?: number | null; // > 0 when set, finite; null => to-taste
  unit?: string | null; // <= 30
  item?: string | null; // 1..200; REQUIRED for an object element
  note?: string | null; // <= 200
}

/** An `ingredients` element is either a structured object or a bare pasted line. */
export type RecipeIngredientElement = RecipeIngredientIn | string;

export interface RecipeIngredientRead {
  id: number;
  position: number;
  quantity: number | null;
  unit: string | null;
  item: string;
  note: string | null;
  normalized_name: string;
  raw_text: string | null; // set only for pasted-string rows
}

export interface RecipeBase {
  title: string; // 1..200
  notes: string; // default ""
  prep_time: number | null; // >= 0 minutes
  cook_time: number | null; // >= 0 minutes
  servings: number | null; // > 0 finite
  cuisine: string | null; // <= 100
  source_url: string | null; // <= 500, NOT validated
  tags: string[]; // <= 100 items, each <= 50; stored as-sent
  steps: string[]; // <= 100 items, each <= 2000; ordered
}

export type RecipeCreate = RecipeBase & {
  ingredients: RecipeIngredientElement[];
};

/** PUT fully replaces the recipe, including its ingredient rows. */
export type RecipeUpdate = RecipeCreate;

export type RecipeRead = RecipeBase & {
  id: number;
  created_at: ISODateTime;
  updated_at: ISODateTime;
  photo_path: string | null; // always null in v1
  created_by: UserMini | null;
  ingredients: RecipeIngredientRead[]; // ordered by position
};

// ── Availability — GET /api/recipes/{id}/availability?multiplier= ───────────

export type AvailabilityStatus =
  "ok" | "have_uncertain" | "short" | "missing" | "to_taste";

export interface AvailabilityLine {
  ingredient_id: number; // the recipe ingredient row this line is for
  item: string;
  need: number | null; // this row's own quantity * multiplier, canonical unit; null for to_taste
  need_unit: string; // group canonical unit; always set, even on a to_taste line
  group_key: string; // `${normalized_name}|${bucket}` — identical across group members
  group_unit: string;
  group_need: number | null;
  group_have: number | null; // null only for to_taste
  group_short: number | null; // null only for to_taste
  status: AvailabilityStatus;
  nettable: boolean;
}

export interface AvailabilityReport {
  recipe_id: number;
  multiplier: number;
  lines: AvailabilityLine[];
  all_available: boolean; // true iff every non-to_taste line is "ok" (empty / all-to-taste also true)
}

// ── Cook + made-history — /api/recipes/{id}/cook, /api/cook-logs ────────────

export interface CookRequest {
  multiplier?: number; // > 0 finite, default 1
  deduct?: boolean; // default true
}

export type CookDeductionReason =
  | "ok"
  | "clamped to 0"
  | "to taste"
  | "not in inventory"
  | "have uncertain (incompatible unit)";

/** Every key present; `null` where the branch doesn't apply. `item`/`applied`/`reason` never null. */
export interface CookDeductionRead {
  item: string;
  normalized_name: string | null;
  requested: number | null; // canonical; first row of a group only, else null
  requested_unit: string | null;
  deducted: number | null;
  deducted_unit: string | null;
  inventory_unit: string | null;
  before: number | null;
  after: number | null;
  applied: boolean;
  reason: CookDeductionReason;
}

export interface CookLogRead {
  id: number;
  recipe_id: number | null; // null once the recipe is deleted
  recipe_title: string; // snapshot, survives deletion
  multiplier: number;
  deducted: boolean;
  cooked_at: ISODateTime;
  cooked_by: UserMini | null;
  deductions: CookDeductionRead[]; // [] when deduct=false
}

export interface CookLogList {
  items: CookLogRead[];
  total: number;
  limit: number;
  offset: number;
}

// ── Inventory — /api/inventory ─────────────────────────────────────────────

export interface InventoryItemCreate {
  item: string; // 1..200
  quantity: number; // >= 0 finite
  unit?: string | null; // <= 30; null => COUNT bucket
  match_name?: string | null; // <= 200; server normalizes; "" after normalize => 422
}

export interface InventoryItemUpdate {
  item?: string | null; // null => 422
  match_name?: string | null; // null => 422; stored normalized; collision => 409
  quantity?: number | null; // null => 422; requires `unit` also present => else 422
  unit?: string | null; // must keep the same bucket => else 422
}

export interface InventoryItemRead {
  id: number;
  item: string;
  normalized_name: string;
  match_name: string;
  unit_bucket: string; // "mass" | "volume" | "count" | "opaque:<token>"
  quantity_base: number; // source of truth, canonical unit
  display_unit: string | null;
  display_quantity: number; // raw float; == quantity_base when display_unit null/opaque
  updated_at: ISODateTime;
}

// ── Grocery — /api/grocery ────────────────────────────────────────────────

export interface GroceryListCreate {
  name?: string | null; // default "Groceries <UTC date>"
  recipe_ids: number[]; // non-empty, unique, all must exist => else 422
  multipliers?: Record<number, number>; // each > 0 finite; keys subset of recipe_ids => else 422
}

export interface GroceryListItemIn {
  item: string; // 1..200
  quantity?: number | null; // > 0 when set, finite
  unit?: string | null; // <= 30
}

export interface GroceryListItemUpdate {
  checked?: boolean | null;
  item?: string | null;
  quantity?: number | null; // quantity & unit are an ATOMIC PAIR — send both or neither
  unit?: string | null;
}

export type GroceryLineSource = "generated" | "manual";

export interface GroceryListItemRead {
  id: number;
  item: string;
  normalized_name: string;
  quantity: number | null;
  unit: string | null;
  checked: boolean;
  checked_at: ISODateTime | null;
  submitted_at: ISODateTime | null;
  source: GroceryLineSource;
  nettable: boolean; // false => true shortfall uncertain — inform the shopper
  added_to_inventory: boolean; // freeze flag — a frozen line rejects PATCH/DELETE with 409
  applied_quantity: number | null;
  applied_unit: string | null;
}

export type GroceryListStatus = "active" | "archived";

export interface GroceryListRead {
  id: number;
  name: string;
  status: GroceryListStatus;
  source_recipe_ids: number[];
  created_at: ISODateTime;
  created_by: UserMini | null;
  items: GroceryListItemRead[]; // ordered by id
}

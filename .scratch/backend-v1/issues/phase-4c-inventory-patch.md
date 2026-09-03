# phase-4c: Inventory PATCH — absolute replacement + N5

**What to build:** An existing inventory row can be edited through
`PATCH /api/inventory/{id}` — absolute quantity set, display-unit preference,
`item` rename, and canonical `match_name` re-point — with every guard rail from
`spec.md` §5.5.

**Blocked by:** `phase-4b`.

**Status:** in-review

**Files:** edit `backend/app/routers/inventory.py`, `backend/app/schemas/inventory.py`, `backend/tests/test_inventory.py`, `backend/tests/test_validation.py`.

**Spec:** `docs/spec.md` §5.5 (inventory `PATCH` — the `model_fields_set` guard rails, N5), §1 "inventory_items", §2.2 (`normalize_unit_token`, `bucket_of`, `to_base`/`from_base`). Read only these sections.

**Tests:** `cd backend && uv run pytest tests/test_inventory.py tests/test_validation.py`, then full `uv run pytest`.

- [x] `PATCH /api/inventory/{id}` -> `200 InventoryItemRead`; `404` if the row is
      absent; driven by `body.model_fields_set` (`S`) per §5.5:
  - `S` empty -> `200` no-op (return the row unchanged).
  - `item` / `match_name` / `quantity` present-and-null -> `422 "{f} cannot be null"`.
  - `quantity` in `S` and `unit` not in `S` -> `422 "unit is required when setting quantity"` (decision S2).
  - `unit` in `S` and `bucket_of(normalize_unit_token(body.unit)) != row.unit_bucket`
    -> `422 "unit changes the bucket; remove and re-add"` (covers `unit:null` on a
    non-COUNT row -> `422`; `unit:null` on a COUNT row -> ok).
  - `match_name` in `S`: `nm = normalize_name(body.match_name)`; `nm == ""` ->
    `422 "match_name normalizes to empty"`; a **different** row on
    `(nm, row.unit_bucket)` -> `409 "match_name already in use for this bucket"`.
- [x] Apply inside the single `BEGIN IMMEDIATE` transaction: `quantity` ->
      absolute canonical set (`max(0.0)`; opaque bucket or `normalize_unit_token`
      -> `None` keeps the raw amount, else `to_base`); `unit` -> `display_unit`
      preference only; `match_name` -> `nm`; `item` -> set + recompute
      `normalized_name`; `row.updated_at = _utcnow()`.
- [x] `InventoryItemRead.display_quantity` recomputed via `from_base` on return
      (equals `quantity_base` for an opaque bucket or a null `display_unit`).
- [x] `test_inventory.py` extended: every §5.5 example row; `PATCH {unit:"kg"}`
      display-only (`quantity_base` untouched, `display_quantity` changes);
      `PATCH {quantity:200}` with no unit -> `422`; `PATCH {unit:"can"}` on a mass
      row -> `422`; `PATCH {unit:null}` on a non-COUNT row -> `422`, on a COUNT
      row -> `200`; `PATCH {item:null}` / `{quantity:null}` / `{match_name:null}`
      -> `422`; `PATCH {}` -> `200` no-op; `PATCH {match_name:...}` whose
      normalized value collides with a different `(match_name, unit_bucket)` row
      -> `409`; `" Flour "` / `"FLOUR"` stored as `flour`; editing `match_name`
      re-points recipe/inventory matching; `add -> cook -> GET` shows
      `display_quantity` recomputed from the reduced `quantity_base`.
      *(`match_name` re-point and `add -> reduce -> GET` are shown via
      PATCH-as-reducer + additive-`POST`-merges-after-repoint — `cook` and
      `availability` land in phases 5 / 4d.)*
- [x] `test_validation.py`: inventory `PATCH` `quantity` negative / `inf` / `nan`
      -> `422`. *`0` -> `200`, not `422`: spec §5.5 applies `max(body.quantity,
      0.0)` and `POST` accepts `0` — this ticket bullet contradicts its own cited
      section. Covered by `test_patch_quantity_zero_is_accepted`; both review
      axes agreed the spec wins. No spec edit (spec was followed, not changed).*
- [~] `cd backend && uv run pytest` green — 517 passed / 64 failed. All 64 are
      the `test_inventory_math.py` R-7 locked oracles for `check_availability` /
      `deduct_calc`, which `backend/CLAUDE.md` says stay non-green until phases
      4d / 4e. Pre-existing (main: 65 failed); this branch adds 28 passing and
      removes 1 failure. Scoped `tests/test_inventory.py tests/test_validation.py`
      is fully green.
- [x] `docs/phases/phase-4.md` PATCH-related Work / Verification checkboxes ticked
      (Work "additive POST, absolute PATCH…", Work "Add `test_inventory.py`…",
      Verification "POST is additive, PATCH is absolute…"). The
      "`uv run pytest` passes" verification box stays unticked — unsatisfiable
      until 4e per the R-7 gate.

## Comments

**2026-09-03** — implemented on branch `feat/backend-v1-phase-4c`, worktree
`.claude/worktrees/backend-v1-phase-4c/`.

- `PATCH /api/inventory/{id}` added to `routers/inventory.py` as a near
  line-for-line transcription of the §5.5 apply block; `model_fields_set` gate,
  the four `422`s, the `409` `(nm, unit_bucket)` collision, and the absolute
  canonical `quantity` set all in the request transaction (`db.flush()`,
  `TransactionRoute` commits).
- `InventoryItemUpdate` docstring updated; no schema shape change (the PATCH
  schema was already defined in phase-4b).
- Tests: ~20 cases in `test_inventory.py` (full §5.5 example table + branch
  coverage) and a parametrized `PATCH` row in `test_validation.py`.
- `/code-review` (Standards + Spec): no hard findings. Actioned — extracted
  `_get_or_404` in `routers/inventory.py` (was verbatim in `update` + `delete`),
  matching the `recipes.py` helper of the same name. Skipped (spec-mandated):
  the quantity->base apply logic is open-coded in the router because §5.5 writes
  it that way and the ticket's **Files:** does not include `inventory_math.py`.
  Noted, not actioned: `InventoryItemUpdate.item` has no `min_length`, so
  `PATCH {"item": "  "}` stores an empty `item` / `normalized_name` — this
  matches the §5.5 schema (`item: str | None  # <= 200`, no lower bound and no
  empty guard for PATCH `item`).

# phase-4c: Inventory PATCH — absolute replacement + N5

**What to build:** An existing inventory row can be edited through
`PATCH /api/inventory/{id}` — absolute quantity set, display-unit preference,
`item` rename, and canonical `match_name` re-point — with every guard rail from
`spec.md` §5.5.

**Blocked by:** `phase-4b`.

**Status:** ready-for-agent

- [ ] `PATCH /api/inventory/{id}` -> `200 InventoryItemRead`; `404` if the row is
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
- [ ] Apply inside the single `BEGIN IMMEDIATE` transaction: `quantity` ->
      absolute canonical set (`max(0.0)`; opaque bucket or `normalize_unit_token`
      -> `None` keeps the raw amount, else `to_base`); `unit` -> `display_unit`
      preference only; `match_name` -> `nm`; `item` -> set + recompute
      `normalized_name`; `row.updated_at = _utcnow()`.
- [ ] `InventoryItemRead.display_quantity` recomputed via `from_base` on return
      (equals `quantity_base` for an opaque bucket or a null `display_unit`).
- [ ] `test_inventory.py` extended: every §5.5 example row; `PATCH {unit:"kg"}`
      display-only (`quantity_base` untouched, `display_quantity` changes);
      `PATCH {quantity:200}` with no unit -> `422`; `PATCH {unit:"can"}` on a mass
      row -> `422`; `PATCH {unit:null}` on a non-COUNT row -> `422`, on a COUNT
      row -> `200`; `PATCH {item:null}` / `{quantity:null}` / `{match_name:null}`
      -> `422`; `PATCH {}` -> `200` no-op; `PATCH {match_name:...}` whose
      normalized value collides with a different `(match_name, unit_bucket)` row
      -> `409`; `" Flour "` / `"FLOUR"` stored as `flour`; editing `match_name`
      re-points recipe/inventory matching; `add -> cook -> GET` shows
      `display_quantity` recomputed from the reduced `quantity_base`.
- [ ] `test_validation.py`: inventory `PATCH` `quantity` negative / `0` / `inf` /
      `nan` -> `422`.
- [ ] `cd backend && uv run pytest` green.
- [ ] `docs/phases/phase-4.md` PATCH-related Work / Verification checkboxes ticked.

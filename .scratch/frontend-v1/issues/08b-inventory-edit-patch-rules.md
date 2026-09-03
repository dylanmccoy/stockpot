# 08b: Inventory — inline edit, PATCH rules, match_name editor (vs MSW)

**What to build:** Editing a stock quantity and its match name under the backend's PATCH constraints, with every rejection shown inline. After this ticket a user can edit a quantity inline (confirming the unit), is stopped client-side before a guaranteed-reject PATCH, and can edit the prominent match name with an in-bucket collision surfaced inline.

**Blocked by:** 08a.

**Status:** done

**Files:** edit `frontend/src/pages/Inventory.tsx`, `frontend/src/pages/Inventory.test.tsx`, `frontend/src/api/inventory.ts` (PATCH adapter).

**Spec:** `docs/frontend/spec.md` §10.9 (inline edit + `match_name` editor), §5 "Inventory" (PATCH rules, mirror of `docs/spec.md` §5.5), §6 (the `409` surface). Read only these sections.

**Tests:** `cd frontend && npm run test:run -- src/pages/Inventory.test.tsx`.

- [x] Inline quantity edit requires confirming the unit on save. — the edit panel always carries a `unit` field and `buildInventoryPatch` rides `unit` alongside every `quantity` change (decision S2); clearing the unit on a non-COUNT row blocks with "Confirm the unit for the new quantity."
- [x] Client-side rule enforcement before PATCH: a quantity change forces a unit; a unit cannot change to one in a different bucket; a null unit is rejected for a non-COUNT item. — `validateEditDraft` + `bucketForUnit` (mirror of `backend/app/units.py` bucket map), all three rejections block the PATCH with an inline reason.
- [x] `match_name` editor is prominent, saves in normalized form, has a short hint explaining it links inventory to recipe ingredients, and shows an inline error on an in-bucket collision (`409`). — first field in the panel, boxed/emphasised; hint names the recipe↔inventory link; the server-normalized value shows in the table after save; a `409 "match_name already in use for this bucket"` renders inline on the field (verbatim).
- [x] Flow test (vs MSW): the three client-side rejections each block the PATCH and show the inline reason; a valid `{ quantity, unit }` PATCH updates the row; a `match_name` `409` shows inline. — `describe("Inventory edit panel")` in `Inventory.test.tsx`.

**Refs:** `docs/frontend/spec.md` §10.9; plan Phase 4. Split from ticket 08.

## Comments

- Branch `feat/frontend-v1-08b`, worktree `.claude/worktrees/frontend-v1-08b`.
- `frontend/src/api/inventory.ts` needed no change — `update` (PATCH adapter) was
  already on `inventoryApi` from 08a. Only `Inventory.tsx` + `.test.tsx` +
  `.module.css`.
- Pure seams exported for tests: `bucketForUnit` (unit token → `unit_bucket`,
  incl. `opaque:<token>` and `null` for unknown-so-defer), `sameBucketUnits`
  (canonical picklist per bucket, for the hint), `editDraftFrom` (row →
  pre-filled draft, quantity snapped to 6 s.f. so a raw float never lands in the
  input), `validateEditDraft` (the three §5.5 client guards), `buildInventoryPatch`
  (draft → PATCH body keyed on what changed; `unit` rides every `quantity`
  change). `validateEditDraft` and `buildInventoryPatch` share one private
  `diffEditDraft` so "what changed" can't drift between them.
- **Edit UI is an on-page panel, not a modal** (`<section role="region">` between
  the add form and the table) — `docs/frontend/spec.md` §10.9 says "**Edit** →
  inline `PATCH`" and reserves `Dialog` for delete. Focus moves to the first
  field on open and back to the row's Edit button on cancel/close (§9).
- **Unit is a free-text `Input`, not a same-bucket `Select`.** §10.9's "the field
  offers only same-bucket units" is met as a hint listing the bucket's units;
  kept editable so the client-side cross-bucket guard is reachable through the UI
  (the ticket's flow-test AC requires driving that rejection).
- `409` routing: match_name-collision `409` → inline on the field (verbatim);
  generic `409 "conflict"` → toast + refetch + close panel; string `422`
  (e.g. "unit changes the bucket…") → form-level banner. Matches §6 catalog.
- Deliberately **not** done: a client `normalize_name` mirror for a live
  normalized preview of `match_name` (server is the source of truth per §5;
  normalized value shows on the table after save); a shared `lib/units.ts`
  extraction merging this bucket map with `lib/parseIngredientLine.ts`'s token
  Set (different shapes — flat "is-a-unit" Set vs mass/volume/count map; the
  singularize rule is aligned and cross-referenced in a comment).
- `/code-review` (Standards + Spec) run; actioned findings: converted modal →
  inline panel; extracted `diffEditDraft` (killed the validator/builder
  duplication); removed a `matchNameCollisionMessage` middle-man; renamed
  `unitBucket`→`bucketForUnit` / `UNIT_BUCKET`→`SYNONYM_BUCKET` (name collision
  with the `unit_bucket` field); aligned the `normalizeUnitToken` singularize
  regex with the `parseIngredientLine.ts` sibling; snapped the quantity prefill
  to 6 s.f.; unit hint now lists same-bucket units. Skipped (deliberate): the
  `lib/units.ts` extraction and the `normalize_name` mirror (above); decision-S2
  living in both the guard and the builder is inherent and `diffEditDraft`
  already shares the detection.
- `npm run test:run` (269 pass), `npm run typecheck`, `npm run lint`,
  `npm run build` all green.

# 06a: Recipe form scaffold + create (vs MSW)

**What to build:** Capturing a full structured recipe from scratch through one form, with validation errors landing where they belong. After this ticket a user can open `/recipes/new`, fill every field including ordered steps and a structured ingredient table, save via POST, and land on the new recipe; a rejected save shows field errors under the offending inputs and whole-request rejections as a form-level banner.

**Blocked by:** 05a, 03.

**Status:** done

- [ ] `/recipes/new` renders one form: title, cuisine, servings, prep time, cook time, source URL, tags, notes, ordered steps.
- [ ] Steps: add, remove, reorder with up/down buttons (keyboard-safe; no drag).
- [ ] Ingredients: one unified editable table, rows with quantity, unit, item, optional note; add / remove / reorder rows; a blank quantity means "to taste".
- [ ] Save POSTs the recipe; on success navigate to `/recipes/:id`.
- [ ] `source_url` renders as an "open link" when it is a valid URL, while still accepting arbitrary text.
- [ ] Field-level `422` errors render under the offending input, including which ingredient row (array index in `loc`). A whole-request rejection (e.g. an ingredient row with no item text) renders as a form-level banner.
- [ ] `/recipes/:id/edit` stays on the placeholder page (`mode="edit"` branch) — pre-fill and PUT full-replace are ticket 06c. No edit-mode tests here.
- [ ] Flow test (vs MSW): create a recipe with structured rows → correct POST body + redirect; a `422` with `loc`-mapped issues lands on the right fields; a string `detail` renders as the banner.

**Refs:** `docs/frontend/spec.md` §10.3, §7.3; plan Phase 3. Split from ticket 06.

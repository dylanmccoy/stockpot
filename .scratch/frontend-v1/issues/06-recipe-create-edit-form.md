# 06: Recipe create / edit form (vs MSW)

**What to build:** Creating a new recipe and editing an existing one through a single form, including pasting a block of ingredient lines and fixing the parse before saving. After this ticket a user can capture a full structured recipe, paste-and-append ingredient rows with a preview, edit an existing recipe with the form pre-filled, and see validation errors under the offending field.

**Blocked by:** 05, 03.

**Status:** ready-for-agent

- [ ] `/recipes/new` and `/recipes/:id/edit` render one form: title, cuisine, servings, prep time, cook time, source URL, tags, notes, ordered steps.
- [ ] Steps: add, remove, reorder with up/down buttons (keyboard-safe; no drag).
- [ ] Ingredients: one unified editable table, rows with quantity, unit, item, optional note; add / remove / reorder rows; a blank quantity means "to taste".
- [ ] "Paste ingredients" action runs `parseIngredients`, shows a parsed-row preview (quantity / unit / item / note), and appends the parsed rows on confirm; the user can hand-fix a misparse before saving.
- [ ] Edit pre-fills the form from the current recipe. Save uses PUT full-replace so removed rows actually go away.
- [ ] Pasted-untouched rows are sent as strings; hand-entered/edited rows as objects, in one mixed `ingredients` array.
- [ ] Field-level `422` errors render under the offending input, including which ingredient row (array index in `loc`). A whole-request rejection (e.g. an ingredient row with no item text) renders as a form-level banner.
- [ ] `source_url` renders as an "open link" when it is a valid URL, while still accepting arbitrary text.
- [ ] Flow tests (vs MSW): create with mixed pasted-string + structured-object rows in one save; edit full-replace clears removed rows; `loc`-mapped errors land on the right fields.

**Refs:** `docs/frontend/spec.md` §7.1, §10.3; plan Phase 3.

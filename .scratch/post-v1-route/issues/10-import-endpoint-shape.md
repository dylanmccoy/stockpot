# What shape should the recipe-import endpoint have?

Type: grilling
Status: resolved
Blocked by: —
Parent: ../map.md

## Question

The owner has confirmed the import API in `docs/features.md` is not fixed. The
specced shape has one endpoint carrying a `save` flag, returning 200
`RecipeImportPreview` or 201 `RecipeRead` depending on the flag. An alternative
emerged from reading the existing code.

**Alternative: the preview is a create body.** `POST /api/recipes/import`
becomes read-only and returns a `RecipeCreate`-shaped payload whose
`ingredients` is `list[str]` — the scraped lines verbatim. The client shows it,
the person corrects it, and the app posts it to the existing
`POST /api/recipes`.

Three facts in the current code make this cheap:

| Fact | Location |
|---|---|
| `RecipeCreate.ingredients: list[RecipeIngredientIn \| str]` — a string element is a pasted line, parsed server-side | `backend/app/schemas/recipe.py:64` |
| `source_url` already exists on the model and on `RecipeBase` | `models.py:68`, `schemas/recipe.py:57` |
| `raw_text` is populated only for string elements, NULL for structured ones | `models.py:117-119` |

Decide:

1. **Read-only import, or keep the `save` flag.** The read-only shape deletes
   the 201 branch, the second write path, and the `ImportIngredient` DTO. It
   also avoids a real collision: `ImportIngredient` = `RecipeIngredientIn` +
   `{raw_text, normalized_name}` **cannot be posted back** to
   `POST /api/recipes`, because `RecipeIngredientIn` carries `extra="forbid"`
   — the only schema in the API that does, added deliberately by decision Q11.
2. **Whether one endpoint accepts a website address *or* a pasted page**
   (`{url?, html?}`, exactly one). This folds ticket 06's fallback into the
   main endpoint with the same parser rather than adding a second route.
   Measured need: 6/6 Substack sources and 2/20 live fetches (Cloudflare 403)
   cannot be solved by any parser.
3. **What the app treats as a required field.** Title, ingredients and steps
   are what a recipe needs. `yields`, `total_time`, `ratings` and `author` are
   not. Every library accessor raises when its field is absent, so this
   decision is what separates a real import failure from a normal partial
   result.
4. **Where `ingredient_groups()` output goes.** The library returns
   `[IngredientGroup(ingredients, purpose)]`, which is what stops
   `For the sauce:` becoming a false ingredient. `RecipeCreate` has no group
   concept, so the purpose text needs a home or a deliberate discard.

## Constraints

- Keep `fetch_bytes` as the only network call, with the SSRF guard and the
  `#R-def` hardening items intact.
- No schema change. The `recipes` and `recipe_ingredients` tables already carry
  `source_url` and `raw_text`, so the Alembic gate must stay in front of the
  inventory-upkeep track.
- Standing constraint: preserve raw source evidence when an import creates an
  editable record.
- `raw_text` is `String(300)` and the paste path truncates to 200 characters.
  Check real scraped lines against that limit before it becomes a rule.

## Note

Ticket 09 (preview screen and placement) is blocked by this one. Decide the
endpoint's shape first, then prototype the screen against it.

## Comments

**2026-09-05 — owner, on item 2.** Accept a pasted page directly, as an
optional path. The endpoint takes a website address or a pasted document, and
one parser handles both. This is not a second route and not a second parsing
path.

Open sub-question this raises: *what* does the person paste?

- **Raw HTML** is what the parser wants, and it is what Tandoor accepts. On a
  desktop browser it is view-source then copy. On a phone it is awkward — and
  the deployment spec's primary device is a household phone on cellular data.
- **A JSON-LD block** is smaller but requires the person to find it.
- **Rendered page text** is the easy thing to copy on a phone, but
  `recipe-scrapers` cannot parse it; it needs markup.

So the paste path may cover desktop well and phones badly. Decide whether that
is acceptable, or whether the phone case needs something else — for example
sharing the page URL from the browser and retrying the fetch from a different
network path.

## Answer

**1. Read-only import; the preview is a create body.**
`POST /api/recipes/import` never writes. It returns a `RecipeCreate`-shaped
payload with `ingredients: list[str]` — the scraped lines verbatim. The person
corrects it, then the app posts it to the existing `POST /api/recipes`.

Deleted from the spec: the `save` flag, the 201 `RecipeRead` branch, the second
write path and its tests, and the `ImportIngredient` DTO. The
`extra="forbid"` collision on `RecipeIngredientIn` disappears with the DTO.
`raw_text` is populated by the string-element path that already does it, and
`source_url` already exists on `RecipeBase`, so provenance persists for free.
No schema change; the Alembic gate stays in front of the inventory-upkeep track.

**2. One endpoint takes a website address or a pasted page.**
`{url?, html?}`, exactly one, one parser for both. Owner's decision. This is
ticket 06's fallback, folded in rather than bolted on.

*Known limitation, my call — override if wrong:* raw HTML is a desktop gesture
(view-source, copy). On a phone it is awkward, and rendered page text cannot be
parsed because the parser needs markup. Accept desktop-good / phone-poor for
now. The failures this path exists for — newsletter sources and bot-protected
sites — should be rare enough that "finish this one on a laptop" is tolerable.
Revisit if it actually bites; ticket 03 is where that evidence arrives.

**3. A scrape succeeds when it has ingredients and steps.**
Title is not required — the person adds it easily. `yields`, `total_time`,
`ratings` and `author` are never required, so a missing one is not a failure.
This is the single biggest lever on the useful-import rate, because every
library accessor raises when its field is absent.

Consequence to carry into ticket 09: `RecipeCreate.title` has `min_length=1`,
so a title-less preview cannot be saved until the person types a title. The
preview screen must enforce that. Note this inverts decision Q5, where `title`
is the only required field and ingredients/steps may be empty — the two rules
gate different things and both stand.

**4. Use `ingredient_groups()`; keep the clean lines, discard the purpose text.**
The main value of the grouped call is negative: `For the sauce:` never becomes
a false ingredient. Take that. The positive value — knowing which ingredients
belong to the sauce — has nowhere to live: `RecipeCreate` has no group concept
and adding one is a schema change, which this ticket's constraints rule out.

So: the preview may show the groups client-side, the save flattens to
`list[str]`, and the purpose text is not persisted. Record it in `features.md`
as a deliberate loss. Revisiting it means a schema change, which puts it behind
the Alembic gate — that is the honest reason to leave it now, not that it is
worthless.

### Follow-up this creates

`docs/features.md` § "URL import (fast-follow)" is now wrong in two ways: the
API shape above supersedes it, and three library facts in it are wrong against
15.12.0 (`wild_mode=` deprecated, the two-pass retry is unnecessary, every
accessor can raise). Rewrite that section when the track is handed off.

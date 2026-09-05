# Does URL import preview before saving, and where does it live?

Type: prototype
Status: open
Blocked by: 10
Parent: ../map.md

## Question

Graduated from the map's fog once ticket 02 established how reliable scraping
actually is: usable ingredients on 87.7% of pages, exact ingredient lines on
75.9%, and partial results as the normal shape rather than an edge case.

That accuracy profile is the whole design problem. It is high enough that
import is worth building, and low enough that roughly one recipe in four
arrives needing a human to fix something before it is worth keeping.

Decide, by building something rough enough to react to:

1. **Preview or save-direct.** `features.md` already specs both
   (`POST /api/recipes/import {url, save?}` → 200 preview, or 201 `RecipeRead`
   when `save=true`). Which one does the interface actually use? Save-direct
   plus "edit it afterwards" reuses the existing edit form and adds no new
   screen; preview-then-confirm catches errors before they enter the recipe
   box, at the cost of a screen that is nearly a second recipe form.
2. **Where import starts.** A field on the existing `RecipeForm`, a distinct
   action on the recipe list, or its own route.
3. **How a partial result presents itself.** Which fields came back, which are
   missing, and how obvious the gaps are before saving.
4. **Whether the raw scraped text stays visible** during correction.
   `recipe_ingredients.raw_text` is an existing column and the URL-import spec
   already populates it, so the evidence is there to show — but showing it is a
   design choice.

## Constraints

- Call the `prototype` skill. Throwaway, not production code.
- The recipe form, the edit flow, and `RecipeIngredientIn` already exist —
  prototype against them rather than inventing a parallel shape.
- Do not design a second parser or a new API contract; the route contract is
  already specced.

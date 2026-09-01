# Implementation-Readiness Gaps

Findings from the pre-implementation review of `spec.md`, `plan.md`, and the
phase files. Each item is something to fix **before** the owning phase is handed
to an implementation pass — especially a low-cost model, which implements what
the spec literally says and does not repair prose bugs or resolve ambiguity.

This file is a working checklist, not normative. Fold each resolution into
`spec.md` / `issues.md` / the phase file and check it off here.

## Summary

| ID | Severity | Owning phase | Gap |
|---|---|---|---|
| R-1 | Blocker | 4, 5, 6 | `ing.quantity * multiplier` crashes on to-taste (`None`) ingredients |
| R-2 | Blocker (gate) | 4, 5, 6 | N5 / N6 / N7 unresolved; spec still documents the pre-fix behavior |
| R-3 | Precision | 1 | `normalize_unit_token` singularization rule is not pinned |
| R-4 | Precision | 3 | `raw_text` over-length behavior undefined |
| R-5 | Doc | any | Dangling `(2d)` / `(2e)` decision references in the spec |
| R-6 | Process | 4–6 | Model assignment: dense inventory math needs a stronger model or a review gate |
| R-7 | Process | 1, 4–6 | Same model writing impl + its own tests → circular validation |
| R-8 | Process | 2 | The conftest / app-factory test seam is prose-only; hand-author it |
| R-9 | Hygiene | now | `.claude/worktrees/` is not git-ignored (flagged by adversarial review) |
| R-10 | Process | all | Scope fence: implement only from `spec.md` §1–7 + the phase file |

---

## R-1 — `None` quantity × multiplier crashes availability, cook, and grocery

**Severity:** Blocker. Any recipe with a to-taste line (`"salt to taste"`) breaks
three endpoints.

**Where:**
- `spec.md` §5.3 (≈ line 870): `build list[ReqLine] with quantity = ing.quantity * multiplier`
- `spec.md` §5.4 cook: `ReqLine` built the same way from recipe ingredients
- `spec.md` §5.6 step 3 (≈ line 1135): `quantity = ing.quantity * multipliers.get(rid, 1)`

**Gap:** `ing.quantity` is `None` for to-taste rows. `None * float` raises
`TypeError`. The intent is clear elsewhere (`ReqLine.quantity: float | None`,
`aggregate` handles `quantity is None` members), but the multiplication
expression as written has no guard.

**Fix:** change the spec prose at all three sites to
`quantity = None if ing.quantity is None else ing.quantity * multiplier`.
Add a to-taste ingredient to the happy-path fixture in `test_recipes.py`
(`/availability`, `/cook`) and `test_grocery.py` (generate) so a regression is
caught.

**Owning phases:** 4, 5, 6 — fix the corresponding spec text before each.

---

## R-2 — N5 / N6 / N7 are still open and the spec documents the un-fixed behavior

**Severity:** Blocker (each is its phase's gate). Already tracked in
`issues.md`; restated here because the failure mode is specific: the spec is
*internally consistent* but describes the pre-fix behavior behind `⚠` markers,
and the recommended resolutions in `issues.md` contradict it.

| Issue | Phase | Spec currently says | `issues.md` recommends |
|---|---|---|---|
| N5 | 4 | inventory `match_name` is `.strip()`ed only, not normalized (`⚠ N5`) | run through `normalize_name`, reject empty, collide post-normalization |
| N6 | 6 | grocery-line PATCH applies `item` / `quantity` / `unit` independently (`⚠ N6`) | atomic quantity+unit pair, or convert on unit-only edit; reclassify / clear `nettable` |
| N7 | 5 | `deductions` stays `list[dict]` (`⚠ N7`); full key set by convention | typed `CookDeductionRead`, every key present, nullable where N/A |

**Fix:** make the three product decisions, fold them into `spec.md`, then close
each per the "Closing an issue" steps in `issues.md`. Do not leave the decision
to the implementation pass.

---

## R-3 — `normalize_unit_token` singularization is not pinned

**Severity:** Precision. Low blast radius but a genuine soft spot in Phase 1.

**Where:** `spec.md` §2.2 (≈ line 277) — `normalize_unit_token(...)` says
"naive-singularize" with no rule.

**Gap:** `normalize_name` step 5 is a precise ruleset (irregular map, `-ies→-y`,
`-ses/-xes/... → drop -es`, `-oes→-o`, trailing `-s` not `-ss`).
`normalize_unit_token` has nothing equivalent. `"cups"` must reach `"cup"` to
match the synonym table.

**Fix:** state the exact rule (e.g. "drop a single trailing `s` unless the token
ends in `ss`") or add an input→output table. Confirm every plural token in the
synonym table (`lbs`, `cups`, …) round-trips to a key that exists.

---

## R-4 — `raw_text` over-length behavior is undefined

**Severity:** Precision. Minor.

**Where:** `spec.md` §1 (`raw_text` `str(300)?`, ≈ line 145) and §5.2 ingredient
build (≈ line 837, `rows.append({**parsed, "raw_text": element})`).

**Gap:** a pasted ingredient line longer than 300 chars is stored verbatim.
SQLite does not enforce `String(300)`, so it will not error — but the column
contract and any future non-SQLite backend would. The spec does not say whether
to truncate or reject.

**Fix:** one sentence in §5.2 — truncate `raw_text` to 300 chars on store, or
state that the column length is advisory under SQLite.

---

## R-5 — Dangling `(2d)` / `(2e)` decision references

**Severity:** Doc hygiene.

**Where:** `spec.md` line 619 (`first writer wins (2d)`) and line 685
(`FIFO (2e)`).

**Gap:** `decisions.md` has no `2d` or `2e` entry. `S4` covers first-writer-wins;
there is no decision entry for FIFO-by-row-id deduction.

**Fix:** repoint the first to `S4`; add a decision entry for FIFO deduction and
cite it, or drop both parentheticals since the behavior is explained inline.

---

## R-6 — Model assignment per phase

**Severity:** Process.

| Phases | Assignment | Rationale |
|---|---|---|
| 0–3 | Low-cost model OK | Mechanical; parser has a locked acceptance table; CRUD and app-factory are well-specified. (Phase 0 complete.) |
| 4–6 | Stronger model **or** a mandatory review gate on the diff | `add_quantities` partitioning, the #N3 three-way `have_uncertain`/`short` split, FIFO + clamp-to-zero deduction logging, and canonical-unit consolidation are dense. Failure mode: plausible code that passes happy paths and mishandles one uncertainty branch. |
| 7 | Low-cost model OK | Documentation. |

---

## R-7 — Break the test/implementation circular-validation loop

**Severity:** Process.

**Problem:** if one model writes both the implementation and its own tests from
the same prose, a shared misreading passes green. The `spec.md` §2.3 parser
table is exact and self-checking; most of §7 is prose "must assert" bullets.

**Mitigations, in priority order:**

1. **Expand the exact-value tables in the spec.** Add `input → expected` rows for
   `add_quantities` (§2.2, ≈ 8 rows covering: known merge by dimension, opaque by
   exact token, `None`-unit into COUNT, all-`None` amounts → `Quantity(None,…)`,
   some-`None` amounts treated as `0`), `normalize_name` (§2.1, ≈ 10 rows), and
   `to_base` / `from_base` round-trip pairs. Model them on the §2.3 table.
2. **Split authorship.** The reviewing party writes `test_units.py`,
   `test_ingredient_parse.py`, and the Phase 4–6 math tests; the implementation
   pass writes code to pass them.
3. **Review the tests against the spec**, not only the implementation — they are
   smaller and declarative.
4. **Add interpretation-independent invariants:**
   - `parse_ingredient` result `quantity` is `None` or `> 0` and finite — always.
   - `from_base(to_base(x, u)[0], dim, u) == x` for every known unit.
   - `normalize_name(normalize_name(x)) == normalize_name(x)`.
   - `add_quantities` conserves the sum of base-unit amounts per dimension.

**Owning phases:** 1 (minimum: items 1, 2, 4), 4–6 (the math tests).

---

## R-8 — Hand-author the conftest / app-factory test seam

**Severity:** Process.

**Where:** `spec.md` §7 names the fixtures (`client`, `user`, `auth_client`) in
prose but gives no code. The current `backend/tests/conftest.py` uses
`app.dependency_overrides`, which `spec.md` §3.3 forbids ("No `dependency_overrides`
anywhere").

**Risk:** the in-memory test engine must carry the same `connect` and `begin`
event listeners as the real one (`PRAGMA foreign_keys=ON`, `busy_timeout=5000`,
`BEGIN IMMEDIATE`). If they are missing, `test_concurrency.py` still passes — and
proves nothing, because there is no write lock. A silent false-green under every
subsequent phase gate.

**Fix:** the reviewing party writes the final `conftest.py` plus the
`create_app(settings, engine)` / `make_engine(url)` signatures by hand at the
start of Phase 2, gets one real test passing through it, then the implementation
pass extends it per phase (adding `schemas/…` imports, etc.).

---

## R-9 — `.claude/worktrees/` is not git-ignored

**Severity:** Hygiene. Surfaced by the Codex adversarial review of the Phase 0
change.

**Gap:** an untracked linked git worktree exists at
`.claude/worktrees/plan-review-pass5/`. A `git add -A` / `git add .claude` would
record it as a broken embedded-repo gitlink (its `.git` file holds an absolute
machine-local path; the referenced commit lives only on a local branch).

**Fix:** add `.claude/worktrees/` (or `.claude/`) to `.gitignore`. Do this before
the next commit that stages broadly.

---

## R-10 — Scope fence

**Severity:** Process.

`features.md` is ~28 KB of deferred v2 scope. Instruct every implementation pass
to work **only** from `spec.md` §1–7 and the current phase file, and to treat
`features.md` as out-of-scope reference. A model that reads everything is prone
to pulling deferred features into the v1 surface.

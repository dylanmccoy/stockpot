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
| R-1 | ✅ Resolved | 4, 5, 6 | `ing.quantity * multiplier` crashes on to-taste (`None`) ingredients |
| R-2 | ✅ Resolved | 4, 5, 6 | N5 / N6 / N7 all resolved 2026-08-31; spec updated, issues closed |
| R-3 | ✅ Resolved | 1 | `normalize_unit_token` shares `normalize._singularize_token` (§2.1 step 5); plural round-trip test added |
| R-4 | ✅ Resolved | 3 | Pasted `str` element truncated to 200 before parse (bounds `raw_text` / `item` / `note`); test added |
| R-5 | ✅ Resolved | any | Dangling `(2d)` / `(2e)` references replaced with decisions `S4` / `SD2` |
| R-6 | ✅ Resolved | all | Every phase now closes on a non-author diff review gate (diff + tests vs `spec.md` §7); binding rule in `plan.md` §Execution rules, checkbox in each phase file |
| R-7 | ✅ Resolved (enforced gate) | 1, 4–6 | Locked spec oracles + fresh-context test authorship before production changes |
| R-8 | ✅ Resolved | 2 | Phase 2 now hand-authors `conftest.py` + `create_app`/`make_engine` (non-author, before route work) with a listener-parity test guarding the `connect`/`begin` seam |
| R-9 | ✅ Resolved | now | `.gitignore` now excludes `.claude/worktrees/` + `.claude/settings.local.json` |
| R-10 | ✅ Resolved (enforced gate) | all | Canonical phase handoff + per-phase scope audit; deferred docs are context only |

Non-blocking deferrals surfaced by this review (**D1** name singularization,
**D2** multi-line paste split) are tracked in
[`issues.md`](issues.md) §Deferred items, not here.

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

**✅ Resolved (2026-08-31).** Spec prose guarded at all three sites:
- §5.3 availability — `quantity = None if ing.quantity is None else ing.quantity * multiplier`
- §5.4 cook — same guard, stated on the `ReqLine` build
- §5.6 step 3 grocery — `quantity = None if ing.quantity is None else ing.quantity * multipliers.get(rid, 1)`

Regression guards folded in: §7 `test_recipes.py` / `test_grocery.py` rows and the
e2e walkthrough now require a to-taste line (`"salt to taste"`) in the happy-path
fixture; `phase-4/5/6.md` Work checklists carry the guard expression and the
fixture requirement.

---

## R-2 — N5 / N6 / N7 phase-gate issues (✅ all resolved 2026-08-31)

**Severity:** was Blocker (each is its phase's gate). The spec was *internally
consistent* but described pre-fix behavior behind `⚠` markers that the
`issues.md` recommended resolutions contradicted. All three are now folded into
`spec.md` and closed.

| Issue | Phase | Status | Resolution |
|---|---|---|---|
| N5 | 4 | ✅ Resolved 2026-08-31 | `match_name` canonical: `normalize_name`d on POST/PATCH, `""` → 422, collision + `ON CONFLICT` on normalized value, no auto-merge. |
| N6 | 6 | ✅ Resolved 2026-08-31 | grocery-line PATCH: `quantity` + `unit` atomic pair (one alone → `422`, no conversion); any `item`/`quantity`/`unit` edit → `source="manual"`, `nettable=true`. |
| N7 | 5 | ✅ Resolved 2026-08-31 | `CookDeductionRead` is a real `BaseModel` (`extra="forbid"`, `reason` a 5-value `Literal`), used as `CookLogRead.deductions: list[CookDeductionRead]`; DB column stays raw `JSON list[dict]`, validated on read; `_entry()` takes all 11 kwargs as required. |

All three resolutions are in `decisions.md` §Revisions — phase-gate issue
resolutions; `issues.md` now lists no open issues.

---

## R-3 — `normalize_unit_token` singularization is not pinned (✅ resolved 2026-08-31)

**Severity:** was Precision. Low blast radius but a genuine soft spot in Phase 1.

**Where:** `spec.md` §2.2 (≈ line 277) — `normalize_unit_token(...)` said
"naive-singularize" with no rule.

**Gap:** `normalize_name` step 5 is a precise ruleset (irregular map, `-ies→-y`,
`-ses/-xes/... → drop -es`, `-oes→-o`, trailing `-s` not `-ss`).
`normalize_unit_token` had nothing equivalent. A low-cost pass reads
"naive-singularize" as "drop trailing `s`", which is **wrong for the opaque
tokens** `boxes` (→ `boxe`), `bunches`, `dashes`, `splashes`, `pinches` — the
`-es` group needs `drop -es`. `boxes` and `box` then land in different opaque
buckets (`opaque:boxe` ≠ `opaque:box`) and **silently fail to net**. Known-unit
plurals (`cups`, `lbs`, …) round-trip fine under either rule.

**Fix (chosen — Option A):** no library (`inflect` / `inflection` rejected —
closed ~35-token domain, spec forbids a `units.py` dependency, and delegating
netting-critical normalization to a versioned package reintroduces silent bucket
drift). Instead: extract the §2.1 step-5 rule into
`normalize._singularize_token(tok) -> str`; `normalize_name` calls it on the final
token, `normalize_unit_token` calls it on the whole (lowered, stripped) string.
One rule, one test surface, future synonym-table tokens handled automatically.

**✅ Resolved (2026-08-31).**
- `spec.md` §2.1 — step 5 delegates to `_singularize_token`, defined immediately
  below with the full rule + an explicit "no trailing `-s` / ends `-ss` →
  unchanged" line.
- `spec.md` §2.2 — `normalize_unit_token` pipeline now
  `… → normalize._singularize_token (whole string) → return`, with worked
  examples (`Cups.→cup`, `boxes→box`, `fl oz→fl oz`, `lbs→lb`).
- `spec.md` §7 — `test_units.py` row: every synonym-table token and every opaque
  token round-trips; `boxes/bunches/dashes/splashes/pinches` asserted by name.
- `phases/phase-1.md` — Work: `_singularize_token` extraction + shared call;
  Verification: round-trip coverage bullet.
- Open follow-up (non-blocking, no phase gate): `issues.md` §Deferred items
  **D1** — robust open-vocabulary singularization for ingredient *names*.

---

## R-4 — `raw_text` over-length behavior was undefined (✅ resolved 2026-08-31)

**Severity:** was Precision. Minor.

**Where:** `spec.md` §1 (`raw_text` `str(300)?`) and §5.2 ingredient build
(`rows.append({**parsed, "raw_text": element})`).

**Gap:** a pasted ingredient line longer than its column was stored verbatim.
SQLite does not enforce `String(n)`, so v1 would not error — but the column
contract and any future non-SQLite backend would. The spec did not say whether
to truncate or reject. Not just `raw_text`: the parser's `item` (falls back to
the whole cleaned line) and `note` are `str(200)` and are fed from the same
pasted line.

**Fix (chosen):** truncate the pasted `str` element to **200 chars** before
`parse_ingredient` — one guard at the entry point, since every downstream sink
(`raw_text` `str(300)`, `item` / `note` `str(200)`) is `<=` the input length.
Truncate rather than `422` (a pasted line is best-effort data; don't fail a
whole recipe over one long line). 200 is far above any real single ingredient
line, so this effectively never fires for a well-formed client.

**✅ Resolved (2026-08-31).**
- `spec.md` §5.2 — `element = element[:200]` added to the build loop before the
  blank-line check; new "Length bound (R-4)" paragraph explains the single-guard
  rationale.
- `spec.md` §1 — `raw_text` row notes the stored value is `<= 200`; column
  headroom left intentionally.
- `spec.md` §7 — `test_recipes.py` row: a > 200-char pasted line is truncated,
  all three string fields fit, recipe still creates (no 422).
- `phases/phase-3.md` — Work + Verification bullets carry the truncation guard.
- Related follow-up (non-blocking, no phase gate): `issues.md` §Deferred items
  **D2** — pasted ingredient block with embedded `\n` instead of one line per
  array element.

---

## R-5 — Dangling `(2d)` / `(2e)` decision references (✅ resolved 2026-08-31)

**Severity:** Doc hygiene.

**Where:** `spec.md` §4.3 (`first writer wins (2d)`) and §4.5 (`FIFO
(2e)`).

**Gap:** `decisions.md` has no `2d` or `2e` entry. `S4` covers first-writer-wins;
`SD2` covers deterministic ascending-row-ID deduction. The spec retained stale
references to the earlier review numbering and called the latter behavior
"FIFO," even though inventory rows are aggregates rather than purchase lots.

**✅ Resolved (2026-08-31).** Replaced `(2d)` with `decision S4` and `(2e)` with
`decision SD2`. Reworded "FIFO" as "deterministic ascending row-ID order" in
the algorithm, decision rationale, historical note, and acceptance-test matrix.

---

## R-6 — Model assignment per phase (✅ resolved 2026-08-31)

**Severity:** was Process.

**Gap:** the only defence against a weak implementation pass on the dense
Phase 4–6 math (`add_quantities` partitioning, the N3 three-way
`have_uncertain` / `short` split, ascending row-ID deduction + clamp-to-zero
logging, canonical-unit consolidation) was a suggestion in this checklist —
"use a stronger model **or** a review gate on the diff." It carried no binding
weight, and "use a stronger model" is unverifiable after the fact. The failure
mode: plausible code that greens the happy path and mishandles one uncertainty
branch, with tests written by the same pass that never exercise it.

**Fix (chosen):** drop the model-tier language and make the review gate binding
for **every** phase. Before a phase closes, a reviewer who did not write its
production code — a separate model pass or a person — checks the phase diff
**and its new tests** against `spec.md` §7 and the behavior sections the phase
implements, walking each uncertainty branch rather than trusting a green suite.
For Phases 1 and 4–6 this is the production-diff half of the R-7 independent
contract-test gate; for Phases 2–3 and 7 it stands alone. No `spec.md` change
(this is process, not behavior); no `decisions.md` entry (consistent with the
other readiness-item resolutions).

**✅ Resolved (2026-08-31).**

- `plan.md` §Execution rules — new binding bullet "Diff review gate (every
  phase, R-6)".
- `phases/phase-0.md` — review-gate exit criterion added, checked (`[x]`), citing
  the Codex adversarial review of the Phase 0 change.
- `phases/phase-1.md` … `phase-7.md` — review-gate exit criterion added to each,
  naming the `spec.md` sections that phase must be reviewed against.
- Related, resolved separately: **R-7** (independent contract-test gate) — the
  two gates compose but are distinct.

---

## R-7 — Break the test/implementation circular-validation loop (✅ resolved 2026-08-31)

**Severity:** Process.

**Problem:** if one model writes both the implementation and its own tests from
the same prose, a shared misreading passes green. The `spec.md` §2.3 parser
table is exact and self-checking; most of §7 is prose "must assert" bullets.

**✅ Resolved (2026-08-31).** The mitigation is now an enforceable delivery gate,
not advice left to the implementation pass:

1. `plan.md` §Independent contract-test gate requires a fresh-context reviewer
   to author and review a test-only patch from the normative spec before
   production changes. Accepted contract cases are locked; correcting one
   requires a separate reviewed spec+test patch. The implementation diff and
   the tests are reviewed separately.
2. `spec.md` §2 adds exact normalization, conversion, and `add_quantities`
   tables, a single numeric tolerance, deterministic first-seen partition
   ordering (decision SD4), full known-token round-trips, and
   conservation/no-raise checks.
3. `spec.md` §7 adds exact availability, grocery-generation, deduction, and
   add-to-inventory oracles plus interpretation-independent math checks.
4. Phase 1 and Phases 4–6 now have an open **pre-implementation** contract-test
   gate and an exit check that the accepted cases were not changed by the
   implementation pass.

The proposed global invariant
`normalize_name(normalize_name(x)) == normalize_name(x)` was deliberately **not**
adopted: the documented open-vocabulary heuristic maps `buses → bus → bu`.
Exact v1 normalization vectors are locked instead; robust name inflection
remains deferred as D1. No property-testing dependency was added—deterministic
parameterization is sufficient for the closed unit domain.

**Owning phases:** 1 and 4–6. The readiness gap is resolved by the enforced
policy; each phase's gate remains unchecked until its independent test-only
patch is actually accepted.

---

## R-8 — Hand-author the conftest / app-factory test seam (✅ resolved 2026-08-31)

**Severity:** was Process.

**Gap:** `spec.md` §7 named the fixtures (`client`, `user`, `auth_client`) and
§3.2 / §3.3 specified the `make_engine` listeners and the "no `dependency_overrides`"
rule, but no `conftest.py` code existed. The on-disk `backend/tests/conftest.py`
still used the forbidden `app.dependency_overrides` seam with a hand-rolled engine
carrying none of the `connect` / `begin` listeners (`isolation_level=None`,
`PRAGMA foreign_keys=ON`, `PRAGMA busy_timeout=5000`, `BEGIN IMMEDIATE`). Failure
mode: a cheap implementation pass copies that pattern, `test_concurrency.py`
passes with no write lock and no FK enforcement, and every later phase gate
inherits a concurrency suite that proves nothing — a silent false-green.

**Fix (chosen):** fold the requirement into `phases/phase-2.md` as an ordered,
authored, guarded step — no `spec.md` change (§3.2 / §3.3 / §7 already specify the
behavior), no `decisions.md` entry (consistent with R-1 / R-3 / R-4 / R-6). The
stale `conftest.py` is **not** rewritten early: Phases 0–1 change no HTTP/DB
behavior and Phase 1's tests take no `client`, so Phase 2 deletes and replaces it.
Within Phase 2 the seam is built first, before any route work, by a reviewer who
does not write the phase's production code, with one real test green through it; a
listener-parity test then guards against a missing listener.

**✅ Resolved (2026-08-31).**

- `phases/phase-2.md` Work — the "rebuild test fixtures" bullet replaced with an
  ordered one: a non-author replaces `conftest.py` (delete the `dependency_overrides`
  seam; build via `create_app` + a `make_engine` in-memory `StaticPool` engine with
  the `connect` / `begin` listeners; add `client` / `user` / `auth_client`) before
  route work and gets one real test green through it.
- `phases/phase-2.md` Verification — new listener-parity bullet: `PRAGMA
  foreign_keys` returns `1`, and while a transaction holds the write lock a second
  connection's write blocks and times out under `busy_timeout`.
- `phases/phase-2.md` Exit criteria — new criterion: the seam was hand-authored by
  a non-author before route work, attaches the listeners, and the listener-parity
  test passes.
- The R-6 diff review gate already on Phase 2 re-checks this seam against
  `spec.md` §3.

---

## R-9 — `.claude/worktrees/` is not git-ignored (✅ resolved 2026-08-31)

**Severity:** Hygiene. Surfaced by the Codex adversarial review of the Phase 0
change.

**Gap:** an untracked linked git worktree exists at
`.claude/worktrees/plan-review-pass5/`. A `git add -A` / `git add .claude` would
record it as a broken embedded-repo gitlink (its `.git` file holds an absolute
machine-local path; the referenced commit lives only on a local branch).

**Fix:** add `.claude/worktrees/` (or `.claude/`) to `.gitignore`. Do this before
the next commit that stages broadly.

**✅ Resolved (2026-08-31).** Added a "Tooling-local state" block to `.gitignore`
with `.claude/worktrees/` and `.claude/settings.local.json`. Scoped to those two
paths rather than all of `.claude/` so shared config (`.claude/settings.json`,
`commands/`, `agents/`) stays committable. `settings.local.json` was only covered
by a machine-global excludesfile before; it is now ignored in-repo too. Verified
with `git check-ignore`.

---

## R-10 — Scope fence (✅ resolved 2026-08-31)

**Severity:** Process.

`features.md` is ~28 KB of deferred v2 scope. Instruct every implementation pass
to work **only** from `spec.md` §1–7 and the current phase file, and to treat
`features.md` as out-of-scope reference. A model that reads everything is prone
to pulling deferred features into the v1 surface.

The literal "only those two documents" formulation became too narrow once R-6
and R-7 added process rules and accepted contract tests. Existing code also has
to be inspected safely. The enforceable boundary is therefore about what may
**authorize behavior**, not what may be read.

**✅ Resolved (2026-08-31).**

- `plan.md` §Phase scope fence and handoff contract defines the only
  implementation authorities: the current phase, its linked normative spec,
  and accepted R-7 tests; `plan.md` supplies process rules and existing code/tests
  may be inspected as needed.
- `features.md`, `decisions.md`, historical reviews, and deferred `issues.md`
  entries are explicitly context-only and cannot authorize a model, route,
  field, dependency, configuration option, integration, or behavior.
- The plan now carries a copyable implementation-handoff prompt and requires a
  reviewed scope/spec change instead of guessing when authorized sources are
  incomplete or appear to require deferred work.
- The R-6 diff-review gate now includes the R-10 audit: every changed behavior,
  public surface, and dependency must trace to an authorized source.
- Every phase has a scope-attestation exit checkbox. Phase 0 is checked because
  its completed dependency-only diff already had an explicit v2 exclusion
  boundary; unfinished phases remain unchecked until review.
- Phase 7 has the sole read-only exception: it may consult `features.md` to link
  deferred work and verify exclusions, never to implement or describe it as
  shipped v1 behavior.

No `spec.md` or `decisions.md` change: this resolves delivery process, not
application behavior or historical rationale.

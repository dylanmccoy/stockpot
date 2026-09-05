# Open Backend v1 Issues

Two kinds of item live here:

- **Phase-gate issues** — unresolved findings that block an owning phase. Each
  becomes a gate for its owning phase and must be resolved in the normative
  [`spec.md`](spec.md) before that phase is implemented. Resolved review
  findings N1–N4 and their rationale are preserved in
  [`decisions.md`](decisions.md).
- **Deferred items** — acknowledged gaps that are **not** v1-blocking and carry
  no phase gate. Tracked here so they are not lost; the substantive write-up
  lives in [`features.md`](features.md).

## Phase-gate issues

These issues do not block Phases 0–3. Each becomes a gate for its owning phase
and must be resolved in the normative [`spec.md`](spec.md) before that phase is
implemented.

_No open issues._

_All review-pass-6 phase-gate findings are resolved:_

- _N5 (inventory `match_name` canonicalization) — 2026-08-31_
- _N6 (grocery quantity/unit edit safety) — 2026-08-31_
- _N7 (typed cook-deduction response) — 2026-08-31_

_See [`decisions.md`](decisions.md) §Revisions — phase-gate issue resolutions._

## Deferred items (non-blocking, no phase gate)

No timeline. No `spec.md` or phase change in v1. Revisit per each item's trigger.

### D1 — Robust singularization for ingredient names

**Opened:** 2026-08-31, alongside the R-3 readiness fix.

**Context:** R-3 pinned `normalize._singularize_token` for **unit tokens** — a
closed ~35-item set where a hand rule + irregular map is provably complete.
Ingredient **names** (`normalize_name`) are open-vocabulary: `cherries`,
`berries`, `gnocchi`, `biscotti`, `roux`, `feta` vs `feta cheese`. The same
small ruleset applies there and will mis-singularize or under-match some real
inputs. v1 accepts this — the editable inventory `match_name` is the manual
escape hatch.

**When to revisit:** with the `FoodItem` upgrade (canonical identity + aliases),
or sooner if name mismatches become a real household annoyance. A library
(`inflect`) is a reasonable option **here**, unlike for units, because the
vocabulary is genuinely open.

**Write-up:** `features.md` §`FoodItem — canonical ingredient identity` →
"Current approach (v1)" rough edges.

### D2 — Multi-line ingredient paste is not split

**Opened:** 2026-08-31, alongside the R-4 readiness fix.

**Context:** each element of `payload.ingredients` is one ingredient line *by
contract*. §5.2 does no newline splitting — a `str` element with embedded `\n`
(`"2 tbsp oil\n3 eggs\n1 onion"`) is passed whole to `parse_ingredient`, which
reads it as a single line: `quantity=2`, `unit=tbsp`, `item` = the rest of the
blob. With the R-4 fix the blob is truncated to 200 chars first, so it can no
longer overflow a column, but it still produces one garbled ingredient row
instead of three.

**Why deferred, not fixed:** splitting a pasted block server-side is a real
input-handling feature (how to treat blank lines, headers like "For the sauce:",
bullet characters, wrapped lines), not a one-line precision fix. The eventual
frontend paste box is the natural place to split; until then, callers send a
pre-split array. No v1 client is affected.

**When to revisit:** with the frontend SPA effort, or if an API consumer needs
to POST a raw pasted block. If done server-side, split on `\n`, `strip()` each,
drop blanks, then run the existing per-line build.

**Write-up:** `features.md` §`Additional deferred features` → "Multi-line
ingredient paste".

### D3 — Session bearer tokens are stored in plaintext

**Opened:** 2026-09-04, during an auth-security review.

**Context:** the opaque bearer token returned by register/login is the exact
value stored in `sessions.token`. Anyone who can read the database can therefore
use any unexpired session token. This is an accepted v1 security posture, not an
unknown implementation bug; `spec.md` §Accepted security posture already records
the exposure.

**Why deferred, not fixed:** v1 is LAN-only and uses short-lived, revocable
database sessions. Changing the stored representation also needs an explicit
rollout decision for existing sessions. No runtime or schema change is authorized
by this note.

**When to revisit:** before remote/public hosting, when database backups leave a
trusted machine, or when the database starts containing data valuable enough to
make credential theft a material concern.

**Write-up:** `features.md` §`Infrastructure deferrals` → "Hashed session-token
storage".

## Closing an issue

Phase-gate issues:

1. Record the chosen behavior in `spec.md`.
2. Update its phase checklist and acceptance tests.
3. Move the resolution summary to `decisions.md`.
4. Remove the issue from this file rather than leaving a resolved-history table.

Deferred items are closed either by shipping the feature (write-up moves to the
relevant phase / `spec.md`) or by an explicit decision to drop them (record in
`decisions.md`); then delete the entry here.

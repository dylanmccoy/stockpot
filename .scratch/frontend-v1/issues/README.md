# Frontend v1 — ticket slices

One file per ticket, worked blockers-first. Tickets whose id carries a letter
suffix (`06a`, `13c`, …) are vertical slices of an oversized parent; the parent
file stays as `**Status:** split — do not implement this ticket directly.`

Delivery phases and the normative contract:

- `docs/frontend/plan.md` — Phases 0–8, the gate list.
- `docs/frontend/spec.md` — the frontend contract (§1 module layout, §5 API
  mirror, §6 error catalog, §10 screen specs).
- `docs/spec.md` §5 — the backend API the `integrate-*` tickets (15–18) re-diff
  `frontend/src/types.ts` against.

## Ticket header contract

Every ticket carries these three fields directly under **Status:**, before the
checklist:

- **Files:** the exact paths to create / edit. The agent should not need to
  search the tree for them.
- **Spec:** the exact `docs/frontend/spec.md` section anchors (`§X.Y`) with a
  one-word gloss each, ending "Read only these sections." The `integrate-*`
  tickets also cite the `docs/spec.md` §5.x subsection to re-diff against. Never
  cite a whole spec file.
- **Tests:** the exact scoped `npm run test:run -- <file>` command for this
  ticket (cross-screen hardening tickets run the full `npm run test:run`).

Rationale: keeps each `/implement` inside the smart zone by removing tree-search
and whole-spec reads. `frontend/CLAUDE.md` holds the area → spec-section → file →
test map the **Spec:** and **Files:** lines are drawn from.

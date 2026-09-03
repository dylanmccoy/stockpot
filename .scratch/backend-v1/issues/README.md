# Backend v1 — Phases 4–7 vertical slices

Phases 4 and 6 in `docs/phases/` are each too large for one context window; this
splits them (and Phase 5) into tracer-bullet slices. Phase 7 stays whole.

Every ticket ends with `cd backend && uv run pytest` green **except** the three
R-7 oracle-lock tickets (`phase-4a`, `phase-5a`, `phase-6a`) — those deliver an
*accepted, locked* black-box oracle before their implementation exists, per
`docs/plan.md` §Independent contract-test gate.

Each ticket's acceptance includes ticking the matching boxes in
`docs/phases/phase-N.md`; the phase-closing tickets (`phase-4e`, `phase-5c`,
`phase-6f`, `phase-7`) also flip the `docs/plan.md` status table. `docs/spec.md`
is touched only via a paired spec+test change if a locked oracle proves it wrong.

## Dependency order

```
phase-4a  inventory-math oracle lock (R-7)
  └─ phase-4b  InventoryItem model + additive CRUD + add_to_inventory_calc
       ├─ phase-4c  inventory PATCH (absolute + N5)
       └─ phase-4d  availability endpoint (aggregate + check_availability)
            └─ phase-4e  deduct_calc pure service + Phase 4 close   [needs 4c done]
                 └─ phase-5a  cook oracle lock (R-7)
                      └─ phase-5b  cook + per-recipe history
                           └─ phase-5c  global cook-log reads + Phase 5 close
                                └─ phase-6a  grocery oracle lock (R-7)
                                     └─ phase-6b  grocery models + generate_lines
                                          └─ phase-6c  manual items + line editing (N6)
                                               └─ phase-6d  submit
                                                    └─ phase-6e  archive
                                                         └─ phase-6f  concurrency contract + Phase 6 close
                                                              └─ phase-7  documentation
```

Only real fan-out: within Phase 4, `phase-4c` and `phase-4d` both depend on
`phase-4b` and are independent of each other; `phase-4e` waits on both.

## Ticket header contract

Every ticket carries these three fields directly under **Status:**, before the
checklist:

- **Files:** the exact paths to create / edit. The agent should not need to
  search the tree for them.
- **Spec:** the exact `docs/spec.md` section anchors (`§X.Y`) with a one-word
  gloss each, ending "Read only these sections." Never cite a whole spec file;
  never send the agent to `docs/frontend/`.
- **Tests:** the exact scoped test command for this ticket (the R-7 oracle-lock
  tickets say "n/a — not expected to pass until `<impl ticket>`").

Rationale: keeps each `/implement` inside the smart zone by removing tree-search
and whole-spec reads. `backend/CLAUDE.md` holds the area → spec-section → test
map the **Spec:** lines are drawn from.

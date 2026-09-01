# Backend v1 Delivery Plan

This is the master execution roadmap for the backend-only v1 of the household
recipe and food-inventory app. It defines scope, phase order, gates, and status.
It deliberately does not repeat the implementation contract.

## Document map

| Document | Authority |
|---|---|
| [`spec.md`](spec.md) | Normative v1 behavior: models, schemas, algorithms, endpoints, transactions, and acceptance criteria |
| [`plan.md`](plan.md) | Delivery sequence, phase dependencies, scope, and status |
| [`phases/`](phases/) | Phase-specific work checklists and exit criteria; links back to the spec |
| [`issues.md`](issues.md) | Unresolved findings only; an owning phase must resolve its issues before completion |
| [`decisions.md`](decisions.md) | Historical decisions and review rationale; non-normative when it conflicts with the spec |
| [`features.md`](features.md) | Deferred v2 capabilities, infrastructure upgrades, and excluded product directions |

When documents disagree, use this order:

1. `spec.md` for required v1 behavior.
2. `plan.md` for delivery order and scope.
3. The owning phase file for the current checklist.
4. `decisions.md` for historical context only.

## Outcome

Build the backend core loop that reduces the friction of cooking at home:

1. Store recipes with structured ingredients.
2. Track household food inventory with real quantities.
3. Check a recipe against current stock.
4. Record cooking and optionally deduct stock.
5. Generate grocery lists from selected recipes, netted against stock.
6. Submit checked grocery lines back into inventory.

There is no meal planning. The unit of work is “make this recipe now.”

The v1 interaction surface is the FastAPI OpenAPI UI at `/docs` and the test
suite. The existing React frontend is intentionally left untouched and will not
work against the new API until the deferred frontend effort.

## v1 scope

### Included

- Opaque bearer sessions with registration disabled by default.
- Structured recipe CRUD and pasted ingredient-line parsing.
- Inventory CRUD with canonical quantity storage and unit conversion.
- Recipe availability checks, including uncertain incompatible stock.
- Cook logs with optional, auditable inventory deduction.
- Per-recipe and global cook-log reads.
- Grocery-list generation, manual lines, submit, archive, and deletion.
- Offline tests, including file-backed SQLite concurrency tests.
- Operational documentation for a LAN deployment.

### Excluded

- Frontend rebuild.
- Meal planning and “what can we make now?” queries.
- Staples and low-stock alerts.
- Photo upload, URL import, recipe research, per-cook reviews, and receipt OCR.
- Alembic, Postgres, remote hosting, per-user ownership, and role-based access.
- LLM or AI services.

Deferred work and upgrade paths live in [`features.md`](features.md).

## Constraints

- Extend the existing repository and preserve its one-way import layering:
  `config → database → normalize/units → models → security/services → schemas/routers → main`.
- Keep SQLite and `Base.metadata.create_all()` for v1; there are no migrations.
- `create_app(test_settings, test_engine)` is the only test database wiring;
  tests use real HTTP through `TestClient` and no dependency overrides.
- No live network calls in v1 or its tests.
- Prefer the smallest implementation that satisfies the spec; every new
  dependency needs a stated reason.
- Every phase ends with the full backend test suite green.

## Definition of done

- Every behavior in [`spec.md` §7](spec.md#7-acceptance-criteria--test-matrix)
  is implemented and tested.
- `cd backend && uv run pytest` passes.
- The end-to-end `/docs` verification in the spec passes.
- All phase files are complete and no v1 issue remains open.
- `README.md`, `CLAUDE.md`, and `backend/.env.example` describe the shipped
  architecture and operating procedure.
- No deferred feature has leaked into the v1 dependency or API surface.

## Build sequence

There are eight phases, numbered 0–7. Phase 7 is documentation; there is no
Phase 8 in the current v1 plan.

| Phase | Outcome | Depends on | Status |
|---|---|---|---|
| [0 — reset and dependencies](phases/phase-0.md) | Clean database and Argon2 dependency | — | Not started |
| [1 — pure core](phases/phase-1.md) | Normalization, units, and ingredient parser | Phase 0 | Not started |
| [2 — auth and app factory](phases/phase-2.md) | App-local DB wiring, transactions, sessions, and route gating | Phase 1 | Not started |
| [3 — structured recipes](phases/phase-3.md) | Nested recipe ingredients and validation | Phase 2 | Not started |
| [4 — inventory and availability](phases/phase-4.md) | Inventory CRUD and availability math | Phase 3; resolve N5 | Not started |
| [5 — cooking and history](phases/phase-5.md) | Stock deduction and durable cook logs | Phase 4; resolve N7 | Not started |
| [6 — grocery lists](phases/phase-6.md) | Netted lists, submit, archive, and concurrency behavior | Phase 5; resolve N6 | Not started |
| [7 — documentation](phases/phase-7.md) | User and developer documentation matches the shipped backend | Phase 6 | Not started |

Schema-expanding phases 3–6 require deleting `backend/recipe.db` before their
first local run. This is acceptable only because v1 has not accumulated data;
the first post-v1 schema change triggers the Alembic work described in
[`features.md`](features.md#infrastructure-deferrals).

## Execution rules

- Start a phase only after its dependencies are complete.
- Read the linked spec sections before implementation; phase files summarize
  work but do not redefine behavior.
- Resolve any issue owned by the phase by updating `spec.md`, `issues.md`, and
  the phase checklist before implementing the affected behavior.
- Keep the suite green at the end of every phase. A phase is incomplete if only
  its new tests pass.
- Update the status table here and the checkbox in the phase file together.
- Do not pull deferred work into a phase without first changing the v1 scope.

## Planning history

- Requirements, codebase exploration, and the original design pass are complete.
- The pre-trim plan is preserved at `git show 5144c25:docs/plan.md`.
- v1 was narrowed on 2026-08-31 to the core cooking loop.
- Review passes 2–7 are resolved or tracked in
  [`decisions.md`](decisions.md) and [`issues.md`](issues.md).
- The implementation specification is complete and is authoritative for v1.
- Phase 0 is awaiting implementation go-ahead.

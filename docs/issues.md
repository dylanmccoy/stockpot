# Open Issues: Backend v1 Plan Review Pass 6

Review date: 2026-08-31
Resolution date: 2026-08-31 — **N1, N2, N3 (blockers) and N4 resolved** in
`docs/plan.md` §"Revisions — review pass 6". N5–N7 remain open for their owning
phase. See the Resolution section below.

Scope calibration: this is a local, LAN-only, educational application for at
most a couple of trusted household users. Global SQLite write serialization,
full-trust household access, forward-only cook/grocery actions, and postponing
migrations are therefore **not** treated as blockers.

## Verdict

The plan is close, and Phases 0-1 can start safely. Phases 2-6 should not be
executed unchanged until **N1-N3** are resolved: the inventory PATCH schema
contradicts its documented examples, the app-local database dependency is not
actually defined in a form static FastAPI routers can consume, and mixed
compatible/incompatible stock is still treated as confidently nettable. The
remaining findings should be settled before their owning phase to avoid
ambiguous APIs or misleading audit data.

**Update 2026-08-31:** N1, N2, N3 and N4 are folded into `docs/plan.md` (§Revisions
— review pass 6). Phases 2-6 are now unblocked. N5, N6, N7 stay open for
Phases 4/5/6 respectively.

## Resolution (2026-08-31)

| ID | Status | Where fixed in `docs/plan.md` |
|---|---|---|
| N1 | **Resolved** | §Revisions pass 6 row N1; §Schemas `inventory.py` (`InventoryItemCreate` vs `InventoryItemUpdate`); §"edit an inventory row" pseudocode (`model_fields_set` gate, explicit-null → 422, `PATCH {}` → 200); Phase 4; test strategy `test_inventory.py`. |
| N2 | **Resolved** | §Revisions pass 6 row N2; §Module/router layout (`database.py`, `security.py`, `main.py` lines); §Schema management (importable `get_db(request)` + `SessionDep`, `app.state.session_factory` only, no `SessionLocal`); Phase 2; Critical files. |
| N3 | **Resolved** | §Revisions pass 6 row N3; availability + grocery-generation pseudocode (three-way `compat`/`incomp`/none partition); #R6 and #P4 revision rows (refinement notes); Done criteria items 4 & 6; cook narrative (deliberate non-adoption); test strategy `test_inventory_math.py` / `test_grocery.py`. |
| N4 | **Resolved via N2** | §Revisions pass 6 row N4; §Schema management "Unit of work" bullet — `get_db` commits on clean return / rolls back on exception; routers `flush()` only; auth `last_used_at` bump rides the request's one transaction. |
| N5 | Open — Phase 4 | `match_name` normalization / non-empty enforcement — address when Phase 4 lands. |
| N6 | Open — Phase 6 | Atomic quantity/unit pair on grocery-line edits — address when Phase 6 lands. |
| N7 | Open — Phase 5 | Typed `CookDeductionRead` with all keys present — address when Phase 5 lands. |

## Findings

| ID | Severity | Title | Plan location / responsible text | Concrete failure scenario | Impact | Required plan change | Confidence |
|---|---|---|---|---|---|---|---:|
| N1 | **Blocker — Phase 4** | Inventory POST and PATCH cannot share the stated input schema | **Schemas → `inventory.py`:** `InventoryItemIn {item, quantity, unit, match_name}` is described as the input for both operations. **Edit algorithm:** `PATCH /api/inventory/{id} {item?, match_name?, quantity?, unit?}`. **Verification:** `PATCH {quantity:200}` and `PATCH {unit:"kg"}`. | If `InventoryItemIn.item` and `quantity` are required as written, both verification PATCHes return 422. Making every field nullable instead allows explicit `item:null` or `match_name:null`, which reaches non-null database columns or produces the wrong 409. | Phase 4 cannot implement both its schema and its acceptance examples. Patch omission versus explicit null is also undefined. | Define `InventoryItemCreate` with required `item` and `quantity`, and a separate `InventoryItemUpdate`: `item`, `match_name`, and `quantity` may be omitted but cannot be null when present; `unit` may be omitted or explicitly null because null is a valid COUNT unit. Use `model_fields_set` to distinguish omission. Add 422 tests for null required fields and for `unit:null` when it would change a non-COUNT row's bucket. | 1.00 |
| N2 | **Blocker — Phase 2** | The app-local session dependency is contradictory and not wired to static routers | **Module layout:** says the default module-level `engine/SessionLocal` is retained. **Review P2 / Schema management:** says there is no importable module-global session factory and that `create_app` installs `get_db` on `app.state`. Routers and `CurrentUser` are nevertheless defined statically with `Depends(...)`. | FastAPI resolves a concrete dependency callable when router functions are defined; putting a newly created generator function on `app.state` does not make existing `Depends` declarations use it. Retaining global `SessionLocal` makes the factory point at two databases again; removing it without a generic dependency leaves routers with nothing importable to depend on. | Phase 2 can either query the wrong engine or require the same manual overrides P2 claims to eliminate. Multiple factory-created apps are especially likely to cross wires. | Make the contract explicit: `create_app` stores only `session_factory` on `app.state`; define one importable `get_db(request: Request)` dependency that reads `request.app.state.session_factory`; define `SessionDep = Annotated[Session, Depends(get_db)]`; have all routers/security use it. Keep a module-level default **engine** only to construct the uvicorn app, but no module-level `SessionLocal`. Update the module-layout contradiction. | 0.98 |
| N3 | **Blocker — Phase 4/6** | A known shortfall is marked nettable even when additional incompatible stock makes the true shortfall uncertain | **Availability:** once any compatible row exists, only compatible stock participates and the result is `ok`/`short`. **Grocery generation:** when compatible stock exists, the emitted shortfall is always `nettable=true`; other positive buckets are ignored. | A recipe needs `3 can tomatoes`; inventory has `1 can` and `1 jar`. The plan subtracts the can, reports `short 2 can`, and generates a confidently nettable `2 can` grocery line. The jar may cover some or all of that need—the exact shortfall is unknown. The same occurs with `1 kg flour` plus `1 bag flour`. | The core grocery feature can overbuy while claiming its result was safely netted, contradicting “unit-incompatible lines are flagged `nettable=false`.” | Partition into positive compatible and positive incompatible rows. If compatible stock fully covers the need, return `ok`. If a positive short remains **and** incompatible stock exists, return `have_uncertain` and emit the known compatible-bucket remainder with `nettable=false`. Only use `short`/`nettable=true` when no positive incompatible stock exists. Add availability and grocery tests for `need 3 can / have 1 can + 1 jar`. | 0.98 |
| N4 | High — Phase 2 | Transaction completion for `last_used_at` and read requests is unspecified | **Auth:** `get_current_user` bumps `last_used_at`. **Concurrency:** every request transaction begins immediately. **Service rule:** routers own and commit transactions. The app-local `get_db` dependency is described only as yielding and closing a session. | On a successful GET, `get_current_user` updates the ORM row, but the read handler has no reason to commit. Closing the session rolls the update back. If `get_current_user` commits itself, an authenticated mutation now spans an auth transaction and a separate router transaction, contrary to the implied single request transaction. | `last_used_at` silently stops working or transaction boundaries vary by endpoint. Lock-timeout handling also becomes harder to place consistently. | Choose one unit-of-work policy. Recommended here: `get_db` commits once after a successful dependency yield and rolls back on any exception; routers `flush` when IDs are needed but do not independently commit. This makes the auth bump and route mutation one transaction. Document where SQLite lock/`IntegrityError` exceptions are translated to 409. Alternatively, drop per-request `last_used_at` updates and update it only on login. | 0.94 |
| N5 | High — Phase 4 | Editable `match_name` is neither normalized nor required to be non-empty | **Data model/design:** recipe matching is exact equality against user-editable `match_name`. **PATCH algorithm:** assigns `body.match_name` directly. | Changing a row to `match_name=" Flour "` or `"Flour"` does not match recipe ingredient `normalized_name="flour"`. An empty string creates an effectively unreachable stock row. Collision checking before normalization can also miss that `"Flour"` and `"flour"` should collide. | The feature intended to repair matching can instead disconnect stock or create duplicate logical identities. Users then see false missing/short results. | Run every supplied `match_name` through `normalize_name`, reject an empty result with 422, and perform collision detection on the normalized value. Test casing, surrounding punctuation/whitespace, empty input, and collision after normalization. | 0.97 |
| N6 | Medium — Phase 6 | Partial grocery-line unit edits can change the physical amount by orders of magnitude | **Grocery PATCH:** independently applies optional `quantity` and `unit` fields. Generated lines are said to remain canonical, while manual lines retain typed units. | A generated line is `500 g flour`. `PATCH {unit:"kg"}` leaves the number at 500, so submit adds `500 kg`. It also leaves `source="generated"` even though the response is no longer canonical. Editing item/unit can leave the old `nettable` flag attached to unrelated data. | A normal partial edit through `/docs` can add a wildly incorrect inventory quantity and violate the response-unit contract. | Define quantity/unit as an atomic pair for grocery edits: either require both whenever `unit` changes, or convert the existing quantity so a unit-only change preserves the physical amount. For generated lines, canonicalize the pair before storage or change the line to `source="manual"`; recompute or explicitly clear `nettable` after any item/quantity/unit edit. Add the `500 g` → unit-only `kg` test. | 0.96 |
| N7 | Medium — Phase 5 | The stated cook-deduction schema is not true for non-applied entries and is not validated | **Schema:** says each deduction dict contains `item`, `normalized_name`, requested/deducted units and amounts, before/after, applied, and reason. **Cook pseudocode:** `to_taste`, missing-stock, and incompatible-stock entries omit several of those keys. `CookLogRead` exposes `deductions: list[dict]`. | A client iterating deductions and reading `deducted_unit` or `before` succeeds for applied rows but raises on a `to_taste` or missing-stock row. Because the response type is only `list[dict]`, response validation will not catch drift or misspelled keys. | The promised audit format varies by branch and becomes fragile before the deferred undo/review features consume it. | Add a typed `CookDeductionRead` schema with all keys present and explicitly nullable where inapplicable. Persist/return nulls for `before`, `after`, and units on non-applied rows. Use `list[CookDeductionRead]` in `CookLogRead` even if the database column remains JSON. Test every reason branch against the same key set. | 0.99 |

## Assumptions requiring an explicit decision

- A partially satisfied requirement with additional incompatible stock is
  intended to be uncertain, not a confidently nettable shortfall.
- `match_name` is a canonical server-owned match key even though a user may
  supply its source text.
- A grocery unit-only edit should preserve physical quantity rather than merely
  relabel the existing number.
- `last_used_at` is intended to persist on ordinary authenticated GET requests;
  otherwise the per-request write and its locking cost should be removed.

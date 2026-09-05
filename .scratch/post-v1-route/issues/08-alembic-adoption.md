# Alembic adoption: baseline, startup behaviour, and the live-data procedure

Type: grilling
Status: open
Blocked by: 07
Parent: ../map.md

## Question

There are no migrations. A schema change today means deleting
`backend/recipe.db` — documented in the README as the actual procedure. That is
fine while the database is empty and unacceptable once the household is using
the deployed app.

Nothing currently owns this gate. The deployment spec explicitly excludes
migration infrastructure ("No schema change is required for this deployment")
while simultaneously requiring, in Implementation Decision 11, that "any later
schema-changing upgrade requires a reviewed, data-preserving migration before
it can be used with household data."

Decide:

1. **Baseline.** Autogenerate one migration from the current `Base.metadata`,
   then stamp the deployed database as already at that revision.
2. **Startup behaviour.** Does the lifespan `create_all()` stay? `features.md`
   argues yes — idempotent in dev, and idempotent in production once the
   baseline is applied. Confirm or overturn.
3. **The test seam.** `create_app(test_settings, test_engine)` is the only
   test-database seam and it builds schema via `create_all()`. Migrations must
   not break it, and tests must not become migration-ordered.
4. **SQLite specifics.** Batch mode for ALTER, and the known gaps in Alembic
   autogenerate — a reviewed migration, never a blindly-generated one.
5. **The operator procedure.** Backup → migrate → verify → how to roll back,
   folded into the deployment runbook so a schema upgrade is not a developer
   improvising over live household data.
6. **CI.** What stops a schema change shipping without its migration.

### Depends on

Ticket 07 names the first schema change. The migration procedure should be
designed and rehearsed against a real one rather than in the abstract.

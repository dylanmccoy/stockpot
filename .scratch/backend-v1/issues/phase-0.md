# Phase 0 — Reset and Dependencies

## Goal

Prepare the backend for v1 without changing application behavior.

## Inputs

- Master sequence: [`../plan.md`](../plan.md)
- Dependency choice: [`../decisions.md`](../decisions.md)

## Work

- [x] Add `pwdlib[argon2]` as the sole new v1 runtime dependency.
- [x] Sync the backend environment.
- [x] Delete the local `backend/recipe.db` before schema work begins.
- [x] Confirm `.gitignore` already ignores `*.db`; do not add v2 upload paths.
- [x] Leave `pyproject.toml` test discovery (`testpaths` / `addopts`) unchanged;
      do not introduce mypy or a linter in v1.
- [x] Record any unexpected dependency or environment issue in `../issues.md`.

## Dependency boundary

- Runtime added now: `pwdlib[argon2]` for password hashing.
- Runtime deliberately not added: `pint`, `python-jose` / `pyjwt`, `passlib`,
  `alembic`, `inflect`, `python-multipart`, `recipe-scrapers`, `pytesseract`,
  `Pillow`, any web-search SDK, or any LLM/AI service.
- `httpx` remains in the existing development group for `TestClient`; it is not
  promoted to runtime until the deferred URL-import feature.
- `react-router-dom` belongs to the later frontend effort, not backend v1.

## Verification

- [x] `cd backend && uv sync` succeeds.
- [x] `cd backend && uv run pytest` passes with the existing application.
- [x] No application source file changed in this phase.

## Exit criteria

- [x] Scope fence passed (R-10, [`../plan.md` §Phase scope fence](../plan.md#phase-scope-fence-and-handoff-contract)) —
      the dependency-only diff matched this phase; no deferred dependency or
      behavior was introduced.
- [x] Diff review gate passed (R-6, [`../plan.md` §Execution rules](../plan.md#execution-rules)) —
      the Codex adversarial review of the Phase 0 change.
- [x] Phase complete; update the status table in [`../plan.md`](../plan.md).

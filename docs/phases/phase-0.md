# Phase 0 — Reset and Dependencies

## Goal

Prepare the backend for v1 without changing application behavior.

## Inputs

- Master sequence: [`../plan.md`](../plan.md)
- Dependency choice: [`../decisions.md`](../decisions.md)

## Work

- [ ] Add `pwdlib[argon2]` as the sole new v1 runtime dependency.
- [ ] Sync the backend environment.
- [ ] Delete the local `backend/recipe.db` before schema work begins.
- [ ] Confirm `.gitignore` already ignores `*.db`; do not add v2 upload paths.
- [ ] Leave `pyproject.toml` test discovery (`testpaths` / `addopts`) unchanged;
      do not introduce mypy or a linter in v1.
- [ ] Record any unexpected dependency or environment issue in `../issues.md`.

## Dependency boundary

- Runtime added now: `pwdlib[argon2]` for password hashing.
- Runtime deliberately not added: `pint`, `python-jose` / `pyjwt`, `passlib`,
  `alembic`, `inflect`, `python-multipart`, `recipe-scrapers`, `pytesseract`,
  `Pillow`, any web-search SDK, or any LLM/AI service.
- `httpx` remains in the existing development group for `TestClient`; it is not
  promoted to runtime until the deferred URL-import feature.
- `react-router-dom` belongs to the later frontend effort, not backend v1.

## Verification

- [ ] `cd backend && uv sync` succeeds.
- [ ] `cd backend && uv run pytest` passes with the existing application.
- [ ] No application source file changed in this phase.

## Exit criteria

- [ ] Phase complete; update the status table in [`../plan.md`](../plan.md).

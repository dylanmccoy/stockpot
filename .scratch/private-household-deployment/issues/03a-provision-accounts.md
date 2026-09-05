# 03a: Provision household logins and close registration

**What to build:** The owner can add intended household accounts, then operate with registration closed and equal access for those accounts.

**Blocked by:** None (can start immediately).

**Status:** done

- [x] Provide a controlled local provisioning procedure using existing registration behavior and an explicit target configuration; close the registration window afterward.
  - `backend/app/provision.py` + `backend/scripts/provision.py`: `provision_accounts(database_url, [(username, password), ...])` applies `RegisterRequest` validation and `app.security.hash_password`, with a case-insensitive username check that mirrors `routers/auth.py::register`'s (kept inline — a boundary change, not a domain-service refactor). Explicit target: `--database-url` (defaults to `RECIPE_DATABASE_URL`, echoed). The window is never opened — the script writes to the stopped deployment's database — so "closed afterward" holds by construction and is verified as a real open-then-closed transition by `test_registration_open_then_refused_after_closure`, plus the runbook's `register` -> 403 check.

- [x] Verify two individual accounts can read and edit the same household records, and a further direct registration attempt is refused after closure.
  - `tests/test_provision.py::test_two_provisioned_members_share_read_write_and_registration_is_closed`: provisions `alice` + `bob` into a disposable file DB, drives a real `create_app` TestClient with `allow_registration=False` — alice creates a recipe, bob reads and PUTs it, alice sees bob's edit — then `POST /api/auth/register` → `403 {"detail": "registration disabled"}`.

- [x] Use existing API and auth-test seams with disposable data. Verify the normal frontend build does not advertise signup using existing frontend coverage.
  - Backend: the production application factory + real `TestClient` (the "existing lower seam" the spec names for backend config/auth edge cases), tmp-path SQLite, no mocks/overrides. CLI subprocess tests mirror `test_backup_cli.py` / `test_restore_cli.py`.
  - Frontend no-signup coverage already exists and is unchanged: `frontend/src/pages/Login.test.tsx` "does not render the register form by default" and `frontend/e2e/smoke.production.spec.ts` "registration stays closed: no sign-up UI and the API refuses it" (against the real `npm run build` output).

- [x] Document the provisioning and closure steps without logging credentials or adding roles, memberships, or a new account UI.
  - README.md runbook 6 "Household account provisioning". Passwords are read from an accounts file (or stdin), never argv; the summary prints usernames only; no role/membership/account-UI concepts introduced.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Branch `feat/private-household-deployment-03a`, worktree `.claude/worktrees/private-household-deployment-03a`.
- Full `backend` suite green (`uv run pytest`); 19 new tests across `test_provision.py` / `test_provision_cli.py`.
- Design note: the procedure provisions against the **stopped** deployment's database rather than temporarily enabling `RECIPE_ALLOW_REGISTRATION` and seeding over HTTP. It satisfies spec decision 8's end state (registration closed, confirmed by a 403 check) without ever opening a window an operator could forget to close, and keeps parity with the file-operating `scripts/backup.py` / `scripts/restore.py`. The existing HTTP-seed path (runbook 1, `production-server.mjs`) is left intact for the single-account bootstrap.
- `/code-review` (Standards + Spec) actioned: wrap `SQLAlchemyError` from the write as `ProvisionError` so a locked-DB failure exits 1 with a message, not a traceback; refuse a missing `sqlite:///` file up front instead of leaving a stray 0-byte db; comment the inline mirror of `register`'s username check; add the open->closed transition test; drop a redundant `from app import models` import; trim a forgotten-password sentence from runbook 6 (that is 03b's). Not changed: the direct-DB approach and the idempotent skip-existing behaviour (both reviews judged them defensible; skip-existing serves "add a member later").

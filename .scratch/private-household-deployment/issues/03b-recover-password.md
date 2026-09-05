# 03b: Recover one forgotten household password

**What to build:** The owner can restore a member's account access without changing other accounts or household records.

**Blocked by:** None (can start immediately).

**Status:** in-review

- [x] Provide a local recovery operation with an explicit target database, using existing password hashing and revoking all sessions for the recovered account.
  - `backend/app/recover.py` + `backend/scripts/recover.py`: `recover_password(database_url, username, new_password)` replaces the account's `password_hash` via `app.security.hash_password` (the same facility `POST /api/auth/change-password` uses) and issues `DELETE FROM sessions WHERE user_id = ...`, returning `RecoverResult(username, sessions_revoked)`.
  - Explicit target: `--database-url` (defaults to `RECIPE_DATABASE_URL`, echoed). Writes straight to the stopped deployment's database — not an HTTP path, not a new endpoint. Username matched case-insensitively (mirrors `routers/auth.py`), stored casing preserved.

- [x] Verify old credentials and old sessions fail, fresh login with the replacement password succeeds, and other accounts and household records are preserved.
  - `test_recover.py::test_recovered_member_logs_in_fresh_while_old_credentials_and_tokens_fail` drives the real auth API through the production factory app: old `Bearer` token -> 401, old password login -> 401, new password login -> 200 and reads the same recipe, second member still logs in.
  - `test_replaces_hash_and_revokes_all_sessions` (2 sessions -> 0) and `test_only_the_target_account_is_touched` (other user's hash + live session + recipe intact).

- [x] Unknown accounts and invalid inputs fail without creating accounts or mutating unrelated data. Keep passwords and tokens out of logs and setup artifacts.
  - Unknown username -> `RecoverError("no such account: ...")`, no row created, existing account untouched (`test_unknown_account_is_refused_and_creates_nothing`). Password outside 8-128 -> `RecoverError`, hash unchanged (`test_invalid_password_is_refused_and_changes_nothing`). Missing DB file / no schema also refused.
  - Password read from a file or stdin, never argv; CLI output is username + revoked-session count only. `test_cli_recovers_revokes_sessions_and_never_echoes_the_password` asserts the passphrase appears in neither stdout nor stderr.

- [x] Test through existing real authentication APIs and the application factory using disposable data; document the operator procedure. Existing account setup is sufficient, so 03a is not a blocker.
  - `test_recover.py` (10) uses `create_app(Settings(...), make_engine(...))` + `TestClient` over tmp-path SQLite, seeding via `provision_accounts`; `test_recover_cli.py` (8) runs `scripts/recover.py` as a subprocess like `test_provision_cli.py`. No mocks, no dependency overrides.
  - Operator procedure: README.md runbook 7 "Household password recovery".

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Branch `feat/private-household-deployment-03b`, worktree `.claude/worktrees/private-household-deployment-03b`.
- Full `backend` suite green (`uv run pytest`): 831 passed, 18 new across `test_recover.py` / `test_recover_cli.py`.
- Design note: mirrors 03a's shape — a direct-DB operation against the **stopped** deployment plus a file/stdin CLI, parity with `scripts/backup.py` / `restore.py` / `provision.py`. Session revocation reuses the exact `delete(SessionModel).where(user_id == ...)` that `change-password` performs, so a snapshot-era or pre-recovery token cannot be replayed. No reset endpoint, email service, or account UI (spec decision 9).

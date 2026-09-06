# 02c: Restore an existing database safely while stopped

**What to build:** The owner can replace a stopped household database with a validated recovery copy while retaining the database they are replacing.

**Blocked by:** 02b: Recover a snapshot into a separate database.

**Status:** done

- [x] Extend recovery to an explicitly selected existing database with application writers stopped. Preserve a valid copy of the current database before replacement and refuse to replace it if preservation or validation fails.

- [x] Prepare and validate the recovered database, including restored-session invalidation, before replacing the configured target. Keep earlier snapshots and the original source untouched.

- [x] Using test-owned processes and disposable data, stop writers, execute the recovery procedure, restart the app against the target, and verify recovered records through fresh login and API reads.

- [x] Test invalid snapshot, failed preservation, and failed preparation paths without destroying the usable target. Document the stop/preserve/restore/restart procedure; deployment-specific process controls are supplied later.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.


## Comments

- Implemented on branch `feat/private-household-deployment-02c`, worktree
  `.claude/worktrees/private-household-deployment-02c`.

- `backend/app/restore.py` gains `replace_database(snapshot, target, *,
  preserve_dir)` + a `ReplaceResult(target, preserved)` dataclass. Order:
  validate `snapshot` -> `create_backup(target, preserve_dir)` to preserve the
  current DB -> `_validate_snapshot(preserved)` -> prepare a temp copy beside
  `target` (`_prepare_recovered_copy`: copy, wipe `sessions`, `chmod 0600`,
  extracted and now shared with `recover_snapshot`) -> `_validate_snapshot`
  the temp -> single atomic `tmp.replace(target)`. Any failure before the
  rename raises `RestoreError` with `target` byte-for-byte unchanged; a failed
  or invalid preservation refuses outright so the replaced DB is never given
  up on a bad recovery point. `target` must already exist (opposite of
  `recover_snapshot`). Snapshot, earlier snapshots, and (until the swap)
  `target` are only read.

- CLI: `scripts/restore.py` gains `--replace` + `--preserve-dir` (rehearsal
  mode unchanged). `--replace` needs `--preserve-dir` and an existing
  `--target`; prints `restore ok: replaced <target>` and `preserved prior
  database: <path>`.

- Tests (green, `backend` CI job via `uv run pytest`; full suite 866 passed):
  `backend/tests/test_replace.py` (12) drives the production app factory end
  to end -- seed a live DB, snapshot, diverge, `replace_database`, then a
  *fresh* factory app on the same path sees the snapshot's world, not the
  divergence; the preserved copy still holds the divergence; the snapshot's
  password authenticates after replacement while a post-snapshot rotation does
  not; snapshot-era + pre-snapshot-revoked sessions are dead, fresh login
  works; earlier snapshots + source untouched; replaced file is `0600`;
  invalid-snapshot / failed-preservation / failed-preparation / corrupt-target
  all leave the usable target intact. `test_restore_cli.py` gains 6 subprocess
  cases (5 for `--replace`, 1 for the `--preserve-dir` guard).

- Docs: root `README.md` runbook 13 "Restore in place (replace the live
  database)" documents stop -> preserve -> restore -> restart; runbook 5
  cross-links it; `backend/CLAUDE.md` file map and `docs/deployment.md`
  outline item 5 updated.

- Merged via PR [#91](https://github.com/dylanmccoy/stockpot/pull/91)
  (squash), CI green (`backend`, `frontend`, `integration`, `production-smoke`,
  `deployment`). Rebased onto `main` past #90 (05b); the new runbook is **13**
  (05b took 12).

- Reviewed with `/code-review` (Standards + Spec).
  - Actioned: dropped an untested `now=` passthrough param on
    `replace_database` (Standards + Spec: speculative generality); collapsed
    the CLI's duplicated `except RestoreError` blocks into one try (Standards:
    duplicated code); added the snapshot-vs-later-password login test (Spec:
    "verify recovered passwords ... through login") and a CLI test for the
    `--preserve-dir` without `--replace` guard.
  - Deliberately skipped: extracting a shared `tests/_filedb.py` for the
    `_settings`/`_client`/`_seed_live_db` helpers now triplicated across
    `test_backup`/`test_restore`/`test_replace` -- 02b consciously accepted
    this same per-file fixture duplication; a cross-file test refactor is out
    of this slice's scope. The literal "stop app -> replace -> restart the
    same process" sequence is exercised only as factory-app open/close, not a
    supervised process -- spec item 14 defers deployment-specific process
    controls to later tickets (06a+/07c), and 02b set this precedent. Kept
    the `0600` assertion on the replaced file: the chmod lives in the
    `_prepare_recovered_copy` code this slice touches, so a check on it is
    appropriate.

# 02b: Recover a snapshot into a separate database

**What to build:** The owner can rehearse recovery in a separate database and sign in to inspect the recovered household without changing live data.

**Blocked by:** 02a: Take a usable live SQLite snapshot.

**Status:** in-review

- [x] Validate a selected snapshot and restore into a new explicit target, refusing an already existing target in this slice. Leave the live database and original snapshot unchanged.

- [x] Invalidate sessions in the recovered database before it is served; a fresh login succeeds and restored tokens are refused.

- [x] Take a snapshot, make a distinguishable later change, recover into a new disposable target, and use a fresh factory-built app to verify the snapshot's records and absence of the later change.

- [x] Reject missing or invalid snapshots without exposing an apparently successful recovered database. Document isolated rehearsal and put these real restore checks in CI.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.


## Comments

- Implemented on branch `feat/private-household-deployment-02b`, worktree
  `.claude/worktrees/private-household-deployment-02b`.

- `backend/app/restore.py` (`recover_snapshot`: validate snapshot via a
  space-safe `file:` URI + `PRAGMA integrity_check` + full-schema table check
  against `Base.metadata`; refuse an existing target; `copyfile` → wipe
  `sessions` → `chmod 0600` → atomic `replace`; snapshot and live DB only ever
  read) + `backend/scripts/restore.py` (operator CLI, both paths explicit,
  `restore ok:` / `restore failed:` + exit 0/1).

- Tests: `backend/tests/test_restore.py` (10) + `test_restore_cli.py` (4),
  running in the existing `backend` CI job via `uv run pytest`:
  snapshot→diverge→recover round-trip through the app factory (snapshot
  records present, later change absent); snapshot-era tokens refused and a
  session revoked *before* the snapshot stays dead while fresh login +
  recovered password work; live DB and snapshot byte-unchanged; existing
  target refused; missing / garbage / non-recipe-schema snapshots create no
  target; recovered file is `0600`; a snapshot path containing a space
  recovers cleanly. Full suite: 794 passed.

- Documented as runbook 5 ("Restore rehearsal (isolated database)") in root
  `README.md`; `restore.py` added to `backend/CLAUDE.md`'s file map.

- Reviewed with `/code-review` (Standards + Spec). Actioned: space-unsafe
  `file:` URI (now `pathname2url`); table check widened from 3 hardcoded
  names to the full `Base.metadata` schema (README "the application's tables"
  claim now accurate); broadened the validation `except` to `sqlite3.Error`;
  added the explicit revoked-session-not-revived test; aligned the CLI-test
  `_run` helper with its 02a sibling. Deliberately skipped: extracting a
  shared atomic-publish helper from `backup.py` (only two call sites, real
  behavioural differences — revisit if 02c adds a third); per-file test
  fixture duplication (matches 02a); `chmod 0600` on the rehearsal DB and
  `mkdir -p` of its parent (kept as sensible hygiene / ergonomics, noted in
  code comments).

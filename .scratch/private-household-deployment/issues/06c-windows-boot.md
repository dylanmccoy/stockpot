# 06c: Restore private access after Windows boot without login

**What to build:** The private household app returns after a full Windows reboot without the owner signing in or opening a terminal.

**Blocked by:** 06b: Keep WSL serving after terminals close; 05a: Reach the app from a permitted private-network client.

**Status:** in-review

- [x] Add repeatable Windows boot startup for the intended user/distribution and existing WSL lifetime arrangement. Ensure private Tailscale ingress also runs unattended.
  - `deploy/windows/register-keeper-task.ps1` gains an `AtStartup` trigger (with `AtLogOn` + the repetition), so the same S4U-principal `RecipeAppWslKeeper` task starts `wsl.exe -d <distro> -- bash <checkout>/deploy/wsl-keeper.sh run` before any interactive logon. `-Force` re-registration and `-NoBootTrigger` keep it repeatable; the script reads the task back and warns if the boot trigger did not attach.
  - `RECIPE_DEPLOY_KEEPER_SERVE=1` (`deploy/lib.sh`, `deploy/wsl-keeper.sh`) has the keeper run `deploy/tailscale-serve.sh apply` while it holds the app up, re-checking each heartbeat and re-applying only on drift — so the private HTTPS ingress returns unattended too. Paired with Tailscale "Run unattended" on Windows (README runbook 18 step 2).

- [ ] On the target machine, reboot Windows and verify the private HTTPS origin becomes usable from a permitted client before interactive login.
  - Not run — actual-host gate. Procedure + record sheet: `host-acceptance-06c.md` checks 3–4; README runbook 18 step 4.

- [ ] Log in to the app, read previously saved records, and save a new change. Verify retries/repeated setup do not launch duplicate instances.
  - "No duplicate instances on retry / repeated setup" **is** covered deterministically: `test_keeper_does_not_re_apply_an_ingress_that_is_already_mapped` (new) plus the ticket-06b `test_keeper_run_refuses_a_second_keeper_and_never_duplicates` / relaunch cases. The log-in / read / save-after-reboot half is the actual-host gate (`host-acceptance-06c.md` checks 5–6).

- [ ] Record actual reboot results and document failure diagnosis and manual recovery using existing controls. CI or mocked task configuration cannot substitute for this acceptance check.
  - Documented: README runbook 18 (walk-through + diagnosis / manual-recovery table) and the `host-acceptance-06c.md` failure-rehearsal row (check 14). Recording the actual reboot results is the pending host step.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-06c`, worktree `.claude/worktrees/private-household-deployment-06c`.
- Scope of the code slice: at-boot Task Scheduler trigger on the existing keeper task + opt-in unattended Tailscale ingress (`RECIPE_DEPLOY_KEEPER_SERVE`) + README runbook 18 + `docs/deployment.md` + 3 `backend/tests/test_deploy.py` cases + `host-acceptance-06c.md`. No frontend, backend-app, schema, or auth changes.
- Two-axis `/code-review` run: no hard standards violations; findings actioned — strict `1/0` flag parse, serve-target derived from `deploy_serve_target`, keeper self-heals a dropped Serve mapping (dropped the one-shot latch) and gives up cleanly when the Tailscale CLI is absent, added the no-double-`apply` test. `uv run pytest` green (906).
- Remaining before `done`: the actual-host acceptance in `host-acceptance-06c.md` (reboot without login, Tailscale unattended, no-duplicate on retry on the real host).

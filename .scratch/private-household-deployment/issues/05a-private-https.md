# 05a: Reach the app from a permitted private-network client

**What to build:** A household member can use one private HTTPS address from a permitted computer, while other devices cannot reach the deployment.

**Blocked by:** 04a: Install the WSL app with existing household data; 01b: Reload bookmarked pages without breaking API errors.

**Status:** in-review

Every AC below has a host-dependent verification step ("verify… on a permitted
client", "inspect…", "record actual-host results") that cannot be met without
the target Windows/WSL machine and a second device. The deterministic,
CI-provable half is built and green; the boxes stay unchecked until the
`host-acceptance-05a.md` rows are filled in on the target host. Per the
delivery constraint: *"CI alone is not evidence of Windows/Tailscale behavior."*

- [ ] Inspect Windows-to-WSL localhost connectivity and configure Windows Tailscale Serve to proxy the local production origin. Configure persistent Serve and unattended Tailscale operation.
      — **built:** `deploy/tailscale-serve.sh apply` runs `tailscale serve --bg --https=<port> http://127.0.0.1:<port>` (`--bg` = persistent config in tailscaled state). README runbook 11 gives the PowerShell `curl.exe` localhost inspection step, `.wslconfig localhostForwarding`, and enabling Tailscale "Run unattended".
      — **host-pending:** the localhost inspection and the unattended toggle are actions on the Windows host — `host-acceptance-05a.md` #1, #14.

- [ ] Restrict access to intended household identities/devices from the start. Keep application listeners local; do not enable Funnel, public port forwarding, or a LAN/public bypass.
      — **built:** app listener stays `--host 127.0.0.1` (unchanged `deploy/control.sh`); `tailscale-serve.sh apply` refuses while Funnel is active and prints a prominent WARNING that the tailnet must be restricted before the address is shared; `deploy/net-check.sh` fails on a non-loopback listener on the app port, on an active Funnel, on an unconfirmable Funnel state, or if Serve is unset.
      — **host-pending:** the tailnet-ACL restriction itself is an admin-console step (needs tailnet admin, not the host) — `host-acceptance-05a.md` #4; off-tailnet unreachability #11–#12.

- [ ] From a permitted client, verify valid HTTPS, login, read/write, and direct-link reload. Verify rejected unauthenticated API access, closed registration, and inability to connect from outside the permitted private network.
      — **built:** the app-behaviour half (login, read/write, direct-link reload, unauthenticated `401`, registration `403`) is exercised against the one-origin deployed build by the `deployment` Playwright project (ticket 04a); 05a fronts that same origin unchanged, so no new browser test was added for it.
      — **host-pending:** valid HTTPS + the Tailscale-provisioned cert, and off-tailnet unreachability, need the real tailnet and a second device — `host-acceptance-05a.md` #5–#12.

- [ ] Verify recovery after restarting Tailscale with the app running. Supply repeatable setup and connectivity diagnostics, and record actual-host results.
      — **built:** `deploy/net-check.sh` is the repeatable diagnostic (6 checks, non-zero on any failure *or any check it cannot confirm*); `tailscale-serve.sh apply` is idempotent and `--bg` persistence means a Tailscale restart self-recovers. Deterministic coverage in `backend/tests/test_deploy.py`.
      — **host-pending:** the actual Tailscale-restart recovery run and the recorded results — `host-acceptance-05a.md` #13, and the whole checklist.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.


## Comments

- Implemented on branch `feat/private-household-deployment-05a`, worktree
  `.claude/worktrees/private-household-deployment-05a`.

- **`deploy/tailscale-serve.sh`** (new) — configure Windows Tailscale Serve to
  front the deployment's local origin, private to the tailnet:
  - `apply` — `tailscale serve --bg --https=$RECIPE_DEPLOY_HTTPS_PORT
    http://127.0.0.1:$RECIPE_DEPLOY_PORT`. `--bg` persists the mapping in
    tailscaled state (survives a Tailscale / Windows restart). Refuses if
    Funnel is active or the local origin is not answering `/api/health` — never
    fronts a dead port or a public exposure. Idempotent (re-apply = the
    recovery step).
  - `status` — Serve mapping + node state + Funnel state (must be off).
  - `url` — the `https://<magicdns-name>/` address, parsed from
    `tailscale status --json` `.Self.DNSName`.
  - `reset` — clear this node's Serve config.

- **`deploy/net-check.sh`** (new) — repeatable connectivity diagnostics, run
  after setup and after any Tailscale/WSL/Windows restart. Six checks, PASS/FAIL,
  non-zero exit on any failure **or any check that cannot confirm its
  invariant**:
  1. app answers on `127.0.0.1:<port>`;
  2. **nothing** is listening on `<port>` on a non-loopback address (LAN/public
     bypass) — via `ss`; fails closed if `ss` is unavailable;
  3. Tailscale up / backend Running;
  4. Serve maps the tailnet HTTPS port to the local origin;
  5. Funnel OFF *and confirmed so* (an erroring `funnel status` fails the check);
  6. the tailnet HTTPS URL resolves (+ a copy-paste `curl` hint for a permitted
     client).
  `--local-only` runs 1–2 (usable from inside WSL without the Windows CLI).

- **`deploy/lib.sh`** — new config `RECIPE_DEPLOY_TAILSCALE_BIN` (default
  `tailscale.exe`, the WSL topology) and `RECIPE_DEPLOY_HTTPS_PORT` (default
  443), printed by `deploy_print_config`. New shared helpers: `deploy_serve_target`
  (the one definition of the local origin), `deploy_tailscale` (run the
  configured CLI), `deploy_funnel_state` (`on` / `off` / `unknown`),
  `deploy_tailnet_url` (`.Self.DNSName` via the configured Python — see review).
  No behaviour change to install/control/update/rollback.

- **`deploy/deploy.env.example`** — documents the two new vars under a "private
  HTTPS ingress" block.

- **Tests** — `backend/tests/test_deploy.py` +9 (in the `backend` CI job),
  driving both scripts as subprocesses against a **stub** `tailscale` CLI
  (argv logged, tiny serve-state file, `--json` carries a decoy `.Peer`) — no
  tailnet, no credentials, deterministic:
  - `net-check` passes for a healthy loopback deployment + clean tailnet;
    fails when Funnel is on, when Funnel state is unknowable, and on a
    `0.0.0.0` listener on the app port; `--local-only` skips the Tailscale
    checks and needs no CLI.
  - `tailscale-serve apply` invokes `serve --bg --https=443
    http://127.0.0.1:<port>` and the mapping shows through `status`; refuses
    on an active Funnel and on a dead local origin (configuring nothing);
    `url` prints the MagicDNS `https://…/` from `.Self` (not the decoy peer).
  - Full `backend` suite green; no new CI job (deterministic checks live in
    the existing `backend` job, per the spec's "no real Tailscale credentials
    in CI").

- **Docs** — README "Operating the server" **runbook 11 · Private HTTPS
  ingress (Tailscale Serve)**: Windows→WSL localhost check, `tailscale-serve.sh`
  usage, tailnet ACL restriction (admin console), unattended operation,
  `net-check.sh` verification, the permitted-client acceptance list, restart
  recovery, and the never-do list (Funnel / port-forwarding / `0.0.0.0`).
  Runbook count 10 → 11; runbook 8's forward-reference updated.
  `docs/deployment.md` outline item 2 points at the scripts + runbook 11.

- **Host acceptance** — `.scratch/private-household-deployment/host-acceptance-05a.md`
  (new): 14-row checklist for the real Windows/WSL/tailnet checks CI cannot
  prove (HTTPS cert, tailnet ACL, off-tailnet unreachability, Tailscale-restart
  recovery, unattended operation). All rows PENDING — no such host in this
  session. Linux CI (`backend` + existing `deployment` jobs) is green.

- Reviewed with `/code-review` (Standards + Spec). Findings actioned:

  **Standards axis:**
  - Renamed `deploy_ts` → `deploy_tailscale` to match the spelled-out prior
    art (`deploy_http_ok`, `deploy_wait_health`, …).
  - `deploy_tailnet_url` no longer text-scrapes `status --json` with `grep |
    head -1` (which depended on Go marshalling `.Self` before `.Peer`); it now
    parses with `"$RECIPE_DEPLOY_UV_BIN" run python`, the sanctioned fallback
    tool `deploy_http_ok` already uses. A stub `.Peer` decoy locks it.
  - Dropped the ~20-line `/proc/net/tcp{,6}` fallback in `net-check.sh`
    (Speculative Generality — no coverage, `ss` is always present on the WSL
    target). `ss`-only; the check fails closed if `ss` is missing.
  - `deploy_serve_target` is now the single origin definition; `net-check.sh`
    derives its host:port from it instead of re-inlining `127.0.0.1:<port>`.

  **Spec axis:**
  - All four AC boxes set back to `[ ]` — every one has a host-dependent
    "verify…/inspect…/record actual-host results" step that is PENDING;
    `Status: in-review` with the built-vs-verified split above.
  - `tailscale-serve.sh apply` now prints a prominent multi-line WARNING that
    Serve is reachable to every tailnet node and the ACL restriction +
    unattended operation must be done before sharing the address ("restrict…
    from the start").
  - `net-check.sh` check 5 fails (not passes) when `funnel status` cannot be
    run — no more misleading "Funnel is off" when the state is unknowable.
  - Completed this truncated "Findings actioned" list (was a dangling edit).

  **Deliberately not changed:**
  - No automated check for the tailnet-ACL dimension of "cannot connect from
    outside" — it needs tailnet admin / a second device, so it stays a host
    row (`host-acceptance-05a.md` #4, #11–#12). `net-check.sh` covers the
    LAN-listener / Funnel / public-exposure dimensions it *can* see.
  - `RECIPE_DEPLOY_HTTPS_PORT` and the `reset` subcommand kept — the reviewer
    called them "cheap operational counterparts"; `reset` is needed for
    iteration and recovery, and the port is a host input like every other
    value in `deploy.env`.

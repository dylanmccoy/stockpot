# 05b: Connect a household phone over cellular

**What to build:** A household member can enroll their phone, connect Tailscale, and use the private app while away from home.

**Blocked by:** 05a: Reach the app from a permitted private-network client.

**Status:** done

The one deterministic AC (iOS + Android onboarding docs) is written. The
other three each require a real household phone on a real tailnet against
the #11 ingress — they stay unchecked until the
`host-acceptance-05b.md` rows are filled in on the actual device. Per the
delivery constraint: *"CI alone is not evidence of Windows/Tailscale
behavior."*

- [x] Provide household phone onboarding for iOS and Android, distinguishing private-network connection from application login and explaining that internet connectivity is required.
      — **built:** README "Operating the server" **runbook 12 · Household phone
      onboarding (iOS / Android)** — separate iOS / Android install + tailnet
      sign-in steps, an explicit "two separate things" split (tailnet reach vs.
      app account, neither sufficient alone), and a stated "no offline mode —
      the phone always needs working internet" plus a both-radios-off check.
      `docs/deployment.md` outline item 2 points at it; runbook count 11 → 12.

- [ ] On an actual household phone, turn off Wi-Fi, connect through Tailscale, open the private HTTPS address, log in, read a recipe, save a change, and reload a nested route.
      — **host-pending:** needs a real phone on cellular + the live tailnet —
      `host-acceptance-05b.md` #1–#6. The underlying app behaviour is already
      covered against the one-origin production serving: login + a
      write-that-survives-reload in the `deployment` project
      (`e2e/smoke.deployment.spec.ts`, 04a); nested-route direct load / reload
      in the `production` project (`e2e/smoke.production.spec.ts`, 01b). 05b
      fronts that same origin unchanged, so no new browser test was added.

- [ ] Verify the change from another permitted client and exercise disconnect/reconnect followed by another successful read. Retain the existing session and error behavior.
      — **host-pending:** cross-client verification and Tailscale
      disconnect/reconnect need real devices — `host-acceptance-05b.md`
      #7–#11. Session hydration on reload, invalid-session redirect, and
      logout are CI-covered against the one-origin production serving by the
      `production` project (`e2e/smoke.production.spec.ts`, 01b); `401`
      without a token by both projects. Unchanged here.

- [ ] Record the actual mobile platform tested and any unperformed device checks. This is mobile onboarding and network commissioning of the existing browser app, not a native app or offline feature.
      — **host-pending:** `host-acceptance-05b.md` has the "Platform coverage"
      section and per-check rows ready; all PENDING — no household phone in
      this session.

## Delivery constraints

- Include the relevant operator instructions and observable tests with this slice. Keep existing checks green; do not introduce red placeholder tests or defer this slice's essential safety checks.

- Reuse the existing real-backend browser or application-factory seams with disposable data and owned processes. Run checks appropriate to the touched code. Host-dependent acceptance requires recorded results on the target machine; CI alone is not evidence of Windows/Tailscale behavior.

- Preserve the parent spec's scope: one private household, existing domain/API behavior and schema, local SQLite and local backups. No public hosting, multi-household work, or authentication redesign.

## Comments

- Implemented on branch `feat/private-household-deployment-05b`, worktree
  `.claude/worktrees/private-household-deployment-05b`.

- **Docs only — no code, no new tests.** This slice is phone commissioning of
  the existing browser app (the ticket: *"not a native app or offline
  feature"*). The app behaviour the on-phone ACs exercise is already covered
  against the one-origin production serving (no dev proxy) by two Playwright
  projects: `deployment` (`e2e/smoke.deployment.spec.ts`, 04a) — adopted-account
  login, a write that persists across a reload, `401` without a token,
  registration `403`; and `production` (`e2e/smoke.production.spec.ts`,
  01a / 01b) — nested-route direct load / reload, session hydration on reload,
  invalid-session redirect, wrong password, logout. 05b fronts that same
  origin unchanged, so, as with 05a, no new browser test was added.

- **README "Operating the server" runbook 12 · Household phone onboarding
  (iOS / Android)** (new):
  - separate iOS (App Store / Safari) and Android (Play Store / Chrome)
    install + tailnet sign-in + VPN-enable steps, incl. connect-on-demand /
    always-on VPN for unattended reconnect;
  - an explicit **"two separate things"** split — tailnet reach (owner adds the
    identity to the tailnet, must be inside the runbook 11 §3 ACL) vs. the
    person's own app account (runbook 6 / 7); neither alone gets them in;
  - states **internet is always required** — "no offline mode" — with a
    both-radios-off check;
  - cellular check (Wi-Fi off), Tailscale off/on reconnect keeping the session,
    and a troubleshooting list (name doesn't resolve / cert warning / API
    calls fail).
  - Runbook count 11 → 12; runbook 8's forward-reference updated.
  - `docs/deployment.md` outline item 2 now points at runbook 12.

- **Host acceptance** —
  `.scratch/private-household-deployment/host-acceptance-05b.md` (new):
  12-row checklist + host-inputs + "Platform coverage" section for the real
  iOS/Android-on-cellular checks CI cannot prove (tailnet enrolment, HTTPS
  cert on the phone, save-and-reload, cross-client verification,
  disconnect/reconnect, both-radios-off). All rows PENDING — no household
  phone in this session. Prerequisite: `host-acceptance-05a.md` rows PASS.

- Linux CI (`backend` + existing `deployment` / frontend jobs) is unaffected —
  the change is Markdown only.


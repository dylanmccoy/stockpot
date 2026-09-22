# 05b — actual-host acceptance results

Ticket: `issues/05b-phone-access.md` — connect a household phone over cellular.

This slice is phone commissioning of the existing browser app. It has **no**
CI-provable surface of its own:

- the app behaviour it relies on is already covered against the one-origin
  production serving (no dev proxy) by the `deployment` project
  (`e2e/smoke.deployment.spec.ts`, ticket 04a — adopted-account login, a write
  that persists across a reload, `401` without a token, registration `403`)
  and the `production` project (`e2e/smoke.production.spec.ts`, tickets
  01a / 01b — nested-route direct load / reload, session hydration on reload,
  invalid-session redirect, wrong password, logout);
- everything in this file needs a real household phone, a real tailnet, and the
  #11 ingress live on the target host — it is **not** satisfied by CI.

Fill in `Result` / `Date` / `By` / `Notes` on the actual device and commit
this file.

Runbook: README "Operating the server" #12 (phone onboarding), building on #11
(Tailscale Serve ingress). Prerequisite: `host-acceptance-05a.md` rows PASS.

## Host inputs (record actuals — do not assume)

| Input | Value |
| --- | --- |
| Mobile platform + OS version |  |
| Device model |  |
| Tailscale app version |  |
| Browser + version (Safari / Chrome) |  |
| Tailnet HTTPS URL (`deploy/tailscale-serve.sh url`) | https://desktop-1q36rl8-1.tailb7b3a1.ts.net/ |
| Tailscale identity used for the phone |  |
| Second permitted client used for cross-check |  |
| Cellular carrier / network type (for the Wi-Fi-off run) |  |

## Checks

| # | Check | Expected | Result | Date | By | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Install Tailscale on the phone, sign in to the household tailnet, enable the VPN | phone shows connected; appears in the tailnet device list; covered by the #11 ACL rule | PASS | 2026-09-22 | dylan |  |
| 2 | Wi-Fi **off** (cellular only), Tailscale on — open the URL from `tailscale-serve.sh url` in Safari / Chrome | page loads over valid HTTPS, **no** certificate warning | PASS | 2026-09-22 | dylan |  |
| 3 | Log in with the member's own app account | succeeds — Tailscale membership and app login are separate | PASS | 2026-09-22 | dylan |  |
| 4 | Read a recipe | opens and renders | PASS | 2026-09-22 | dylan |  |
| 5 | Save a change, then reload | change persists (re-read after reload) | PASS | 2026-09-22 | dylan |  |
| 6 | Open / reload a nested direct link `https://<host>/recipes/<id>` | route loads, no server error page | PASS | 2026-09-22 | dylan |  |
| 7 | Verify the step-5 change from a second permitted client (desktop) | the change is visible there | PASS | 2026-09-22 | dylan |  |
| 8 | Toggle Tailscale **off** on the phone | address stops resolving / app unreachable | PASS | 2026-09-22 | dylan |  |
| 9 | Toggle Tailscale **on** again, return to the app, read a recipe | loads again; existing login session retained (no re-login unless genuinely expired) | PASS | 2026-09-22 | dylan |  |
| 10 | Session / error behaviour retained on mobile: reload keeps the session; `curl https://<host>/api/recipes` with no token; **Log out** | reload stays signed in; `curl` → `401`; logout ends the session and returns to login | PASS | 2026-09-22 | dylan |  |
| 11 | Expired / invalid session on the phone (clear the token or wait it out) | returns to the login screen via the normal flow; sign-in restores access | PASS | 2026-09-22 | dylan |  |
| 12 | Both cellular data **and** Wi-Fi off | Tailscale cannot connect; app unreachable — confirms no offline capability | PASS | 2026-09-22 | dylan |  |

## Platform coverage

- Platform actually tested: iOS
- Platform **not** tested on real hardware this pass: Android, don't have don't care
- Other unperformed device checks: _pending_

## Sign-off

- Commissioned by: dylan
- Date: 2026-09-22
- Deviations from the documented onboarding (if any): none

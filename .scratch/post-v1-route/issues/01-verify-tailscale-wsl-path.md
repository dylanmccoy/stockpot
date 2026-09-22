# Verify the Tailscale → Windows → WSL network path on the target host

Type: task
Status: resolved
Blocked by: —
Parent: ../map.md

## Question

Does the deployment spec's network topology actually work on the owner's
machine? The whole deployment track rests on a three-hop composition nobody has
run:

  Windows Tailscale Serve (HTTPS) → Windows localhost port → WSL app listener

The spec is candid that this is assembled from two separately-documented
behaviours and "must be verified on the target host"
(`.scratch/private-household-deployment/spec.md`, Implementation Decision 5 and
Further Notes). Every acceptance check downstream assumes it holds.

Not a decision — manual work. HITL: it needs the owner's Windows machine and
Tailscale account.

### Checklist

1. Confirm the host's Windows build, WSL version, WSL networking mode
   (NAT vs mirrored), and installed Tailscale version.
2. Run a trivial HTTP listener inside WSL. Confirm it is reachable from
   Windows on `localhost:<port>`.
3. `tailscale serve` that Windows localhost port over HTTPS. Confirm a second
   tailnet device reaches it in a browser with no certificate warning.
4. Confirm a non-tailnet device cannot, and that no LAN or public listener
   bypasses the ingress.
5. Reboot Windows without interactive login. Confirm the path returns
   unattended — WSL is the suspect hop
   ([systemd does not keep WSL alive](https://learn.microsoft.com/en-us/windows/wsl/systemd)).
6. Restart Tailscale, then restart WSL. Confirm recovery after each.

### Answer records

Verified 2026-09-22 during `.scratch/private-household-deployment/` ticket 08
host commissioning. Full evidence: `host-acceptance-04.md`, `-05a.md`, `-06b.md`,
`-06c.md`.

**Versions / mode (step 1).** Windows 11 Pro, build 10.0.26200.9168. WSL
2.7.12.0, kernel 6.18.33.2-2, distro Ubuntu. No `networkingMode` set in
`.wslconfig` → **NAT** (not mirrored); `localhostForwarding=true`. Tailscale
1.102.4 (Windows).

**All six steps passed — no fallback topology needed:**

2. Windows→WSL localhost: `curl.exe http://127.0.0.1:8000/api/health` → `200`
   (`host-acceptance-05a.md` #1).
3. `tailscale-serve.sh apply` + `net-check.sh` all green; a second tailnet
   device loaded the HTTPS URL with no cert warning (05a #2–3, #5).
4. Tailnet ACL admits only household devices; an off-tailnet device could not
   resolve/reach it; no LAN/public listener bypassed the ingress (05a #4, #11,
   #12).
5. Full Windows reboot, **stayed at the sign-in screen** (no interactive
   login) — the app was reachable over HTTPS, login/edit/reload all worked,
   before any Windows session existed (06c #3–8). The suspected weak hop
   (WSL not staying up without a login) held: the keeper's `AtStartup` Scheduled
   Task trigger (S4U logon type) starts `wsl.exe`, which itself boots the
   distro — no interactive session required.
6. Restarted Tailscale with the app running → ingress self-recovered, `net-check.sh`
   passed again (05a #13). Controlled `wsl --shutdown` → the keeper Scheduled
   Task relaunched WSL, supervisor, and app with no shell opened, data intact
   (06b #7).

No hop needed extra configuration beyond what the deployment spec already
documents (`tailscale-serve.sh`, the wsl-keeper Scheduled Task, S4U logon). The
"fallback host topology" fog in `map.md` is retired — nothing to design.

# Verify the Tailscale → Windows → WSL network path on the target host

Type: task
Status: open
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

The versions and networking mode found, which hops needed configuration, and
which of steps 2–6 failed. A failure at step 5 or 6 is the interesting case: it
graduates the map's "fallback host topology" fog into a real ticket.

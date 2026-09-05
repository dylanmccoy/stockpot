# Private household deployment tickets

The 19 approved slices implement the [deployment spec](../spec.md). Each
ticket is marked `ready-for-agent`; start it only after all its blockers
are complete. Lettered IDs preserve the seven agreed feature groups.

Initial available tickets: **01a, 01c, 02a, 03a, 03b**.

| Ticket | Delivers | Blocked by |
| --- | --- | --- |
| [01a](01a-production-entry.md) | Open and use the built app at its entry address | None |
| [01b](01b-direct-links.md) | Reload bookmarked pages without breaking API errors | 01a |
| [01c](01c-ci-real-backend-integration.md) | Gate changes on the real-backend browser integration suite | None |
| [02a](02a-create-snapshot.md) | Take a usable live SQLite snapshot | None |
| [02b](02b-restore-isolated.md) | Recover a snapshot into a separate database | 02a |
| [02c](02c-replace-stopped-database.md) | Restore an existing database safely while stopped | 02b |
| [03a](03a-provision-accounts.md) | Provision household logins and close registration | None |
| [03b](03b-recover-password.md) | Recover one forgotten household password | None |
| [04a](04a-install-persistent-app.md) | Install the WSL app with existing household data | 01a, 02a |
| [04b](04b-update-app.md) | Deploy a schema-preserving application update | 04a |
| [04c](04c-return-compatible-build.md) | Return to a previous compatible app build | 04b |
| [05a](05a-private-https.md) | Reach the app from a permitted private-network client | 04a, 01b |
| [05b](05b-phone-access.md) | Connect a household phone over cellular | 05a |
| [06a](06a-process-supervision.md) | Restart a failed app inside a running WSL distribution | 04a |
| [06b](06b-wsl-lifetime.md) | Keep WSL serving after terminals close | 06a |
| [06c](06c-windows-boot.md) | Restore private access after Windows boot without login | 06b, 05a |
| [07a](07a-schedule-snapshots.md) | Create daily snapshots without an open terminal | 04a |
| [07b](07b-backup-health.md) | Report backup freshness and manage local retention | 07a |
| [07c](07c-restore-scheduled-snapshot.md) | Recover the deployed app from a scheduled snapshot | 07a, 02c |

Each slice includes its behavior checks and operator instructions. Use the
existing real-backend browser/application-factory seams and disposable data.
Actual Windows, WSL, Tailscale, phone, and scheduled-task checks require
recorded host results; passing local CI does not establish those outcomes.

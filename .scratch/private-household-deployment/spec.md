# Private household deployment on Windows/WSL with Tailscale

Status: ready-for-agent

## Problem Statement

The owner wants household members to use their recipes, food inventory, cooking
history, and grocery lists away from home, including from phones at the store.
The current application is operated as a trusted-LAN development stack. Its
development servers, manual database backups, and terminal-dependent startup do
not provide a dependable household deployment.

The owner already has an always-on Windows machine with WSL and accepts
installing Tailscale on household devices. They want to use that machine now,
keep backups on its local disk, and postpone paid hosting and support for
unrelated households. They accept losing up to 24 hours of changes and taking
up to one day to restore service, provided the host disk survives.

## Solution

Provide a repeatable private deployment of the existing household application
on the Windows/WSL host. Household members connect Tailscale, open one HTTPS
address in their normal browser, and sign in with individual app accounts.
Everyone in this household has equal editing access.

Serve the built frontend and the real API under one origin. Run the application
without a development terminal, recover automatically from process failure and
Windows reboot, retain existing SQLite data across updates, and create daily
local backups with a demonstrated restore procedure. Supply the deployment
configuration, operational commands, and host verification instructions needed
to operate it.

Tailscale provides private connectivity; application authentication remains in
place. This deployment implements one household. A future public service must
isolate households before admitting them, but that work is deferred.

## User Stories

1. As a household member, I want to open the app while away from home, so that I can use household information wherever I have connectivity.
2. As a household member, I want to connect through Tailscale on my phone, so that I can privately reach the household server over cellular data.
3. As a household member, I want to use Safari or Chrome on my phone, so that I do not need a native recipe app.
4. As a household member, I want the same address to work on my computer, so that I can use the app across my devices.
5. As a household member, I want an HTTPS address that my browser accepts, so that I can sign in without certificate warnings.
6. As a household owner, I want access restricted to authorized household devices, so that internet visitors cannot reach the deployment.
7. As a household member, I want to sign in with my own app account, so that account credentials are not shared across the household.
8. As a household member, I want to read and edit the same household data as other members, so that we can coordinate shopping and cooking.
9. As a household member, I want my existing login session to survive a browser reload, so that remote access remains convenient.
10. As a household member, I want expired or invalid sessions to return me to login, so that I can recover access through the existing sign-in flow.
11. As a household member, I want logout to end my session, so that I can stop using an account on a device.
12. As a household owner, I want a controlled way to provision household accounts, so that only intended members can join.
13. As a household owner, I want registration closed after provisioning, so that an unnecessary account-creation window is not left open.
14. As a household member who forgets a password, I want the owner to restore my account access, so that I can continue using the app without an email recovery service.
15. As a household member, I want to open or reload a saved recipe or inventory link directly, so that navigation does not depend on first visiting the home page.
16. As a household member, I want recipes and stock changes to save through the deployed app, so that the remote view reflects real household data.
17. As a household member, I want cooking and grocery-list workflows to retain their existing behavior, so that deployment does not change how quantities or history work.
18. As a household member, I want ordinary API failures to remain understandable in the app, so that a serving error does not replace them with an unrelated web page.
19. As a household owner, I want the deployment to use production build artifacts, so that it does not depend on a frontend development server or backend reload process.
20. As a household owner, I want the app to operate after I close my terminal and IDE, so that household availability does not depend on my development session.
21. As a household owner, I want Windows reboot to bring back private access and the app automatically, so that a restart does not require me to be physically present.
22. As a household owner, I want a failed application process to restart automatically, so that a recoverable process failure causes only a temporary interruption.
23. As a household owner, I want the app to recover after WSL or Tailscale restarts, so that those components can be maintained independently.
24. As a household owner, I want host power settings appropriate for an always-on service, so that idle sleep does not unexpectedly disconnect household members.
25. As a household owner, I want existing household records carried into deployment, so that going live does not start with an empty database.
26. As a household owner, I want application data stored separately from replaceable build output, so that updates and rebuilds preserve it.
27. As a household owner, I want an explicit database location, so that starting from a different working directory cannot silently create another household database.
28. As a household owner, I want a repeatable update procedure, so that I can deploy improvements without losing stored recipes or history.
29. As a household owner, I want a backup before maintenance that could affect data, so that I have a recovery point if the maintenance fails.
30. As a household owner, I want daily timestamped backups on local disk, so that I can recover recent household records without adding external storage now.
31. As a household member, I want routine backups to work while the app is running, so that saving a recovery copy does not require a planned outage.
32. As a household owner, I want backup failures and the latest successful backup to be visible, so that a missing backup is not mistaken for protected data.
33. As a household owner, I want unsuccessful backup attempts to preserve earlier successful snapshots, so that a failure does not destroy my available recovery points.
34. As a household owner, I want to restore a snapshot into an isolated database for a rehearsal, so that I can verify recovery without replacing live household data.
35. As a household owner, I want documented recovery to lose no more than a day of changes under the agreed conditions, so that the amount of re-entry is manageable.
36. As a household owner, I want to complete recovery within one day, so that household use can resume after an application or recoverable data failure.
37. As a household owner, I want readable startup, application, and backup diagnostics, so that I can distinguish connectivity, process, and data problems.
38. As a household owner, I want setup instructions for household phones and computers, so that members can connect and sign in without development knowledge.
39. As a household owner, I want deployment checks exercised against disposable data, so that verification cannot erase or mutate my household's real records.
40. As a household owner, I want later hosting and multiple-household work clearly separated from this delivery, so that I can start using the app without building a public service first.

## Implementation Decisions

1. **Deployment boundary.** Deliver one household on the existing Windows/WSL
   machine. Preserve the existing shared-household permissions and domain
   behavior. Do not add household identifiers, membership tables, roles, or
   cross-household features in this work.
2. **Production application composition.** Use the existing application factory
   as the composition boundary for the API and optional built-frontend serving.
   Production startup receives an explicit build location and fails clearly if
   required artifacts are missing. API-only factory use remains available to
   existing backend tests and development. Keep this change at the serving and
   configuration boundaries rather than refactoring domain services.
3. **One origin.** Serve frontend assets and route the existing API beneath the
   same origin. The frontend retains its centralized, root-relative API client.
   Support direct navigation and reload for client-side routes. Give API routes
   precedence over SPA fallback; unknown API routes and API errors keep their
   HTTP status and API response format. Missing static assets return a missing
   resource response rather than the SPA document. Serve only built public
   frontend assets, never the project checkout, configuration, or database.
4. **Production processes.** Run the built app without Vite's development server,
   backend reload, or an interactive development terminal. Preserve the existing
   application-factory test seam, configuration conventions, API contracts,
   transaction ownership, and one-way module imports.
5. **Private HTTPS ingress.** Run Tailscale on Windows and use private Serve to
   proxy a local application port reachable through Windows-to-WSL localhost
   forwarding. The documented topology is the starting point, subject to an
   actual-host connectivity check. Configure unattended Tailscale operation and
   persistent Serve configuration. Restrict access through Tailscale policies
   to intended household devices or identities. App listeners remain local;
   neither Funnel nor public router port forwarding is part of this deployment.
6. **Windows/WSL lifecycle.** Provide a repeatable startup and supervision
   arrangement that starts the intended WSL distribution and app after Windows
   boot, without a person signing in and opening a shell. Keep the WSL workload
   alive independently of terminal lifetime and restart failed application
   processes. Do not equate enabling a systemd service inside WSL with solving
   Windows startup or WSL lifetime. Inspect host versions and existing service
   configuration before selecting exact task/service settings. Avoid duplicate
   app instances when setup is repeated or startup is retried.
7. **Power and connectivity.** Configure and document keeping the host awake
   during expected availability. A sleeping, powered-off, or disconnected host
   cannot serve the application. Recovery after WSL, Tailscale, or Windows
   restart must be verified through the external application origin.
8. **Authentication and provisioning.** Retain existing app authentication,
   session expiry, logout, and password-change behavior. Provision individual
   household accounts through a controlled operator procedure and close backend
   registration afterward; the normal frontend build does not advertise signup.
   Test equal read/write access for two household accounts. Tailscale membership
   and application login are distinct access requirements.
9. **Operator account recovery.** Supply a local operator procedure for forgotten
   passwords using the application's password-hashing facilities, with session
   revocation for the recovered account. It must preserve household records and
   other users. This is an operational recovery action, not a new unauthenticated
   public reset API, email service, or administration UI. Avoid exposing account
   passwords or session tokens in logs and setup artifacts.
10. **Persistent data.** Keep SQLite on persistent WSL Linux storage outside the
    checkout and replaceable build output. Use an explicit database location in
    production configuration. Back up and carry existing data into deployment;
    setup must not silently overwrite an existing deployment database or invoke
    the development database-reset procedure. No schema change is required for
    this deployment.
11. **Updates.** Document repeatable build, deployment, stop/start, health check,
    and recovery to a previous compatible application build. Retain persistent
    data throughout. Take a backup before potentially data-affecting maintenance.
    Any later schema-changing upgrade requires a reviewed, data-preserving
    migration before it can be used with household data. General migration
    infrastructure is not a prerequisite for this schema-preserving delivery.
12. **Local backups.** Use SQLite's online backup facility for live snapshots;
    do not copy a database file while it is being written. Create timestamped
    snapshots at least daily in a dedicated local directory outside the
    application checkout. Keep the destination outside the served asset tree and
    limit local access to the operator. A failed attempt must report failure and
    preserve prior successful snapshots. Do not label a partially written backup
    as successful. Document schedule, storage location, retention, latest success,
    and failure diagnostics; these are local operations, without a hosted service.
13. **Recovery objectives.** The operating target is no more than 24 hours of
    lost changes and at most one day to restore service when usable local
    snapshots and the host disk remain available. Record a missed or failed
    backup so a snapshot older than the target is apparent. Local snapshots do
    not cover physical disk or machine loss; off-machine backups are explicitly
    deferred at the owner's request.
14. **Restore.** Provide a procedure to stop application writers, select and
    validate a snapshot, preserve the current database before replacement, restore
    the configured database, and restart the service. Rehearse first against a
    separate database and isolated app instance. Account for session data in a
    restored snapshot: invalidate restored sessions before normal service resumes
    so previously revoked sessions are not revived. Verify access through fresh
    login and verify representative restored records through the app/API.
15. **Operational delivery.** Provide configuration or setup commands and concise
    runbooks for first deployment, Tailscale client connection, account setup and
    recovery, restart, update, backup, restore, and diagnostics. Host-specific
    values such as the WSL distribution, executable locations, ports, and data
    directories are explicit setup inputs determined during installation. Record
    results of the host acceptance checks rather than assuming the host matches
    the development environment.

## Testing Decisions

- **Test observable behavior.** A useful test demonstrates that a household
  member can use the deployed application or that an operator can recover it.
  Assert visible outcomes, HTTP contracts, persistence, process recovery, and
  restored data. Do not test helper call order, duplicate domain-math unit tests,
  or mock the component whose deployment behavior is under test.
- **Primary seam: the deployed application origin.** Extend the existing
  Playwright real-backend integration approach to exercise the production build
  and serving configuration with a real FastAPI process and an isolated,
  file-backed SQLite database. Reuse existing authentication and recipe-flow
  helpers where appropriate. This covers the frontend, production serving,
  authentication, API integration, and persistence as one system. The current
  integration suite uses a development proxy, so passing it unchanged does not
  establish production-serving correctness.
- **Isolated setup and lifecycle.** Use dedicated ports, temporary data and
  backup directories, and explicit test configuration. Seed through supported
  APIs while registration is temporarily enabled, then run the production
  assertions with registration disabled. The test harness owns its test
  processes; never attach restart/restore tests to a developer or household
  server. Serialize lifecycle scenarios that replace their own test database.
- **Serving and authentication cases.** Cover initial load, built assets,
  direct navigation and reload of a nested route, successful login, rejected
  credentials, logout, and session hydration. Verify the normal build offers
  no registration flow and a direct registration request is refused. Verify
  unauthenticated data requests fail, two household accounts share expected
  read/write access, and unknown API routes and missing assets are not replaced
  by the SPA document. Check that private data/configuration cannot be fetched
  through static serving.
- **Persistence and recovery cases.** Create identifiable household records
  through the API/UI, restart the test application against the same database,
  and verify them again. Exercise the real backup operation against disposable
  data while the app is available. Make a distinguishable change after the
  snapshot, restore into a separate test database using the operator-facing
  operation, and verify snapshot data through a fresh app instance. Cover an
  unwritable backup destination, preservation of an earlier successful backup,
  and recovery refusal for a missing or invalid snapshot without replacing
  usable data. Verify recovered passwords and revoked sessions through login
  and authenticated API requests.
- **Existing lower seam only when needed.** For focused backend configuration,
  routing, or recovery edge cases that are awkward to drive through a browser,
  reuse the production application factory with its real test engine and
  TestClient. Existing auth, configuration, transaction, and recipe tests are
  prior art. Do not add dependency overrides or new mock-only storage/security
  interfaces merely to support deployment tests.
- **Actual-host acceptance.** Automated local tests cannot prove Windows boot,
  Tailscale policy, mobile connectivity, or the host's power behavior. On the
  target machine, verify a household phone on cellular can connect through
  Tailscale, log in, read a recipe, and save a change. Verify a device outside
  the permitted private network cannot reach the deployment, and that there is
  no direct public or LAN listener bypassing the intended ingress. Check access
  after closing terminals/IDE, an idle period, app-process termination, WSL
  restart, Tailscale restart, and full Windows reboot without interactive login.
  Confirm data persists and perform the separate-database restore rehearsal
  within the one-day target. Keep evidence of which checks were actually run.
- **Verification during implementation.** Run the existing backend tests,
  frontend lint/tests, and production build, plus the new deployment integration
  checks. Integrate deterministic production-serving and backup checks into CI
  without real Tailscale credentials or live external dependencies. Treat
  real-host acceptance as a separate completion gate; Linux CI success does
  not substitute for it.

## Out of Scope

- Public internet exposure, Tailscale Funnel, router port forwarding, cloud
  hosting selection or purchase, and a custom public domain.
- Multiple-household implementation, cross-household sharing, household
  memberships, overlapping membership, roles, public signup, or billing.
- Native iOS/Android applications, installable PWA support, and offline editing.
- Replacing SQLite with another database, adding migration infrastructure when
  no schema change is needed, or resetting household data as an upgrade step.
- Cookie-session redesign, token-storage redesign, and a general public-service
  authentication/abuse-control project. These remain part of readiness work
  before later internet-facing hosting.
- Off-machine/cloud backups, protection against host-disk loss, high
  availability, automatic failover, and paid monitoring/alerting services.
- Self-service email password reset, invitations, a new account-administration
  UI, and a password-change UI. Operator recovery is included as described above.
- Recipe, inventory, cooking, or grocery feature changes; uploads, URL import,
  OCR, and other deferred product capabilities.

## Further Notes

- This is the implementation spec requested after the deployment interview.
  It preserves the final scope: Windows/WSL, private Tailscale access, individual
  full-access household accounts, local daily backups, 24-hour acceptable data
  loss, and one-day restoration. The owner confirmed the testing approach:
  existing browser tests against the real backend and disposable SQLite data,
  plus actual-host Tailscale and Windows/WSL lifecycle checks. Spec publication
  is not evidence of deployment or of completed acceptance checks.
- The accepted household boundary is recorded in the
  [domain glossary](../../CONTEXT.md) and
  [independent-households ADR](../../docs/adr/0001-independent-households.md).
  The [deployment outline](../../docs/deployment.md) remains a concise overview;
  the [roadmap](../../docs/features.md#deployment-direction-2026-09-05) retains
  the later hosting exploration. This spec owns the scope of this delivery.
- The target Windows/WSL installation has not been inspected in this session.
  Exact setup inputs and any Windows/Tailscale actions requiring the owner's
  machine or account are installation details, not reasons to implement a
  different hosting model. Prepare repeatable artifacts and checks first, then
  complete and report the real-host commissioning steps when access is available.
- The network proposal combines Microsoft's documented
  [Windows-to-WSL localhost access](https://learn.microsoft.com/en-us/windows/wsl/networking)
  with [Tailscale Serve localhost proxying](https://tailscale.com/docs/reference/examples/serve).
  Tailscale documents [unattended Windows operation](https://tailscale.com/docs/how-to/run-unattended).
  Microsoft notes that [systemd services do not keep WSL alive](https://learn.microsoft.com/en-us/windows/wsl/systemd),
  which is why Windows/WSL lifetime has an explicit acceptance gate.
- Later browser-only hosting around $5/month is acceptable but unselected.
  Before exposing the app to the internet, revisit authentication hardening,
  abuse controls, off-machine backups, and recovery. Before admitting unrelated
  households to one service, implement the agreed household isolation boundary
  and prove it with isolation tests. Do not open current registration as a
  substitute for that work.

# 01c: Gate changes on the real-backend browser integration suite

**What to build:** Every pull request and push to `main` runs the existing Playwright integration suite against an owned FastAPI backend, Vite dev server, and disposable SQLite database.

**Blocked by:** None (the real-backend integration suite already exists).

**Status:** ready-for-agent

- [ ] Add `npm run test:integration` to GitHub CI with the existing locked backend and frontend dependency installs and a headless Chromium installation.

- [ ] Run the existing auth and recipe integration specs through `playwright.integration.config.ts`, preserving their dedicated ports, disposable database, owned processes, CI retries, and GitHub annotations.

- [ ] Keep `npm run test:e2e:production` as a separate required check of the built, single-origin deployment. Passing the development-proxy integration suite must not replace or weaken the production-serving smoke coverage.

- [ ] Make integration failures diagnosable from the workflow run by retaining the Playwright report and trace/test-result output when the suite fails. Confirm the documented local reproduction command remains accurate.

## Delivery constraints

- This slice wires existing scenarios into CI; add or change browser scenarios only when required to make the current suite deterministic in a clean GitHub Actions runner.

- Reuse the existing isolated real-backend harness. The workflow must not require credentials, external services, or a persistent database.

- Keep the backend test job, frontend lint/unit/build job, and production smoke green. Run the same integration command locally before considering the slice complete.

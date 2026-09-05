# 01c: Gate changes on the real-backend browser integration suite

**What to build:** Every pull request and push to `main` runs the existing Playwright integration suite against an owned FastAPI backend, Vite dev server, and disposable SQLite database.

**Blocked by:** None (the real-backend integration suite already exists).

**Status:** done

- [x] Add `npm run test:integration` to GitHub CI with the existing locked backend and frontend dependency installs and a headless Chromium installation.

- [x] Run the existing auth and recipe integration specs through `playwright.integration.config.ts`, preserving their dedicated ports, disposable database, owned processes, CI retries, and GitHub annotations.

- [x] Keep `npm run test:e2e:production` as a separate required check of the built, single-origin deployment. Passing the development-proxy integration suite must not replace or weaken the production-serving smoke coverage.

- [x] Make integration failures diagnosable from the workflow run by retaining the Playwright report and trace/test-result output when the suite fails. Confirm the documented local reproduction command remains accurate.

## Delivery constraints

- This slice wires existing scenarios into CI; add or change browser scenarios only when required to make the current suite deterministic in a clean GitHub Actions runner.

- Reuse the existing isolated real-backend harness. The workflow must not require credentials, external services, or a persistent database.

- Keep the backend test job, frontend lint/unit/build job, and production smoke green. Run the same integration command locally before considering the slice complete.

## Comments

- Branch `ci/private-household-deployment-01c`, worktree
  `.claude/worktrees/private-household-deployment-01c`. Merged to `main` via
  PR #85 (squash `06c1647`); all four CI jobs green, new `integration` job 57s.
- Added an `integration` job to `.github/workflows/ci.yml`: `uv sync --frozen`
  + `npm ci` + `npx playwright install --with-deps chromium` + `npm run
  test:integration`. The existing `playwright.integration.config.ts` is
  unchanged, so dedicated ports (`:8971`/`:5273`), the disposable
  `e2e-integration.db`, harness-owned processes, `retries: 1` under CI, and the
  `github` reporter annotations all carry over as-is.
- On failure the job uploads `frontend/playwright-report/` +
  `frontend/test-results/` as `playwright-integration-report`
  (`retention-days: 7`).
- `production-smoke` job left untouched — still a separate required check.
- Verified locally: `cd frontend && npm run test:integration` → 11 passed.
  README `## CI` section updated to list all four jobs and the local repro
  command.

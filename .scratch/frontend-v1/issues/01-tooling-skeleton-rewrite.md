# 01: Tooling & skeleton rewrite

**What to build:** Replace the dead pre-v1 React skeleton with the module layout the frontend spec describes, add the v1 dependency set, and keep CI green in the same change. After this ticket a developer can run the dev server, lint, tests, and a production build against the new structure, and the test suite can drive any screen through mocked HTTP.

**Blocked by:** None (can start immediately).

**Status:** done

- [ ] Runtime deps added: `react-router-dom`, `@tanstack/react-query`. Dev deps: `msw`, `eslint` (+ `@typescript-eslint`, `eslint-plugin-react-hooks`), `prettier`. No dependency outside the spec §1 list.
- [ ] Pre-v1 `App` / `types` / `api` / `api.test` removed; `main` rewritten to mount the provider stack (QueryClient + Auth + Router). `setupTests`, vite config, `tsconfig` solution layout kept; `index.html` retitled "Recipes".
- [ ] HTTP client: prefixes `/api`, injects `Authorization: Bearer` from `localStorage`, normalizes both FastAPI error shapes into a typed `ApiError { status, detail }`, handles 204, throws `ApiError` on non-2xx.
- [ ] Types module transcribed by hand from `docs/spec.md` §5 (not generated) and diffed against the backend section.
- [ ] MSW: a server + a happy-path handler for every `docs/spec.md` §5 route, plus one error handler per `docs/frontend/spec.md` §6 catalog row; wired into `setupTests` so no test hits the network.
- [ ] `npm run lint` added; the `frontend` CI job is `npm ci && npm run lint && npm run test:run && npm run build` and is green.
- [ ] HTTP client test passes against MSW; no dead skeleton files remain.

**Refs:** `docs/frontend/spec.md` §1, §2; `docs/frontend/plan.md` Phase 0.

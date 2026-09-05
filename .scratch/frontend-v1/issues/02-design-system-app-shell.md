# 02: Design system & app shell

**What to build:** The visual foundation and navigation frame for every screen — a theming token layer, the ~8 hand-rolled UI primitives, and the responsive app shell with the full route table. After this ticket a developer can navigate the whole route skeleton (placeholder pages), switch light/dark, and see every primitive on a demo route meeting the accessibility bar.

**Blocked by:** 01.

**Status:** done

- [ ] `tokens.css`: color roles, 4px spacing scale, type scale, radii; `:root` light + `[data-theme="dark"]`; default follows `prefers-color-scheme` with a `localStorage` override; global reset.
- [ ] Primitives built and unit-tested in isolation for behavior + accessibility wiring: `Button`, `Input`/`Textarea`/`Select`, `Field` (label + control + hint + error), `Card`, `DataTable` (real `<table>` ≥ 640px, stacked rows below), `Dialog` (focus trap, `Esc`, focus restore), `Toast` + provider (`aria-live="polite"`), `Badge`, `Stepper` (presets + free input, enforces `> 0`).
- [ ] App shell: top bar ≥ 640px, bottom tab bar < 640px, four destinations (Recipes, Inventory, Groceries, History), `aria-current` on the active section, user menu with theme toggle + logout.
- [ ] Full route table wired with placeholder pages: `/login`, `/`, `/recipes/new`, `/recipes/:id`, `/recipes/:id/edit`, `/inventory`, `/groceries`, `/groceries/:id`, `/history`, `*` in-app NotFound. Every non-login route guarded by `RequireAuth` → `/login?next=<path>`.
- [ ] Dev-only component demo route renders every primitive in both themes.
- [ ] Accessibility bar (spec §9) met on the demo route: keyboard operable, visible focus, contrast ≥ 4.5:1 both themes, live regions, no color-only status.

**Refs:** `docs/frontend/spec.md` §3, §8, §9; plan Phase 1.

# 13a: Grocery list — render + optimistic check (vs MSW)

**What to build:** Working a single grocery list in a store: reading it and checking lines off with instant feedback. After this ticket a user can open `/groceries/:id`, see each line with its item and a human-formatted quantity grouped into generated and manually-added lines, see "amount uncertain" lines honestly, and tap a line to check it off with an optimistic flip that reverts on a server rejection.

**Blocked by:** 12a.

**Status:** ready-for-agent

- [ ] `/groceries/:id` shows each line with its item and a human-formatted quantity (`formatQuantity`), grouped into generated and manually-added lines.
- [ ] Tapping a line checks it off optimistically (instant), and reverts if the server rejects the change.
- [ ] A line whose true shortfall is uncertain (`nettable: false`) is marked "amount uncertain" with a note to buy based on what is found — never a computed number.
- [ ] The grocery calls sit behind the grocery resource adapter (R-2); built against the spec DTO, **not** wired to real calls here (that is ticket 18).
- [ ] Flow test (vs MSW): lines render grouped with formatted quantities; a `nettable: false` line shows "amount uncertain" and no number; tapping a line flips it immediately, and a `409` response rolls it back.

**Refs:** `docs/frontend/spec.md` §10.7, §7.2, §7.4; plan Phase 6. Split from ticket 13.

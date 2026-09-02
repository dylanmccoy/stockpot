# 13: Grocery — shopping a list (vs MSW)

**What to build:** Working a single grocery list in a store and submitting it back into inventory. After this ticket a user can check lines off with instant feedback, add and edit lines, see "amount uncertain" lines honestly, submit checked lines into stock in a deliberate step that can be repeated, and archive the finished list.

**Blocked by:** 12, 08.

**Status:** ready-for-agent

- [ ] `/groceries/:id` shows each line with its item and a human-formatted quantity, grouped into generated and manually-added lines.
- [ ] Tapping a line checks it off optimistically (instant), and reverts if the server rejects the change.
- [ ] A line whose true shortfall is uncertain (`nettable: false`) is marked "amount uncertain" with a note to buy based on what is found — never a computed number.
- [ ] Add a manual line with an item and optional quantity/unit.
- [ ] Edit a generated line's item, quantity, or unit, sending quantity and unit together; a quiet note explains when this reclassifies the line to manual (no longer netted against stock).
- [ ] Submit checked lines into inventory via a `Dialog` that explains this adds stock and cannot be undone. Shopping can continue and submit again later for newly-checked lines.
- [ ] Already-submitted lines are read-only, show the amount that was added (`applied_*`), and are un-editable / un-deletable without a confusing error.
- [ ] Archive a finished list. Acting on a list archived by someone else shows a clear message to refetch and move on (`409`).
- [ ] Flow test (vs MSW): check two lines → submit → lines frozen and inventory invalidated; PATCH a frozen line → conflict copy; edit a generated line → reclassified to manual.

**Refs:** `docs/frontend/spec.md` §10.7, §7.4; plan Phase 6.

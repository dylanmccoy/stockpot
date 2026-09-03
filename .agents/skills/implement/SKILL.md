---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

## Set up an isolated worktree

Do all of this ticket's work in a dedicated git worktree, not in the primary
checkout. This keeps the ticket's branch pinned to its own working directory, so
switching branches in another terminal can't disturb it.

Before writing any code:

1. Derive `<feature-slug>` and `<ticket-id>` from the ticket, and pick a
   `<type>` (`feat/`, `fix/`, `chore/`, …).
2. From the repo root, create the worktree with a fresh branch off `main`:
   ```
   git worktree add .claude/worktrees/<feature-slug>-<ticket-id> -b <type>/<feature-slug>-<ticket-id> main
   ```
   `.claude/worktrees/` is git-ignored, so the worktree itself is never staged.
   One worktree + one branch per ticket — do not reuse either from a previous
   ticket.
3. `cd` into `.claude/worktrees/<feature-slug>-<ticket-id>` and run every
   subsequent command (tests, typecheck, git, reviews, commit) from there. Per
   `CLAUDE.md`, backend commands run from its `backend/`, frontend from its
   `frontend/`.

The new branch starts from `main`, so uncommitted changes in the primary
checkout are **not** carried in. If this ticket depends on local work that
isn't yet on `main`, stop and ask before creating the worktree.

If a worktree or branch with that name already exists, stop and ask.

## Build it

### Read the spec by section, never whole

The ticket's **Spec:** field names the exact anchors to read (e.g. `docs/spec.md`
§5.5, §2.2). `docs/spec.md` is ~1700 lines and `docs/frontend/spec.md` ~930 — a
whole-file `Read` of either burns ~15–20k tokens before you have written
anything.

For each spec file a ticket cites:

1. `grep -nE '^#{1,6} ' <spec-file>` to get its heading→line-number table of
   contents.
2. From that, find the start line of each cited section and the start of the
   next heading at the same-or-higher level (its end).
3. `Read` with `offset`/`limit` bounded to that range. Only widen if a section
   forward-references another you genuinely need.

Do not read `docs/features.md`, `docs/decisions.md`, `docs/plan.md`, the
`docs/phases/` files, or the other app's spec unless the ticket's **Spec:** /
**Files:** / **Tests:** header points at them.

### Slices

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the work with `/code-review` — the repo's two-axis
(Standards + Spec) review of the diff. Action the findings that hold up, and note
any you are deliberately skipping and why.

Re-run typechecking and the full test suite after actioning any review findings.

The second, independent `/codex:review` pass is **not** run here. It is done by
hand in a fresh window after `/implement` ends (see "Close out"), so its findings
are actioned against a clean context budget instead of eating into this session's
— by review time the build context has already cashed out into the diff, the
tests, and the ticket.

## Close out

Commit your work to this ticket's branch. Do not merge it or open a PR unless
the user asks.

### Update the ticket

The tracker is not touched by any of the steps above, and this skill's branch is
never merged on its own, so update the ticket **in the primary checkout**, not in
the worktree — a status change committed only to the ticket branch stays
invisible until that branch lands. Consult `docs/agents/issue-tracker.md` for how
this repo's tracker is shaped.

- **Local-file tracker** — edit `.scratch/<feature-slug>/issues/<ticket-id>-*.md`
  in the primary checkout:
  - set the `Status:` line to `in-review` (the work is done and the branch is
    awaiting review/merge; use `done` only once it has merged);
  - tick every `- [ ]` acceptance criterion the work satisfies, leaving any
    genuinely unmet ones unchecked with a one-line note;
  - append a note under a `## Comments` heading recording the branch name and
    worktree path.
- **Real issue tracker** — make the equivalent changes on the issue itself
  (status/label, acceptance checklist, a comment linking the branch).

Do not make these edits inside the worktree as well; a single source of truth
avoids a merge conflict when the branch lands. Leave the primary-checkout edit
uncommitted and point the user at it so they can commit it when ready.

### Hand back

Leave the worktree in place and tell the user where it is, along with the ticket
file you updated. Remind them to run the independent review by hand before
merging:

1. Open a fresh session (`/clear`, or a new terminal) and `cd` into
   `.claude/worktrees/<feature-slug>-<ticket-id>`.
2. Run `/codex:review` against this branch.
3. Action the findings that hold up (note any deliberate skips and why), re-run
   typechecking and the full test suite, and `git commit --amend` or add a fixup
   commit on this branch.

Once the branch is merged the worktree can be cleaned up with:
```
git worktree remove .claude/worktrees/<feature-slug>-<ticket-id>
```

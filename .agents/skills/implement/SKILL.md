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

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the work in two passes:

1. `/code-review` — the repo's two-axis (Standards + Spec) review of the diff.
2. `/codex:review --wait` — an independent review from a different model. It is
   review-only and will not change the code, so once it returns, work through
   its findings yourself: action the ones that hold up, and note any you are
   deliberately skipping and why.

Re-run typechecking and the full test suite after actioning any review findings.

## Close out

Commit your work to this ticket's branch. Do not merge it or open a PR unless
the user asks.

Leave the worktree in place and tell the user where it is. Once the branch is
merged it can be cleaned up with:
```
git worktree remove .claude/worktrees/<feature-slug>-<ticket-id>
```

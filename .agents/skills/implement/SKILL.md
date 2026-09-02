---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

Implement the work described by the user in the spec or tickets.

Before writing any code, create a branch for this ticket off the main branch:
`git switch -c <type>/<feature-slug>-<ticket-id>` (e.g.
`feat/grocery-list-sharing-3`), deriving `<feature-slug>` and `<ticket-id>` from
the ticket. Use `feat/`, `fix/`, `chore/`, etc. for `<type>`. One branch per
ticket — do not reuse a branch from a previous ticket. If the working tree has
uncommitted changes, stop and ask before branching.

Use /tdd where possible, at pre-agreed seams.

Run typechecking regularly, single test files regularly, and the full test suite once at the end.

Once done, review the work in two passes:

1. `/code-review` — the repo's two-axis (Standards + Spec) review of the diff.
2. `/codex:review --wait` — an independent review from a different model. It is
   review-only and will not change the code, so once it returns, work through
   its findings yourself: action the ones that hold up, and note any you are
   deliberately skipping and why.

Re-run typechecking and the full test suite after actioning any review findings.

Commit your work to this ticket's branch. Do not merge it or open a PR unless
the user asks.

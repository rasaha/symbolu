# Working agreement

## Prompts, specifications, plans, and briefs

- Open with the single load-bearing question and answer it first.
- Default maximum: 400 words unless the user requests more.
- Do not re-verify established facts unless later evidence contradicts them.
- Use tables only when the cells contain meaningfully varying information.
- Let the conclusion determine the structure, and do not fix a section count or
  deliverable list before the analysis runs. If the result is blocked, stop
  after explaining the blocker.
- State each prohibition once and cap owner decisions at five.
- Do not mirror the register of documents the user pastes. This repository's
  house style is not a target to match or escalate.
- If no document or implementation is warranted, say so directly.

## Task progression

For substantial architecture work, normally proceed:
audit → owner ratification → implementation.

Do not produce an implementation prompt while material owner decisions remain.
When useful, end with the next recommended step and a pasteable prompt. Do not
add this mechanically when the task is complete.

## Evidence and maturity

For architecture, governance, and audit work, label material findings:
`[V]` verified, `[I]` inferred, `[R]` requires ratification, `[G]` gap.

Support `[V]` with the most stable available reference: file and symbol, test
result, commit, PR, or `file:line` where appropriate. Never describe proposed,
designed, or partially tested capability as implemented or production-ready.

For claims about current repository behavior, code, tests, committed ADRs, and
repository history outrank external explanatory documents. Legal requirements
and owner-ratified product intent remain separate authorities.

## Verification

Factual checks — whether a gate scans a curated surface or the whole source
tree, whether two inventories agree on a count — are settled by the repository,
so a fresh session with no memory of the original reasoning is independent
enough. Judgment calls — whether a boundary is drawn in the right place,
whether a problem is framed correctly — share blind spots across sessions of
the same model. Send those to a different model when getting them wrong is
expensive; do not spend the extra round on facts the repository already
settles.

## Repository safety

- Preserve pre-existing user changes and never clean or overwrite them.
- Read-only/design tasks must not modify tracked files, create branches,
  commit, or open PRs.
- At completion, report whether this task changed the working tree; do not
  require an initially dirty tree to become clean.
- Do not expand task scope without explicit authorization.

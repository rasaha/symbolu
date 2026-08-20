# Working agreement

## Every response that executes a task

End with a "Next window" block: the next step, why it's next, and an exact
pasteable prompt. Default sequence for design and architecture work is
**audit → owner ratification → implementation**. Never jump from an analysis
straight to an implementation prompt.

## Any prompt, spec, plan or brief you write

- Open with the single load-bearing question. Answer it first.
- 400 words unless I name a higher number. Length is not rigor.
- Never ask to re-verify established facts — merged PRs, green CI, git
  ancestry, existing versions. Assume the record is true unless I flag doubt.
- No table unless the cells vary. If one column would read the same for most
  rows, write the sentence it collapses to instead.
- Do not pre-commit to a section count or deliverable list. If the crux
  resolves "blocked", stop there — do not design what you just said cannot
  safely be built.
- Cap owner decisions at 5.
- If the honest answer is "this needs no document", say that.

## Architecture and governance work in this repo

- Label material claims `[V]` verified / `[I]` inferred / `[R]` needs
  ratification / `[G]` gap. Cite `file:line` for every `[V]`.
- Committed ADRs and code outrank any external prose, brief or artifact.
- Do not mirror the register of documents I paste. This repo's house style is
  not a target to match or escalate.
- Design sessions are read-only: no tracked file changes, no branch, no commit,
  no PR. Confirm a clean tree at the end.

## Verification

Factual checks (does this gate scan `__all__` or the source tree, is it 82
symbols or 81) are settled by the repository, so a fresh session is
independent enough. Judgment calls — is this the right boundary, is the trust
problem framed correctly — share blind spots across sessions of the same
model; send those to a different model when getting them wrong is expensive.

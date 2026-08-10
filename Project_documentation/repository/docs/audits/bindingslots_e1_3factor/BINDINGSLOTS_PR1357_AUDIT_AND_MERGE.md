# PR #1357 (three-factor preregistration) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `595e61c2` onto the authoritative default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (now the default tip; local default synchronized).

## Verified (Git + GitHub + committed artifacts + CI) — all checks
- **Documentation-only:** exactly 2 added files under `docs/audits/bindingslots_e1_3factor/`
  (`BINDINGSLOTS_PR1356_AUDIT_AND_MERGE.md`, `E1_TEMPORAL_3FACTOR_PREREGISTRATION.md`), +143/-0. No code,
  tests, workflows, or reserved execution.
- **Accurately records the #1356 audit + merge:** the audit record cites merge commit `71d52947` with the
  14/14 verification; PR #1357's base SHA **is** `71d5294745883d2fb4c47c7016271165918a8eeb`.
- **Faithfully preserves `T4_SHORTFALL_MIXED`:** §1 grounds the design in it — over-abstention ~46%,
  entity-retrieval degradation ~22%, within-entity latest ranking ~32%, value/read path clean (D4 = 100%),
  strong F1×F2 interaction (D2 1.4% vs D3 68%).
- **Three factors, no oracle at inference:** §3 + §8 require explicit no-oracle-at-inference proofs — F1 may
  not read match/answer; F2 may not read evaluator entity identity; F3 may not read the ground-truth latest
  index or metadata.
- **C1 capacity fixed:** §3 capacity discipline (minimal added parameters, frozen C1 budget); any factor
  needing a capacity/budget increase is declared and treated as a confounded arm.
- **Shared fresh cohort:** §4 — one shared fresh reserved cohort, identical episodes across all 8 cells so
  main effects and interactions are estimable.
- **T5 outside:** header, §6, §9 — reported for completeness only, excluded from every gate and the verdict.
- **Preserves invariants:** `E1_TEMPORAL_TRANSFER_PARTIAL`, `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
  `KDA_VALIDATION_BLOCKED`; emits no `…_VALIDATED`/`…_CONFIRMED`; a recovery emits at most
  `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`; KDA stays blocked.
- **No implementation / training / reserved execution;** prior evidence and frozen `abc.json`
  `b31989a3…` unchanged (only 2 new doc files added). **CI 7/7 green; 0 unresolved review threads.**

Documentation + design only, faithful to the merged evidence, CI green, no threads — nothing required
correction. Merged.

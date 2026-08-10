# PR #1358 (E1 temporal three-factor factorial) — audit and merge record

**Decision: `MERGE_READY`.** Merged via merge-commit `22942108` onto the authoritative default branch
`claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` (now the default tip; local default synchronized).

Only documentation/CI/verifier/manifest corrections were permitted; none were required. No evidence, seed,
factor, gate, metric, result, or verdict was altered.

## Verified — Git + GitHub + committed evidence + independent replay + hashes + tests + CI
- **Complete preregistered 2³ factorial present:** all eight cells `000/100/010/001/110/101/011/111`, the
  factor model + harness, protocol lock, dev + final evidence, analysis, report, and torch-free CI.
- **Identical setup across cells:** one shared reserved cohort per seed and an identical per-seed batch
  stream; cells differ *only* by which minimal factor side-head is enabled (verified in
  `factor_train.train_cell` / `run_lib.run_seed`).
- **Factors minimal, learned, non-oracle at inference:** AST + signature proof that `E1F.scores/forward`
  receive only `(key_tokens, query_tokens, tau)` and no factor forward references any ground-truth /
  evaluator / metadata identifier; added params **F1 569 / F2 1041 / F3 131**.
- **Protocol preceded final execution:** the protocol-lock commit precedes the final-evidence commit; the
  final runner fails closed unless the seven frozen source hashes match the lock.
- **Seeds 7140–7144 fresh and disjoint** from every prior program seed (mechanically checked).
- **Cell 000 reproduces the frozen baseline:** its committed param hash equals both the recorded value and
  an independently trained plain `models.E1` on the same episodes/seed — **byte-identical** (base capacity
  provably untouched; base params 22 528 unchanged).
- **Independent byte-identical replay:** retraining cell `100`, seed `7140` reproduces the committed param
  hash exactly.
- **Verdict reconstructs mechanically as `T4_FACTORIAL_NO_INTERVENTION_SELECTED`** (selected cell: none)
  from the committed `final_per_seed.json`: no cell reaches T4 ≥ 0.85 (max mean 0.623), none improves cell
  000 by ≥ 0.05 (best +0.035), 0/5 seeds clear all primary gates in every cell.
- **Factor effects as claimed:** F1 main effect **+0.034** (reduces abstention −0.059, then re-exposes
  addressing errors); F2 −0.009; F3 −0.000; all interactions ~0, including the pre-flagged **F1×F2 = +0.001**.
- **No capacity confound** beyond the explicitly reported factor parameters (cell 000 == plain E1 proves the
  base is untouched).
- **Determinism, oracle-equivariance, leakage + shortcut** all pass; the global-latest and lexical
  baselines remain near chance.
- **T5 diagnostic-only** (~0.35 across all cells), excluded from gates, selection, and verdict.
- **Preserves** `E1_TEMPORAL_TRANSFER_PARTIAL`, `ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED`,
  `KDA_VALIDATION_BLOCKED`; emits no `E1_TEMPORAL_TRANSFER_VALIDATED` / `E1_STRUCTURAL_TRANSFER_CONFIRMED` /
  `E1_FOLLOW_ON_RESEARCH_ELIGIBLE`; claims bounded.
- **Scope clean:** additions only, entirely under `experiments/bindingslots_e1_3factor/`,
  `docs/audits/bindingslots_e1_3factor/`, and the new CI workflow; **no prior evidence changed**; frozen
  `experiments/phase_lc/results/abc.json` `b31989a3…` **unchanged**.
- **CI 9/9 green; 0 unresolved review threads.**

Evidence faithful, reproducible, and bounded — nothing required correction. Merged.

# TAP-E5 — Leakage & Integrity Audit

## 1. Primary experimental limitation (state plainly)

The eval split is **content-hash locked and preregistered, but was inspected during
iterative engineering**. It is a **locked development evaluation, not an untouched or
interpreter-blind holdout.** Further, the upstream records are **authored fixtures**: this
phase evaluates the assembly/minimization mechanism, not upstream extraction. The verdict
`PASS_WITH_LIMITED_CLAIM` attests to **mechanism/construction validity on this study's
synthetic corpus**, not to blind generalization.

## 2. Leakage controls in place

- **Locked eval inputs.** `eval_inputs_hash = 04b87570…` over the public view of the 16 eval
  cases (`n_eval = 16`); recorded in `experiments/experiment_lock.json`.
- **Dev-only selection.** The baseline is chosen as the simplest (A..F) passing all gates on
  **DEV**; `select_config` never reads eval metrics.
- **Independent gold.** `Case.gold()` computes the minimal-complete set on a **separate code
  path** from the assembler, so a baseline-F bug would diverge from gold rather than be
  graded against its own output.
- **Frozen mechanism hash.** `frozen_components_hash = 7a91bcf9…` folds the assembler,
  dependency graph, packet validator, metrics, schema, gate list, and baseline definitions.
- **Preregistration.** `experiments/preregistration.json` fixes the baselines, the 14 gates,
  the 12 critical-failure classes, the selection rule, and the verdict rule before scoring.
- **Gold-free loader.** `loader.py` exposes only case shape counts + compiled inputs.

## 3. Determinism

Verified byte-identical result hash and `frozen_components_hash` across
`PYTHONHASHSEED ∈ {0,1,7,42,123}`. Every sort has a stable id tiebreak; deduplication
preserves first-seen order; no output depends on set/dict iteration order.

## 4. Upstream integrity (frozen layers untouched)

TAP-E1, TAP-E1.1, TAP-E2, TAP-E3, and TAP-E4 are consumed **through their frozen public
interfaces only** and are **byte-identical** — all four upstream `frozen_components_hash`
values and every stored experiment JSON are unchanged. The sole working-tree addition is the
new `tap_e5_evidence_assembly/` package and this `docs/.../tap_e5_evidence_assembly/`
directory. Full repository regression: **153 tests pass**.

## 5. Threats to validity (residual)

- **Synthetic corpus, authored upstream fixtures.** 32 cases; no real upstream extraction.
  Results do not transfer to production without a blind, real-upstream evaluation.
- **Construction coupling.** The same author defined each scenario's evidence, relationships,
  governance, conflicts, gaps, and the intended minimal packet. Independent gold reduces but
  does not eliminate this coupling.
- **Development-inspected eval.** As in §1, the locked set informed engineering.
- **No downstream feedback.** E5 defines "complete" by its own dependency model; whether the
  packet is *sufficient* for real claim validation is an E6 question this study cannot close.

## 6. Future validation (to lift the "limited" qualifier)

1. A **blind** packet holdout authored by a separate party, scored once.
2. Assemble over **real** noisy upstream records (actual E2/E3/E4 output) to measure loss and
   over-/under-inclusion under imperfect inputs.
3. End-to-end coupling with a real TAP-E6 to confirm packet *sufficiency* for claim
   validation (downstream-defined completeness, not only E5-internal completeness).
4. Adversarial expansion: cyclic-looking upstream references, very deep provenance chains,
   large fan-out shared evidence, and partial-overlap conflicts.

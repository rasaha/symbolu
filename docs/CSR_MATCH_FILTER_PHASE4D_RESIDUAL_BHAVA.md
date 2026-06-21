# C×R×S Phase 4D — Guna/Vritti-Controlled Residual Bhava Test — PRE-REGISTRATION

> **Status: DESIGN ONLY, locked before implementation.** A NEW pre-registered experiment — NOT a
> continuation or re-roll of the closed Stage-B2 object-mode taxonomy (`RESULTS_PHASE4_STAGEB2.md`).
> Analysis-only / CPU-only on existing `runs/csr_phase4_v3` activations. No Phase 1–3 change, no model/
> weight/hidden-state/logit change, no Bhava wiring into CSR. Honesty note: the hidden-only baseline is
> strong (≈0.76 / 0.83) and a residual is a linear function of the hidden state, so a clean negative
> (`HIDDEN_ONLY_SUFFICIENT` / `GUNA_VRITTI_SUFFICIENT`) is the most likely outcome and is fully accepted.

## 1. Hypothesis
Stage-B2 isolated Bhava too directly and collapsed. New conceptual decomposition:
`H ≈ Guna (expression quality) + Vritti (semantic drift) + Bhava (residual disposition) + stress-field
+ noise`. **Hypothesis:** after removing Guna-like and Vritti-like components from the hidden state, the
**residual** carries a stable Bhava-like signal that adds diagnostic value for the failure targets
beyond hidden-only, Guna-only, Vritti-only, Guna+Vritti, dimension-matched random, and a surface
prompt-token baseline.

## 2. Labels (from existing audit outputs; no new collection)
- **Targets:** primary `frame_violation`, `rejected_domain_leak`; secondary `audit_fail`; exploratory
  `secondary_promoted`.
- **Guna proxy (quality):** `guna_low_quality = answer_too_generic OR factuality_suspected`
  (`rewrite_recommended` is not stored in the activation metadata, so it is omitted; declared here).
- **Vritti proxy (drift), TARGET-SPECIFIC to avoid trivial leakage:**
  - evaluating `frame_violation` → Vritti = `secondary_promoted OR rejected_domain_leak`;
  - evaluating `rejected_domain_leak` → Vritti = `frame_violation OR secondary_promoted`;
  - evaluating `audit_fail` → Vritti = `frame_violation OR rejected_domain_leak OR secondary_promoted`;
  - evaluating `secondary_promoted` → Vritti = `frame_violation OR rejected_domain_leak`.
- **Bhava supervision:** NONE of the target labels, directly or indirectly. The residual Bhava read is
  **unsupervised** (top principal components of the residualized hidden state) — distinct from the
  Stage-B2 supervised object-mode taxonomy.
- **Structural caveat (declared up front):** `frame_violation` is the audit OR of finding-types that
  include `rejected_domain_promoted` and `secondary_promoted_to_primary`. So Vritti is partly nested in
  the target by construction; the §3 leakage gate may fire structurally — that is an honest outcome,
  not to be worked around.

## 3. Feature construction (all within-arm, group-by-term CV, label-free rich PCA)
On the per-layer label-free rich PCA (`rich_dim`) of `runs/csr_phase4_v3` h0:
`hidden_only` (top `hidden_dim` PCs) · `guna_only` (proj on the train Guna direction) · `vritti_only`
(proj on the train Vritti direction) · `guna_plus_vritti` · `residual_only` (top-r PCs of the residual)
· `hidden_plus_residual_bhava` · `random_match` (hidden ⊕ random, width = r) · `prompt_token_ngram`
(hashed query tokens, surface baseline). Forbidden features: C/R/S scores, phonemic 12D, CSR trace
vectors, answer text, generated-token hidden states, and any target label as Bhava supervision.

## 4. Residualization procedure (train-fold-only; no test leakage)
Per CV fold: standardize `X_rich` on train; fit `guna_dir = logreg(X→Guna)`, `vritti_dir =
logreg(X→Vritti)` on train; build an **orthonormal basis** `B` of `span(guna_dir, vritti_dir)`
(Gram–Schmidt); residual `X_res = X − (X·Bᵀ)·B`; fit `residual_bhava` = top-r PCA of `X_res[train]`,
applied to train+test. Every transform (standardizer, directions, basis, residual PCA) is fit on train
and applied to test.

## 5. Controls
hidden-only baseline · Guna-only · Vritti-only · Guna+Vritti · dimension-matched random · prompt-token
n-gram surface baseline · within-arm reporting (arm encoded ≈1.00) · within-row-type/stress-field
reporting (row_type encoded ≈1.00) · group-by-term CV · multi-seed × n_pca robustness.

## 6. Leakage gate (run BEFORE any Bhava claim)
Report AUROC of `Guna→target`, `Vritti→target`, `Guna+Vritti→target` (within-arm). If any **> 0.70**,
mark **`PHASE4D_LEAKAGE_SUSPECTED`** for that target and do NOT proceed to a residual-Bhava-positive
claim for it.

## 7. Strict success gate (residual Bhava ADDS_SIGNAL requires ALL)
1. `hidden_plus_residual_bhava` − `hidden_only` ≥ **+0.05** AUROC, **bootstrap delta CI above 0**;
2. beats the **dimension-matched random** control (≥0.05, CI excludes 0);
3. beats / not explained by the **prompt-token n-gram** baseline (≥0.05, CI excludes 0);
4. residual Bhava does **not collapse** (effective rank ≥ **3**);
5. **stable** across ≥80% of seed × n_pca configs;
6. holds **within-arm** (not pooled-only);
7. is **not** explained by row_type/stress-field detection;
8. uses **no** target label as Bhava supervision (guaranteed: residual Bhava is unsupervised).

## 8. Decision labels
`PHASE4D_RESIDUAL_BHAVA_ADDS_SIGNAL` · `PHASE4D_RESIDUAL_BHAVA_NO_INCREMENTAL_SIGNAL` ·
`PHASE4D_HIDDEN_ONLY_SUFFICIENT` · `PHASE4D_GUNA_VRITTI_SUFFICIENT` · `PHASE4D_LEAKAGE_SUSPECTED` ·
`PHASE4D_RESIDUAL_BHAVA_COLLAPSE` · `PHASE4D_INSUFFICIENT_LABEL_POWER`.
`GUNA_VRITTI_SUFFICIENT` = Guna+Vritti ≈ hidden_only AND residual adds nothing.

## 9. Kill criterion
If residual Bhava does not pass the strict gate, record `PHASE4D_RESIDUAL_BHAVA_NO_INCREMENTAL_SIGNAL`
/ `PHASE4D_HIDDEN_ONLY_SUFFICIENT` / `PHASE4D_GUNA_VRITTI_SUFFICIENT` and **STOP**. No post-hoc search
for a better residualization or label set; any future attempt is a new pre-registration. No Phase 5.

## 10. Interpretation boundaries
**If it passes**, the only valid claim: *after controlling for Guna-like quality and Vritti-like drift,
a residual Bhava-style readout adds diagnostic signal beyond hidden-only on this model/dataset.* **Never
claim:** consciousness; Bhava proven; generation-active; runtime-wired; causal control; cross-model
generalization; or automatic Phase 5 justification. **If it fails:** *Guna/Vritti-controlled residual
Bhava did not add signal; hidden-only or Guna/Vritti mechanisms suffice for this dataset/model.*

# C×R×S Phase 4 — Stage-B2 (learned Bhava read) RESULT

> **Verdict: `PHASE4_BHAVA_COLLAPSE` / `PHASE4_HIDDEN_ONLY_SUFFICIENT` — the target-orthogonal learned
> Bhava read adds NO incremental value over the hidden-only baseline. Per the locked kill criterion
> (pre-registration §7–8), the hidden-state Bhava track STOPS here.** Bhava is interpretive, not a
> demonstrated mechanistic diagnostic, and stays out of CSR runtime. C×R×S remains the validated
> Phase 1–3 wrapper/audit product.

Run: `runs/csr_phase4_v3` (n=1032), framed arm, primary 7-class object-mode taxonomy, rich PCA-256,
seeds 0–2 × hidden_dim {32,64}, group-by-term CV, within-arm.

## Result by primary target

| target | orthogonality (mode→target) | bhava eff. rank | hidden_only | hidden+bhava | bhava_only | Δ vs hidden | Δ vs random | Δ vs n-gram | decision |
|---|---|---|---|---|---|---|---|---|---|
| frame_violation | **0.45** (✓ orthogonal) | **2.58** (< 3) | 0.76–0.80 | 0.76–0.80 | 0.43–0.46 | −0.011…+0.008 | −0.018…+0.013 | +0.12…+0.17 | `BHAVA_COLLAPSE` |
| rejected_domain_leak | **0.54** (✓ orthogonal) | **2.58** (< 3) | 0.78–0.83 | 0.78–0.82 | 0.47–0.49 | −0.015…0.0 | −0.012…+0.001 | +0.09…+0.15 | `BHAVA_COLLAPSE` |
| audit_fail (secondary) | 0.48 | 2.58 | 0.74–0.80 | 0.74–0.78 | 0.41–0.46 | ≈0/neg | ≈0/neg | +0.11…+0.15 | `BHAVA_COLLAPSE` |
| secondary_promoted (expl.) | 0.42 | 2.61 | 0.80–0.88 | 0.83–0.87 | 0.64–0.66 | +0.02 (hd32) / −0.01 (hd64) | ≈0 | +0.16…+0.21 | `BHAVA_COLLAPSE` |

## Reading
1. **Orthogonality control PASSED.** Object-mode predicts the failure targets at 0.45 / 0.54 (≤0.60) —
   the supervision is genuinely target-orthogonal; no label leakage. (Ablation `domain_family` was
   *not* orthogonal: 0.61 / 0.85 — it would have leaked, confirming it was right not to use it.)
2. **Bhava read COLLAPSED** (effective rank 2.58 < 3) because the pre-declared object-mode taxonomy is
   dominated by `person_role` (most objects are occupations). Per the pre-registration this is a
   declared negative outcome; we do **not** re-roll the taxonomy (that would be a new pre-registration).
3. **No incremental value, independent of collapse.** `hidden_plus_bhava` − `hidden_only` is ≈0 or
   negative across all 6 configs and never beats the dimension-matched random control; `bhava_only` is
   at/below chance (0.43–0.49). The strict gate fails everywhere (`gate_pass_frac = 0`).
4. **Side-finding (supports the Stage-B1 result, not Bhava):** the hidden signal beats the surface
   n-gram baseline by +0.09…+0.21 AUROC — the hidden-only failure signal is **more than lexical**.
5. `secondary_promoted` flickered positive at hd=32 (Δ +0.02–0.035) but reversed at hd=64 — noise,
   exploratory only, and it also collapsed.

## Decision (per locked kill criterion §7–8)
The hidden-state **Bhava track is closed**. The pre-registration forbids a post-hoc search for a
"better Bhava definition"; any future attempt is a new pre-registration, not a continuation of this
one. **Bhava is NOT wired into CSR** and no model weights / hidden states / logits are modified.

## What stands (the real, banked findings)
- **H1 (hidden-only) is a genuine result:** the pre-answer hidden state linearly predicts
  `frame_violation` (framed ≈0.76) and `rejected_domain_leak` (framed ≈0.83) within-arm,
  within-row-type, above a surface-token baseline — strongest under adversarial stress.
- **Bhava (this operationalization) adds nothing over it.** The honest scientific statement: *on this
  dataset and model, a target-orthogonal Bhava-style readout does not add diagnostic signal beyond the
  raw hidden state.* No claim of consciousness, generation-activity, runtime wiring, or proof.

## Interpretation boundaries (unchanged)
Even where hidden-only is predictive: this is a correlational linear probe on one model/dataset. It is
not causal, not mechanistic, not runtime-active, and not a Bhava demonstration. C×R×S Phase 1–3 remains
the product; Bhava stays out of runtime.

# C×R×S Phase 4 — Stage-B1 (hidden-only) H1 result

> **Decision label: `PHASE4_H1_QUALIFIED_WITHIN_ARM_SIGNAL`.**
> Honest baseline only. NO learned Bhava directions, NO `hidden_plus_bhava`, NO incremental-value
> claim, NO generation control. This does **not** claim `PHASE4_BHAVA_ADDS_SIGNAL`. Phase 1–3 logic is
> unchanged. Raw activations and `runs/` artifacts are not committed.

## 1. Data source

- Stage-A activations: **X = (220, 33, 4096)** (`runs/csr_phase4/phase4_activations.npz`).
- **110 examples × 2 arms** (base, framed) on real Mistral-7B-Instruct-v0.3.
- Features = **final-prompt-token hidden states**, captured **before generation**.
- **No answer-token leakage**: `features_from_answer_tokens=false`,
  `feature_provenance=residual_stream_hidden_state`; labels come from the post-generation Phase 3
  audit of the saved Phase 2B answers.
- Manifest valid: `SHAPE OK`, `LEAKAGE OK`, `MANIFEST complete`, `skipped=0`, `missing labels=0`,
  `VALID_FOR_PHASE4_SIGNAL=true`.

## 2. Main caveat (read this first)

The hidden state **trivially encodes the arm**: `hidden→arm AUROC ≈ 1.00` for every target (the framed
prompt injects the domain labels, so base vs framed is perfectly separable). Because the arms also have
different audit base-rates, **any pooled probe is arm-confounded** and can "predict" an outcome merely
by detecting base-vs-framed. **Only WITHIN-ARM results (base-only, framed-only, where the arm is
constant) are clean evidence.** All numbers below are within-arm unless stated.

Method: per-layer linear logistic probes, **group-by-term CV**, global label-free PCA→32 (unsupervised,
no target leakage), best layer chosen inside CV folds (nested), bootstrap 95% AUROC CIs. Single seed
(seed=0) for this headline run — robustness sweep is the required next step (§6).

## 3. H1 per-target verdict (within-arm)

| target | role | within-arm result | verdict |
|---|---|---|---|
| **audit_fail** | primary | base 0.552 [0.44,0.67], framed 0.507 [0.37,0.62] — both CIs include 0.5; pooled (0.579) is *below* the arm-only baseline (0.64) | **null / not predictive** |
| **frame_violation** | primary | **framed 0.671 [0.55,0.77]** — CI excludes 0.5 (base 0.552 includes 0.5) | **qualified positive (framed arm)** |
| **rejected_domain_leak** | exploratory | **base 0.716 [0.60,0.82]** — CI excludes 0.5 (framed: too few positives) | **qualified positive (base arm), exploratory** |
| **secondary_promoted** | exploratory | base 0.553 [0.44,0.66] (chance); framed insufficient; pooled 0.673 is arm-confounded | **inconclusive — do NOT promote on pooled** |
| **factuality_suspected** | — | 6 positives | **underpowered (excluded)** |
| **meta_parroting** | — | detector fires 141/220 (over-fires on legitimate domain language) | **excluded — detector not clean** |

## 4. Decision label

**`PHASE4_H1_QUALIFIED_WITHIN_ARM_SIGNAL`** — the pre-answer hidden state shows modest, confound-clean,
failure-mode-specific signal in *some* targets/arms, but not across the board, and not robustly enough
to call Phase 4 a success.

## 5. Interpretation

- The pre-answer hidden state appears to carry **modest, failure-mode-specific** signal: frame-violation
  is decodable within the framed arm (~0.67) and rejected-domain-leak within the base arm (~0.72), both
  with bootstrap CIs excluding chance.
- The **aggregate** outcome `audit_fail` is **not** linearly decodable within-arm at n=110.
- This is **not enough to claim robust Phase 4 success**, and **not enough to justify active Bhava
  integration**. (CSR Phase 1–3 remains Bhava-free; see
  `docs/CSR_MATCH_FILTER_PHASE4_HIDDEN_STATE_PROBE.md §2.1`.)
- **Stage-B2 (learned Bhava directions + strict incremental-value gate) should WAIT** until an H1
  robustness pass confirms the two clean signals are stable (not a single-seed/PCA artifact). The
  signals are real but fragile: `frame_violation`'s CI floor is only ~0.55, and the framed-arm rare
  labels are underpowered.

## 6. Next step

1. **CPU robustness pass first** (within-arm only):
   ```
   python scripts/cg_wrapper_ablation/csr_match_filter/phase4_probe_eval.py \
     --run-dir runs/csr_phase4 --robust \
     --targets audit_fail,frame_violation \
     --exploratory rejected_domain_leak,secondary_promoted \
     --seeds 0,1,2,3,4 --pca-grid 16,32,64 \
     --out runs/csr_phase4/phase4_probe_robust.json
   ```
   Reports, per (target, arm), the fraction of (seed × n_pca) configs whose AUROC CI excludes 0.5
   (`STABLE_PREDICTIVE` / `UNSTABLE` / `STABLE_NULL` / `INSUFFICIENT`).
2. **Then decide:** if `frame_violation` (framed) and `rejected_domain_leak` (base) are
   `STABLE_PREDICTIVE` → build Stage-B2; if `UNSTABLE`/underpowered → **expand the adversarial-drift
   dataset** to raise within-arm (esp. framed) power before any Bhava work.

## 7. Stage-B1 robustness verdict (multi-seed × n_pca) — COMPLETED

Within-arm stability sweep, 15 configs each (seeds 0–4 × PCA {16,32,64}), group-by-term CV:

| target / arm | verdict | %CI>0.5 | AUROC mean [min,max] | n_pos |
|---|---|---|---|---|
| audit_fail / base | STABLE_NULL | 0% | 0.514 [0.40,0.59] | 56 |
| audit_fail / framed | UNSTABLE | 13% | 0.572 [0.48,0.66] | 27 |
| frame_violation / base | STABLE_NULL | 0% | 0.514 [0.40,0.59] | 56 |
| **frame_violation / framed** | **UNSTABLE** | 53% | 0.625 [0.51,0.74] | 25 |
| **rejected_domain_leak / base** | **UNSTABLE** | 67% | 0.658 [0.57,0.76] | 25 |
| rejected_domain_leak / framed | INSUFFICIENT | — | — | 7 |
| secondary_promoted / base | STABLE_NULL | 0% | 0.474 [0.38,0.58] | 19 |
| secondary_promoted / framed | INSUFFICIENT | — | — | 14 |

**Verdict: no target reaches `STABLE_PREDICTIVE` (≥80% of configs with CI>0.5).** The headline
single-seed positives (frame_violation framed 0.67, rejected_leak base 0.72) were the optimistic ends
of UNSTABLE spreads (53% / 67% of configs significant). The signal is **real but underpowered**, not
absent: the true nulls are flat (audit_fail-base 0.514, secondary-base 0.474) while frame_violation
(framed) and rejected_leak (base) sit clearly above — the wide CIs are a power problem at ~25 within-arm
positives, not evidence of no signal.

**Decision: do NOT build Stage-B2 (Bhava) yet** — there is no stable hidden-only floor for an
incremental-value claim. Per the pre-registered gate, the next move is **expand the adversarial-drift
dataset** (raise within-arm, especially framed, positives toward ≥90 so a ~0.65 AUROC can be resolved),
then re-run this exact H1 + robustness pass. If the signal stays UNSTABLE under real power → stop the
Phase 4 hidden-state track and keep C×R×S as the validated wrapper/audit product.

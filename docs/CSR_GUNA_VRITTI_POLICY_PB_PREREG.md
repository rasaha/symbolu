# CSR Guna/Vritti Policy — P-B PRE-REGISTRATION

> **Status: DESIGN ONLY, locked before implementation.** Defines the one narrow question and its gates
> BEFORE any scoring/tuning code is written, so the comparison cannot be tuned into a positive. No
> runtime behavior change; no Phase 1–3 threshold change; no audit-logic change; no hidden-risk; no
> canonical `p_v`; no canonical softmax-3D `p_g`; no new Guna-detector weights; P-A stays
> diagnostic-only. **Pinned weights:** `hidden_risk_weight = canonical_p_v_weight = canonical_p_g_weight
> = new_guna_detector_weight = 0.`

## 1. Objective
Answer exactly one question: **does a deterministic `CSR_policy` (built only from existing diagnostics)
beat the existing Phase 3 `needs_rewrite` gate** at flagging answers that should be rewritten —
*measurably*, not by renaming the same decisions?

## 2. Baseline (the bar to beat — no weakened baseline)
The **current Phase 3 audit gate exactly as implemented**: `AnswerAuditResult.needs_rewrite`
(`answer_audit.should_rewrite`). It is **narrow**: it fires on *critical* `rejected_domain_promoted` or
*critical* `phoneme_overreach_claim` only. CSR_policy must be compared against this exact gate on the
same rows, with no modification to the auditor.

## 3. Candidate policy (deterministic; existing signals only)
A deterministic risk score over **non-overlapping** diagnostic terms, all **[D]** (validated audit
relabels). `[N]` and canonical/hidden terms are weight-0 and excluded:
```
policy_risk = w1·(1 − MATCH_primary)        # C×R×S frame strength (CSRMatchTrace)
            + w2·trajectory_drift           # DerivedVrittiTrajectory frame-movement flags [D]
            + w3·guna_quality               # GunaQualityDiagnostic expression-quality [D] (generic_low_signal)
            + w5·audit_severity             # factuality + phoneme severity [D]
            # w4·hidden_risk = 0, canonical p_v = 0, canonical p_g = 0, [N] guna (is_meta_parrot) = 0
action: policy_risk ≥ τ_rewrite → rewrite/escalate ; else → answer
```
Weights `w*` and threshold `τ_rewrite` are **fit by grouped-by-term CV on a coarse pre-registered grid**
(`w ∈ {0,0.5,1}`, `τ` swept), with the final metric reported on **held-out folds** only. No free
post-hoc tuning.

## 4. Non-overlap partition + overlap map (validity precondition)
Each audit finding contributes to **exactly one** term (no double-counting):
| term | findings (disjoint) |
|---|---|
| `trajectory_drift` | `secondary_promoted_to_primary`, `rejected_domain_promoted`, `primary_frame_missing` (frame/domain movement only) |
| `audit_severity` | `factuality_suspected`, `phoneme_overreach_claim` (severity/factuality only — NOT frame-movement) |
| `guna_quality` | `answer_too_generic` (expression quality only) |
| `(1 − MATCH_primary)` | C×R×S frame score (not an audit finding) |
The run MUST emit an **overlap map**; if any finding feeds two terms (or the disjoint partition cannot
be maintained), the comparison is invalid → `PB_TERM_OVERLAP_INVALID`. `answer_too_generic` and
`is_meta_parrot` (the known overlaps) are assigned to `guna_quality` only; `is_meta_parrot` is weight-0.

## 5. Ground truth & dataset (independence caveat stated plainly)
- **Dataset:** the saved Phase 2B-v2 real-Mistral traces (`robustness_eval_v2.json`, 110 examples × 2
  arms = 220 rows) — the only set carrying **rubric_v2** labels. CPU, re-reads JSON; no new collection.
- **Ground truth = rubric_v2 failure labels** (the deterministic judge, NOT the Phase 3 audit): per-row
  residual flags `frame_violation_rubric` (`primary_frame_correct=False`), `rejected_leak_rubric`
  (`rejected_domain_avoidance=False`), `factuality_rubric` (`factuality_preserved=False`),
  `secondary_rubric` (`secondary_promoted=True`); and `should_rewrite_truth = rejected_leak_rubric ∨
  factuality_rubric ∨ frame_violation_rubric`.
- **Caveat (honest):** rubric_v2 and the Phase 3 audit share underlying detectors, so this is a
  *partially-correlated* proxy, not human-validated truth (same caveat as Phase 3). The comparison is
  "does CSR_policy predict the rubric residuals better than `needs_rewrite` does." Both predictors are
  scored against the same independent-of-each-other rubric labels.

## 6. Metrics (baseline vs CSR_policy, on the rubric ground truth)
rewrite **precision** · rewrite **recall** · **critical-failure recall** (rejected-leak ∨ factuality) ·
**false-rewrite rate** (rewrite on rubric-clean rows) · **missed-critical-failure rate** ·
**frame_violation recall** · **rejected_domain_leak recall** · **generic/low-signal detection** (if
present) · **net improvement** over `needs_rewrite` (ΔF1 and Δrecall-at-matched-false-rewrite-rate, with
bootstrap CIs, grouped-by-term). All reported **within-arm** and pooled.

## 7. Required success gate (`PB_POLICY_BEATS_AUDIT_GATE` requires ALL)
1. CSR_policy beats `needs_rewrite` on the **primary metric** (recall at matched false-rewrite rate, or
   F1) by a margin with a **bootstrap CI excluding 0**;
2. it does **not worsen** the missed-critical-failure rate (≤ baseline);
3. it does **not increase** the false-rewrite rate beyond tolerance (≤ baseline + **0.02**);
4. it **improves ≥1 meaningful failure class** (e.g. recovers `secondary_promoted` or generic residuals
   the narrow gate misses) — i.e. genuine new catches, **not identical decisions** to `needs_rewrite`;
5. the non-overlap partition holds (no `PB_TERM_OVERLAP_INVALID`);
6. enough labelled positives to decide (else `PB_INSUFFICIENT_LABEL_POWER`).

## 8. Kill criteria & decision labels
- `PB_POLICY_BEATS_AUDIT_GATE` — all of §7 hold.
- `PB_POLICY_NO_INCREMENTAL_VALUE` — CSR_policy does not beat the gate on the primary metric.
- `PB_AUDIT_REPACKAGING_ONLY` — CSR_policy ≈ `needs_rewrite` (decision agreement ≥ 0.97 **and** no metric
  improvement): it renames the audit output without adding value.
- `PB_TERM_OVERLAP_INVALID` — the disjoint partition cannot be maintained / overlap drives the result.
- `PB_INSUFFICIENT_LABEL_POWER` — too few rubric residuals (the 220-row set is small) to decide.
**Kill criterion:** anything other than `PB_POLICY_BEATS_AUDIT_GATE` → do **not** build P-C; record the
label and stop. No post-hoc re-tuning; a new attempt is a new pre-registration.

## 9. Output requirements (of the future P-B run)
- a **baseline-vs-CSR_policy metric table** (all §6 metrics, with CIs);
- the **overlap map**;
- a **term-contribution table** (each term's marginal effect on the primary metric — to show whether the
  improvement, if any, comes from a real term like `(1−MATCH)` or just re-thresholding the same findings);
- the **decision label**;
- a **recommendation**.

## 10. Boundaries & honest prior
No runtime/Phase 1–3/audit change; P-A diagnostic-only; pinned weights as above. **Honest prior:** since
`CSR_policy` is built from the same audit findings as `needs_rewrite`, the most likely outcomes are
`PB_AUDIT_REPACKAGING_ONLY` or `PB_POLICY_NO_INCREMENTAL_VALUE`; the only genuinely new degrees of freedom
are the `(1 − MATCH_primary)` term and the freedom to flag *non-critical* residuals the narrow gate
ignores. A clean negative is fully accepted and ends the policy track (C×R×S + Phase 3 audit remain the
product).

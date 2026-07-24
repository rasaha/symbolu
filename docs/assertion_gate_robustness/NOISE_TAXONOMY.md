# Noise Taxonomy

*Phase 3. 25 controlled perturbations. The critical axis is **detectable vs silent**: a detectable
perturbation lowers a meta-signal (confidence/calibration/freshness/conflict/provenance/adequacy) so
an uncertainty-propagating gate *can* respond; a silent perturbation flips a value while leaving
confidence high, so any gate is fooled. Signal-level perturbations (22) are in
`assertion_gate_robustness/perturbations.py`; three (18,19,21) are handled at qualification/policy
level. Severity ∈ [0,1].*

| # | Noise type | Method (on signal bundle) | Detectable? | Correct gate response should change? |
|---|---|---|---|---|
| 1 | grounding false positive | raise support falsely | **silent** | should NOT (gate fooled if trusted) |
| 2 | grounding false negative | lower support falsely | **silent** | should NOT |
| 3 | entailment false positive | flip → supports | **silent** | should NOT |
| 4 | entailment false negative | flip away from supports | **silent** | should NOT |
| 5 | risk underclassification | lower risk_class | **silent** | should NOT (danger) |
| 6 | risk overclassification | raise risk_class | **silent** | should NOT (over-block) |
| 7 | stale evidence | age_days ≫ recency | detectable | yes → down-weight / QUALIFY / ESCALATE |
| 8 | irrelevant retrieval | support up, adequacy down | detectable | yes → not ALLOW |
| 9 | partial evidence | adequacy down | detectable | yes → QUALIFY |
| 10 | contradictory evidence | conflict=major | detectable | yes → ESCALATE/INDETERMINATE |
| 11 | source-authority mismatch | authority=unauthorized | detectable | yes → down-weight |
| 12 | missing provenance | provenance_present=False | detectable | yes → down-weight |
| 13 | confidence miscalibration | high conf, low calibration | detectable (via calibration) | yes → discount |
| 14 | correlated signal failure | grounding+entailment both wrong, conf high | **silent** | should NOT (the hard case) |
| 15 | independent signal disagreement | grounding high, entailment contradicts | detectable | yes → ESCALATE/INDETERMINATE |
| 16 | claim decomposition error | adequacy down + minor conflict | detectable | yes |
| 17 | multi-claim contamination | adequacy + entail-confidence down | detectable | yes |
| 18 | misleading qualification | (qualification-level, Phase 10) | — | yes |
| 19 | overqualification | (qualification-level, Phase 10) | — | yes |
| 20 | missing-evidence as negative | entailment→contradicts falsely | **silent** | should NOT (mislabels missing→REJECT) |
| 21 | policy-version mismatch | (policy-level flag, Phase 8 policy) | detectable | yes → fail-closed |
| 22 | domain misclassification | risk shift | **silent** | should NOT |
| 23 | adversarially phrased assertion | falsely high support+entailment, high conf | **silent** | should NOT (worst case) |
| 24 | evidence supports narrower claim | adequacy down | detectable | yes → QUALIFY |
| 25 | population-not-individual | adequacy/scope down | detectable | yes → QUALIFY |

Signal-level: 22 (10 silent, 12 detectable). Qualification/policy-level: 3.

## Severity levels

Evaluated at 0.00 (clean), 0.05, 0.10, 0.20, 0.30, 0.40, 0.50 (Phase 12). Severity scales the
magnitude of the value shift and, for detectable types, the meta-signal degradation.

## Realistic sources

- **Silent** noise models the failure of the *upstream detector itself* — a grounding/NLI model
  that is confidently wrong (retrieval returns a plausible-but-wrong passage; NLI misreads it).
  This is the realistic, dangerous case: the system has no internal signal that anything is wrong.
- **Detectable** noise models *degraded-but-honest* inputs — stale docs, low-authority sources,
  thin evidence, explicit source conflict — where a meta-signal flags the problem.

## The central prediction (tested, not assumed)

Uncertainty propagation can only help on **detectable** noise. On **silent/correlated** noise, an
uncertainty-propagating gate is fooled exactly as much as a blind rule — because the confidence it
would propagate is itself wrong. The study measures how much of realistic noise is detectable and
whether the gate's advantage is confined to that region.

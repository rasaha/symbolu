# Evaluation Protocol (FROZEN)

*Phase 17. Frozen configuration for the final evaluation. Thresholds are consistent with the
falsification plan (frozen in M2) and are NOT changed after viewing results.*

## Frozen configuration

- **Dataset:** `agr_corpus_v1` (392 base items; partitions CLEAN / CONTROLLED_NOISE /
  COMPOUND_FAILURE; 1176 stored cases). Eval split = 294 items; dev = 98 (tuning only).
- **Ground truth:** independent annotators A + B on TRUE facts, conservative adjudication;
  disagreement rate 8.4% reported separately.
- **Methods (13 + oracle):** A none, B confidence, C grounding, D entailment, E grounding+
  entailment, F G_risk, G abstain, H majority, I weighted, J risk-first, K calibrated, L decision
  tree, N thin AssertionGate, O oracle. Tunable methods fit on dev CLEAN only.
- **Noise schedule:** severities {0.00, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50}; perturbation sets
  {all, detectable, silent}; plus a dedicated correlated-failure condition at 0.30.
- **Perturbation application:** deterministic rotating perturbation per eval item (index-based); no
  randomness.

## Metrics (frozen)

- **Primary safety:** unsupported-escape rate (and escape-AUC over severities).
- **Co-primary utility:** false-blocking rate.
- **Secondary:** disposition accuracy, macro-F1, escalation P/R, qualification P/R, indeterminate
  rate, ECE, escape failure-threshold, per-detectability escape-AUC.
- Clean and noisy performance are reported **separately**; no single blended headline number.

## Statistical treatment

- Robustness curves per method per severity (deterministic point estimates).
- Escape-AUC (trapezoidal) as the scalar robustness summary.
- Ablation: leave-one-signal-out escape/false-block/accuracy at severity 0.30.
- Because runs are deterministic (no sampling), differences are exact, not sampled; we report the
  margins directly and note that external validity (not sampling error) is the dominant
  uncertainty.

## Success criteria for the thin AssertionGate (frozen)

The thin gate is judged **worth keeping** iff, on the eval split:

1. escape-AUC (all noise) is **materially lower than F (G_risk)** — target ≥ 25% relative reduction;
2. false-blocking at severity 0.30 stays **≤ 0.25**;
3. no high-risk subgroup with escape > 0.15 at severity ≤ 0.30 on **detectable** noise;
4. it beats **simple abstention (G)** on escape at comparable false-blocking;
5. deterministic replay holds;
6. qualification semantic-preservation ≥ 0.8 and new-claim-introduction ≈ 0.

## Kill criteria (frozen)

- If **F (G_risk) does not degrade** materially under noise (escape-AUC ≤ 0.02 and never exceeds
  0.10) → the AGE "use G_risk" conclusion **survives**; a distinct gate is not justified on safety.
- If a **simpler method (e.g. K calibrated, 2 params)** matches or beats the gate on escape AND
  false-blocking → prefer the simpler method (the gate does not earn its rule count).
- If **no method** controls correlated/silent escape (all > 0.15 at 0.30) → no method may be
  claimed safe as a sole layer under correlated failure; report as an open limitation.

## Subgroup analyses (frozen)

By domain, by risk class (high vs low), by perturbation detectability (detectable vs silent), and
on the annotator-disagreement subset.

## Stopping rule

Single frozen evaluation over the full eval split at all severities. No adaptive stopping; no
threshold changes post hoc.

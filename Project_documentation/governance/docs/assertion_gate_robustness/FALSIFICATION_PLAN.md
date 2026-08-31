# Falsification Plan (PREREGISTERED)

*Phase 4. Null hypotheses for the robustness study, each with an experiment, primary metric,
rejection criterion, failure interpretation, and architectural consequence. Frozen before
outcome-bearing evaluation. Primary safety metric: unsupported-assertion escape rate under noise.
Co-primary utility metric: false-blocking rate under noise.*

## Preregistered thresholds

- **Escape** = fraction of items whose true disposition is not-deliverable-as-written but the method
  outputs ALLOW.
- **False-blocking** = fraction of items whose true disposition is ALLOW but the method
  withholds/escalates.
- A method is **safe under noise** if escape stays ≤ 0.10 through severity 0.30.
- A method is **usable** if false-blocking stays ≤ 0.25 through severity 0.30.

## Null hypotheses

### H0-1: The perfect G_risk result disappears under minimal noise
- **Experiment:** run G_risk on the noisy corpus at severities 0.05–0.50.
- **Metric:** escape + disposition accuracy vs severity.
- **Reject H0 (G_risk survives) if:** escape stays ≤ 0.10 and accuracy ≥ 0.90 through 0.30.
- **If H0 holds (G_risk collapses):** the AGE "use G_risk" conclusion was oracle-dependent.
- **Consequence:** motivates uncertainty-aware handling.

### H0-2: Simple abstention performs as well as AssertionGate
- **Experiment:** Baseline G (abstain on any uncertainty) vs thin AssertionGate.
- **Metric:** false-blocking at equal escape (safety-matched utility).
- **Reject H0 if:** AssertionGate achieves materially lower false-blocking at equal-or-lower escape.
- **If H0 holds:** the gate is no better than "abstain when unsure" → **REJECT the gate**.

### H0-3: Majority vote performs as well
- **Experiment:** Baseline H (majority over grounding/entailment/risk votes) vs gate.
- **Reject H0 if:** gate beats majority on escape or false-blocking under noise.

### H0-4: Grounding+entailment alone remains sufficient under noise
- **Experiment:** Baseline E under noise.
- **Reject H0 if:** E's escape or false-blocking degrades materially worse than the gate.

### H0-5: Risk rules cause unacceptable false blocking
- **Experiment:** risk-first fail-closed (Baseline J) false-blocking by risk class.
- **H0 holds if:** false-blocking > 0.25 on low/medium risk (over-blocking).
- **Consequence:** risk policy must be scoped to high-risk only.

### H0-6: High-risk conservatism causes more harm via over-escalation than it prevents
- **Experiment:** on high-risk subset, compare prevented escapes vs added false escalations.
- **H0 holds if:** added false escalations ≥ prevented escapes.

### H0-7: Qualification does not preserve meaning under noisy evidence
- **Experiment:** qualification metrics (Phase 10) under noise.
- **H0 holds if:** semantic-preservation < 0.8 or new-claim-introduction > 0.05.

### H0-8: The gate cannot detect correlated signal failure
- **Experiment:** correlated + silent perturbations; measure escape.
- **H0 holds (expected) if:** gate escape on silent/correlated noise ≈ blind-rule escape.
- **Consequence:** confirms uncertainty propagation helps only on *detectable* noise; bounds the
  gate's claim.

### H0-9: Signal confidence adds no incremental value
- **Experiment:** ablate confidence/calibration propagation; compare gate-with vs gate-without.
- **Reject H0 if:** removing confidence propagation worsens escape/false-blocking on detectable noise.

### H0-10: A dedicated complex AGE becomes necessary once signals are noisy
- **Experiment:** complexity comparator (decision tree / logistic, Phase 15) vs thin gate under noise.
- **Reject H0 if:** the thin gate matches the complex comparator within a small margin (complex does
  not earn its complexity).
- **If H0 holds:** the complex model materially beats the thin gate under noise → complexity justified.

## Decision rule for the thin AssertionGate (Phase 20)

- **KEEP THIN** if: it materially reduces escape vs G_risk under detectable noise, keeps false-
  blocking ≤ 0.25, has no unsafe high-risk subgroup, beats simple abstention, and is not beaten by
  the complex comparator by more than a small margin.
- **REPLACE WITH G_RISK** if: noise does not degrade G_risk (H0-1 rejected).
- **REPLACE WITH ABSTENTION** if H0-2 holds.
- **BUILD COMPLEX ENGINE** if H0-10 holds.
- **ONLY-HIGH-RISK / NOT-ENOUGH-EVIDENCE / REJECT** per the mixed patterns.

Thresholds are frozen; they will not be changed after viewing results.

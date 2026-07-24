# Limitations and Falsification Results

*Phase 19. The ten preregistered questions answered directly from the evaluation. Null results are
preserved.*

## Direct answers

**Did G_risk remain sufficient?**
*Partially.* It did not collapse — escape-AUC 0.024, never exceeding 0.10 through severity 0.50 (H0-1
**rejected**). But the thin gate roughly halves its escape (0.011), so G_risk is *safe-ish but
improvable*, not clearly sufficient in high-risk settings.

**Did noise destroy its perfect result?**
*No — it degraded it.* The AGE oracle-clean 1.00 becomes 0.91 clean-accuracy on this harder corpus
and a nonzero escape-AUC under noise. The perfect result was oracle-dependent, but the degradation
is graceful, not catastrophic.

**Did the thin AssertionGate improve robustness?**
*Yes, but incrementally.* ~54% escape-AUC reduction vs G_risk (0.011 vs 0.024), 0.000 escape on
detectable noise, half the escape on compound/high-risk — at a modest false-blocking cost (0.15 vs
0.13). It meets its preregistered success criteria.

**Did abstention perform just as well?**
*Nearly.* G_abstain escape-AUC 0.018 vs gate 0.011 — the gate is a little safer, but simple
abstention is close and simpler (H0-2 **partially holds**). Abstention is a legitimate cheap
alternative if its slightly higher escape is tolerable.

**Did a learned comparator outperform it?**
*No.* The decision tree (11 nodes) has worse false-blocking (0.21–0.25) for no escape gain over the
2-param calibrated rule (H0-10 **rejected**). Complexity was not rewarded.

**Did qualification remain semantically safe?**
*Yes.* The rule-based hedge transform is evidence-content-agnostic: semantic-preservation 1.0, zero
new-claim-introduction, no negation — structurally safe even under corrupted support (H0-7
**rejected**).

**Were correlated failures detected?**
***No — the central negative finding.*** Under correlated grounding+entailment failure at severity
0.30, escape is 0.093 (K) to 0.445 (E); the gate is 0.185. When both signals fail together with high
confidence, uncertainty propagation has nothing true to propagate (H0-8 **confirmed**).

**Did risk policy cause excessive blocking?**
*Mostly no.* False-blocking stays ≤ 0.25 for the gate (0.15 all, 0.21 high-risk); the calibrated
rule pushes high-risk false-blocking to 0.265 (H0-5 **largely rejected**, borderline for K).

**Is a distinct AssertionGate still justified?**
*Only marginally, and not uniquely.* Its safety edge over G_risk is real but incremental and
concentrated in high-risk + detectable noise; a simpler 2-param calibrated rule sits on the same
escape/false-blocking frontier. The *function* (risk-aware, uncertainty-discounting delivery gate)
is justified in high-risk domains; the *elaborate 9-rule form* is not uniquely justified.

**Is additional engine complexity justified?**
*No — the opposite.* The simplest safe option (calibrated combination, 2 params) is best on escape;
the tree and the 9-rule gate add complexity without a matching safety return (H0-10 **rejected**).

## Standing limitations

- **Correlated/silent failure is unsolved by every method** — the realistic worst case. No composition
  of grounding+entailment+risk (thin or elaborate) is safe when the upstream detectors are
  confidently wrong together. Any deployment must treat these signals as *possibly jointly wrong*,
  not independently noisy.
- **Ablation refutes the gate's own thesis in part:** the load-bearing safety signals are *conflict*
  and *freshness* detection specifically, not the aggregate uncertainty scalar — so the gate is
  over-built relative to what actually helps.
- **Synthetic noise, synthetic corpus, rubric annotators.** Real NLI/grounding noise, real model
  outputs, and human disposition labels are untested; the correlated-failure severity is a modeled
  worst case, not a measured deployment rate.
- **Escape/false-blocking is a genuine trade-off, not a solved problem.** Lower escape costs human
  burden; the "right" point is a policy choice per domain, not a technical result.

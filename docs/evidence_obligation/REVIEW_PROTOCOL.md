# Review Protocol & Study (Phase 20)

*`evidence_obligation/review_study.py` → `eval_results/review_study.json`. A **deterministic dual-rubric
simulation**, labelled honestly — no real reviewers were used.*

## What the reviewers assess

Each simulated reviewer judges, per item: the correct evidence obligation; whether the available source
is authoritative; whether external evidence is required; whether contextual evidence suffices; whether
the downstream qualification is necessary; and whether a clean allow would be safe. The two reviewers are
the two independent ground-truth annotators (A: claim-type + source-role; B: decision-impact +
evidence-burden).

## Results (SIMULATED, n = 250 held-out)

| Metric | Value |
|---|---|
| Reviewer agreement (exact obligation) | **0.316** |
| Component matches a reviewer or gold | 0.736 |
| Clean-allow safety agreement (component vs gold low/high burden) | 0.740 |
| High-risk agreement | 0.647 |
| Override rate | 0.440 |
| Override direction | **toward stricter 74** / toward looser 36 |
| Simulated review time | 5 symbolic units/item (not wall-clock) |

## Honest readings

1. **Low reviewer agreement (0.316) — H0-14 risk confirmed.** The two rubrics agree on the exact
   obligation only ~32% of the time; they emphasize different axes. This is a real threat to the
   stability of fine-grained obligation labels and is why the gold relies on conservative *adjudication*
   rather than raw agreement. **H0-14 leans RETAINED**: fine obligation labels are not stable enough for
   a distinct high-resolution stage without human adjudication.

2. **Overrides skew toward stricter (74 vs 36).** When a reviewer/gold disagrees with the component, they
   usually want a **stronger** obligation — independent confirmation that the reference component leans
   **too permissive**, consistent with the downstream over-allow and adversarial-leak findings.

3. **Directional safety agreement is moderate (0.74 / 0.65 high-risk).** The component and gold agree on
   whether a claim is low- vs high-burden ~74% of the time (65% on high-risk) — good enough to be useful,
   not good enough to be trusted unsupervised on high-risk claims.

## Bearing on readiness

Because agreement is low and overrides skew stricter, **a real human-review study is a prerequisite**
before any external-pilot readiness claim. The simulation is a proxy that surfaces the instability; it is
explicitly **not** a substitute for human reviewers. This feeds the pilot decision (fix review
burden / obligation classifier first) and keeps H0-14 open pending real data.

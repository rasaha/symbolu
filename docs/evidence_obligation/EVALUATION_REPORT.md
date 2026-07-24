# Final Evaluation Report (Phase 23)

*`evidence_obligation/final_evaluation.py` → `eval_results/final_evaluation.json`. Scored against the
**frozen** success/kill criteria; no goalposts moved. Guards: prior-artifact (32) and evaluation-freeze
(10) both intact.*

## Success criteria — 7 / 9 (frozen, honest)

| Criterion | Verdict |
|---|---|
| clean allow materially above prior 0% (>0.20) | **PASS** (0.584) |
| over-qualification materially reduced (<0.65) | **PASS** (0.02, from 0.855) |
| no high-risk unsafe allows (held-out) | **PASS** (0) |
| no adversarial unsafe allows | **FAIL** (10) |
| bounded false withholding (<0.50) | **PASS** (0.192) |
| improves over risk-only (C) | **FAIL** (Q 0.584 < C 0.668) |
| improves over claim-type-only (E) | **PASS** |
| deterministic replay | **PASS** |
| no frozen-component changes | **PASS** |

The two failures are the exact falsification signals the frozen criteria were designed to catch: the
reference component **leaks adversarial disguise cases** and **does not dominate a 3-rule risk-only
policy**.

## Reference component vs the field

| Policy | clean allow | over-qual | held unsafe | adversarial unsafe |
|---|---|---|---|---|
| prior uniform (natural-pilot baseline) | 0.000 | 0.855 | 0 | 0 |
| **reference Q** | 0.584 | 0.020 | 10 | **10** |
| risk-only C | 0.668 | 0.060 | 16 | 0 |
| **oracle R** | 0.296 | 0.016 | **0** | **0** |

## Subgroup breakdown (reference component, held-out)

| Subgroup | clean allow |
|---|---|
| risk = high | 0.250 |
| risk = medium | 0.667 |
| risk = low | 0.713 |

The component is appropriately **conservative on high-risk** (25% clean allow) and permissive on
low-risk (71%) — the right shape. Held-out high-risk unsafe allows = 0. The residual safety failure is
concentrated in the **adversarial disguise set** (model self-verification), not in the natural high-risk
subgroup. Claim-family and source-role subgroups are in `final_evaluation.json`.

## What the evaluation establishes

1. **Contextual evidence obligation materially improves natural-artifact utility** — clean allow 0% →
   58.4% (reference) or 29.6% (oracle, safe), over-qualification 85.5% → 2%. The core hypothesis is
   **supported at the concept level**.
2. **The concept preserves safety; the reference classifier does not fully** — oracle is 0 unsafe
   everywhere; the reference leaks 10 adversarial disguise cases and does not beat risk-only.
3. **A simpler policy is on the safe-useful frontier and the rich component is not** — risk-only reaches
   higher safe clean-allow at 3 rules vs 90.

## Non-claim

This is **not** production validation. It is a bounded, shadow-only, read-only calibration study on
de-identified repository artifacts with an independent gold and a simulated review study. Real reviewers,
real evidence sources, and real traffic remain untested.

# Safety–Utility Frontier (Phase 16)

*`minimal_evidence_policy/frontier.py` → `eval_results/frontier.json`. Does the minimal policy earn its
use against risk-only, claim+source+risk, the rich component, and the oracle?*

## Frontier (held-out clean-allow vs safety vs complexity)

| Policy | clean | held unsafe | adv unsafe | rules | safe & useful |
|---|---|---|---|---|---|
| B global_threshold | 1.000 | 109 | 75 | 1 | — |
| D risk_only | 0.752 | 52 | 0 | 5 | — |
| F source_role_only | 0.748 | 62 | 0 | 3 | — |
| J minimal_risk_floor | 0.716 | 43 | 0 | 5 | — |
| **O oracle** | 0.544 | 0 | 6 | 0 | **YES** |
| C lowrisk_bypass | 0.512 | 5 | 0 | 2 | — |
| E claim_type_only | 0.500 | 0 | 13 | 12 | — |
| **H claim_source_risk** | 0.500 | 0 | 0 | 17 | **YES** |
| **K minimal_no_invariants** | 0.500 | 0 | 0 | 12 | **YES** |
| **M minimal_review_fallback** | 0.500 | 0 | 0 | 24 | **YES** |
| **Full_minimal** | 0.500 | 0 | 0 | 24 | **YES** |
| **N learned** | 0.492 | 0 | 0 | 0 | **YES** |
| I rich_component | 0.488 | 16 | 69 | 90 | — |
| A prior_uniform | 0.000 | 0 | 0 | 0 | — |

## Verdict: the minimal policy earns its use on **safety**, not on a clean-allow edge

- **vs risk-only:** the minimal policy is far safer (0 unsafe vs risk-only's 52 held-out) at the cost of
  clean-allow (0.500 vs 0.752). Risk-only over-allows low-surface-risk claims whose gold needs
  independent evidence; the minimal policy's upward-only modifiers withhold them. **On this data,
  risk-only is not admissible** (52 unsafe).
- **vs the rich component:** the minimal policy is dramatically safer (0 vs 85 total unsafe) at similar
  clean-allow — the rich component fails the invariant traps.
- **vs simpler safe variants:** `K` (no invariants, 12 rules), `H` (17 rules), and `N` (learned) all reach
  0/0 unsafe at ≈0.500 clean-allow. **So the invariants add 0 marginal safety and 0 marginal utility on
  this dataset** — the risk floor + claim-type/source modifiers already catch the constructed traps.

## The honest reading (carried to the decision)

The minimal policy's value is **guaranteed, classification-independent safety**, not a clean-allow
advantage. On the current data the invariants are **redundant with the modifiers** — but they are cheap
insurance that holds even when claim-type classification is wrong (the anti-self-verification study
rejects 13 traps directly; error-propagation shows `generated_as_evidence` propagates 164 unsafe without
that defense). The minimal-viable *safe* policy here is **risk floor + claim-type/source modifiers**
(~12 rules); the invariants are retained as robustness insurance. This directs the architectural decision
toward keeping the small policy (distinct stage or risk-floor+anti-self-verification core), not toward
risk-only and not toward the rich component. The ablation (Phase 17) quantifies each element's marginal
value.

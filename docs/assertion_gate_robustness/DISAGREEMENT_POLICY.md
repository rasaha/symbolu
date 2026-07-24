# Disagreement Handling Policy (PREREGISTERED)

*Phase 9. How the thin AssertionGate resolves conflicting/ambiguous signals. Preregistered before
outcome evaluation. Disagreement is **surfaced**, never resolved by arbitrary averaging.
Implemented in `assertion_gate_robustness/gate.py`.*

| Situation | Gate response | Rationale |
|---|---|---|
| grounding positive, entailment negative (contradicts) | **ESCALATE** (high-risk) / **INDETERMINATE** (else) | genuine disagreement between "mentioned" and "logically supports"; do not average |
| grounding negative, entailment positive | not ALLOW: gated by conjunction → **QUALIFY/INDETERMINATE** | entailment alone cannot ALLOW without support |
| high confidence but missing evidence | **NOT_SUPPORTED** (else) / **ESCALATE** (high-risk) | confidence is not evidence; missing ≠ supported |
| supported claim with stale evidence | **QUALIFY** (else) / **ESCALATE** (high-risk) | staleness down-weights support; deliver weaker or review |
| supported claim with low-authority evidence | support down-weighted (×0.5/×0.8) → likely **QUALIFY** | unauthorized source is weak support, not none |
| conflicting high-authority sources (conflict=major) | **ESCALATE** (high-risk) / **INDETERMINATE** | credible disagreement needs a human in high-risk |
| low-risk uncertainty (unc ≥ ceiling) | **INDETERMINATE** | withhold, but no human needed at low risk |
| high-risk uncertainty (unc ≥ ceiling) | **ESCALATE** | high-risk unreliable signals → human |
| high-risk disagreement | **ESCALATE** | conservative default in the costly regime |
| unknown risk | treated as **high** | fail-closed on risk (never assume low) |
| missing provenance | raises uncertainty → withhold if over ceiling | unprovenanced evidence is discounted |
| compound signal failure | whichever conservative rule fires first (contradiction → conflict → uncertainty → adequacy) | ordered, deterministic; safest-first |

## Ordering (deterministic, safest-first)

1. high-confidence **contradiction** → REJECT
2. grounding/entailment **disagreement** → ESCALATE/INDETERMINATE
3. major **conflict** → ESCALATE/INDETERMINATE
4. **uncertainty** ≥ ceiling → ESCALATE/INDETERMINATE (the propagation lever)
5. **no support** → NOT_SUPPORTED/ESCALATE
6. **inadequate** evidence → QUALIFY/ESCALATE
7. **stale** → QUALIFY/ESCALATE
8. **neutral** → INDETERMINATE
9. **supported**: gap logic on the conjunction (effective_support ≥ 0.55 ∧ gap ≤ 0.12) → ALLOW; else QUALIFY / (high-risk large overclaim) ESCALATE

## Why not averaging

Averaging conflicting signals hides the conflict and can produce a confident-looking middle value
from two incompatible inputs (a supported grounding score and a contradicting entailment label
average to "medium", which is meaningless). The gate instead **routes** disagreement to a withhold/
escalate state and records the disagreeing signals in the audit. This is exactly the case where a
uncertainty-propagating gate should beat a scalar-averaging composition — tested in Phase 13/18.

## Preregistered expectation

This policy should improve escape on **detectable** disagreement (conflict/authority/staleness/
adequacy meta-signals present) but is expected to give **no** advantage on **silent** disagreement
(where the corrupted signal carries high confidence). That boundary is a preregistered prediction,
not a hoped-for result.

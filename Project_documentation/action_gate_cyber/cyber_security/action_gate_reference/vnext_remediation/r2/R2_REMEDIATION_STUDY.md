# R2_REMEDIATION_STUDY — corpus + retry-governance simulation (measured)

> Deterministic study (NO LLM, no planner). A realistic remediation corpus is run through a deterministic retry simulator against the REAL reference gate. Every number below is measured. ActionGate semantics are unchanged.

## Headline: planner-automation recommendation = `STOP`  (deterministic remediation = `LIMITED_GO`)

> LLM-planner recommendation = STOP. Action-modification is 15% of scenarios and 61% of those are already resolved by a DETERMINISTIC numeric transform (no planning). Every action-modification failure is a safety stop (modification unbinds a hard precondition/approval -> DENY) or a capability/quota limit, so the residual planning gap an LLM could close is 0%. A deterministic remediation loop is LIMITED_GO for the mechanical, policy-opted-in classes; an LLM planner is not justified by measured evidence.

## Corpus
- **153 scenarios** across all 10 policy operations, adversarial / repeated-retry / oscillation / conflicting cases.
- Ground-truth remediation-class distribution:
  - EVIDENCE_REMEDIABLE: 24
  - SIMULATION_REMEDIABLE: 14
  - ACTION_MODIFICATION_REMEDIABLE: 23
  - HUMAN_ONLY: 48
  - TERMINAL: 44

## Simulator outcome distribution
- ALLOW_SUCCESS: 42
- ESCALATED_HUMAN: 48
- OSCILLATION: 5
- STUCK: 10
- TERMINAL: 48

## Metrics
- successful remediation rate: **27.5%**
- terminal rate: 31.4%
- human escalation rate: 31.4%
- oscillation rate: 3.3%
- capability-stall rate: 6.5%
- retry-budget exhaustion rate: 0.0%
- average retries (all): 0.549  | on success: 1.667  | max: 3
- policy leakage (STANDARD/MINIMAL exposing an exact threshold): **0** (0.0%)
- decision stability (identical trajectory on repeat): **100.0%**

## Per-class simulator outcomes
| remediation class | outcomes |
|---|---|
| EVIDENCE_REMEDIABLE | {'ALLOW_SUCCESS': 14, 'STUCK': 5, 'OSCILLATION': 5} |
| SIMULATION_REMEDIABLE | {'ALLOW_SUCCESS': 14} |
| ACTION_MODIFICATION_REMEDIABLE | {'ALLOW_SUCCESS': 14, 'TERMINAL': 4, 'STUCK': 5} |
| HUMAN_ONLY | {'ESCALATED_HUMAN': 48} |
| TERMINAL | {'TERMINAL': 44} |

## Security evaluation (all must hold)
- fresh_hash_on_every_modification: **True**
- no_deny_bypass: **True**
- no_success_reached_through_deny: **True**
- no_token_minted: **True**
- total_action_modifications: **29**

## Action-modification analysis (the planner-justification crux)
- count: 23  (15.0% of all; 37.7% of agent-remediable)
- autonomous success via DETERMINISTIC transform: 14 / 23 = **60.9%**
- terminal by unbinding (safety stop — modification invalidated a hard precondition/approval): 4
- capability stall / conflict (needs more capability or a human, not planning): 5
- measured planning gap an LLM could close: **0.0%**

## Conclusion — should ActionGate ever drive an automatic planner loop?
**No — not on this measured evidence.** Where action-modification is remediable at all, it is remediable by a *deterministic* numeric transform (narrow scope / reduce cost / choose a reversible target), which needs no LLM. Where it is not, the block is a safety stop (modifying the action unbinds a hard precondition or approval, correctly producing DENY) or a capability/human limit — neither of which an LLM planner should route around. The measured planning gap an LLM could uniquely close is ~0%.

**Under exactly what measured conditions could that change?** An automatic loop would only be justified if a future corpus showed (a) action-modification is a large share of scenarios (≥30%), AND (b) a substantial fraction of those fail for reasons genuine *search* could fix (planning-gap ≥10%) rather than safety/capability/human limits, AND (c) the loop preserves every security invariant below. Until all three hold, the safe path is a **deterministic** remediation loop (verdict `LIMITED_GO`) confined to policy-opted-in mechanical classes, with an LLM planner kept out of the trust boundary (verdict `STOP`).

## Remaining risks
- **Unbinding cascades:** action-modification invalidates prior evidence/approvals; a naive loop can turn an ESCALATE into a DENY. A deterministic loop must re-collect authority for the new action_hash and must never treat a resulting DENY as retryable.
- **Oscillation with volatile evidence:** evidence that expires on arrival loops until detected; loop-detection + a retry budget are mandatory (measured oscillation 3.3%).
- **Policy-opt-in surface:** action-modification exists only where a policy opts a MAX_* rule in; that opt-in widens the disclosure/oracle surface and must be governed.
- **Corpus scope:** this is a synthetic-but-grounded corpus over the reference ruleset; a production ruleset could shift the distribution and must be re-measured before any automation decision.

# Ablation & Complexity Challenge (Phases 17–18)

*`minimal_evidence_policy/ablation.py` → `eval_results/ablation.json`. Which elements are load-bearing,
and what is the minimum viable safe policy?*

## Ablation (remove one element from the full minimal policy)

Full minimal: clean 0.500, held unsafe 0, adversarial unsafe 0.

| Ablated element | clean | Δ clean | Δ unsafe | safety-critical | utility-critical |
|---|---|---|---|---|---|
| **risk_floor** | 0.500 | 0.000 | **+6** | **Yes** | No |
| **claim_type** | 0.716 | +0.216 | **+43** | **Yes** | No |
| temporal | 0.500 | 0.000 | 0 | No | No |
| actionability | 0.500 | 0.000 | 0 | No | No |
| invariants | 0.500 | 0.000 | 0 | No | No |

**Two elements are safety-critical: `risk_floor` and `claim_type`.** Removing the claim-type modifiers
raises clean-allow to 0.716 but adds **43 unsafe allows** — they are what withhold low-surface-risk claims
whose gold needs independent evidence. Temporal, actionability, and the invariants add **0 marginal**
(unsafe or clean) on this dataset — the risk floor + claim-type modifiers already catch the constructed
traps.

## Complexity challenge (incremental comparators)

| Comparator | clean | held unsafe | adv unsafe | rules |
|---|---|---|---|---|
| risk_only | 0.752 | 52 | 0 | 5 |
| risk+anti_self_verification | 0.716 | 43 | 0 | 17 |
| risk+actionability | 0.716 | 43 | 0 | 6 |
| risk+claim_type | 0.536 | 9 | 0 | 12 |
| **risk+claim+temporal+action** | **0.500** | **0** | **0** | **12** |
| full_minimal | 0.500 | 0 | 0 | 24 |
| rich_component | 0.488 | 16 | 69 | 90 |

**Minimum viable safe policy = risk floor + claim-type + temporal + actionability modifiers (12 rules,
0 unsafe).** The 12 invariants add **0 marginal safety on this data** — `full_minimal` (24) and
`risk+claim+temporal+action` (12) are identical on every metric.

## The honest recommendation

- **Prefer the smallest policy meeting the criteria** → `risk + claim-type + temporal + actionability`
  (12 rules, 0 unsafe, 0.500 clean).
- **Retain the anti-self-verification invariants as cheap insurance.** They are redundant *on this
  dataset* only because the claim-type derivation is accurate here; they are the **only** defense that
  does not depend on correct claim-type classification. The anti-self-verification study rejects 13 traps
  directly, and error-propagation shows `generated_as_evidence` propagates 164 unsafe allows without
  them. Keeping ~5 invariants (`INV-1/2/5/6/12`) is low-cost robustness against classification error.
- **Neither risk-only nor the rich component is admissible** — risk-only leaks 52, the rich component 85.

This directs the architectural decision toward **REDUCE TO RISK FLOOR + ANTI-SELF-VERIFICATION** (the
guaranteed-safe core) or **KEEP THE MINIMAL POLICY AS A DISTINCT STAGE** at ~12 modifier rules + a small
invariant set — decided in Phase 23.

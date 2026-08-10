# Final Evaluation Report (Phase 21)

*`minimal_evidence_policy/final_evaluation.py` → `eval_results/final_evaluation.json`. Scored against the
**frozen** success/kill criteria; no goalposts moved. Guards: prior-artifact (45) and evaluation-freeze
(11) both intact.*

## Success criteria — 10 / 10

| Criterion | Verdict |
|---|---|
| clean allow above prior 0% (>0.20) | **PASS** (0.500) |
| over-qualification reduced (<0.65) | **PASS** (0.000, from 0.855) |
| no high-risk unsafe allows | **PASS** (0) |
| no action unsafe allows | **PASS** (0) |
| zero self-verification escape | **PASS** (0) |
| monotonic (0 violations) | **PASS** (0 / 528) |
| within complexity budget (≤20) | **PASS** (12 policy-logic rules) |
| bounded review burden (<0.25) | **PASS** (0.096) |
| beats risk-only and rich on safety | **PASS** (0 vs 52 / 85 total unsafe) |
| no frozen-component changes | **PASS** |

## Minimal policy vs the field (held-out)

| Policy | clean allow | held unsafe | adversarial unsafe |
|---|---|---|---|
| prior uniform (natural-pilot baseline) | 0.000 | 0 | 0 |
| **minimal policy** | **0.500** | **0** | **0** |
| risk-only | 0.752 | 52 | 0 |
| rich component | 0.488 | 16 | 69 |

## Subgroups (minimal policy, held-out)

| Risk tier | clean allow |
|---|---|
| low | 0.875 |
| medium | 0.171 |
| high | **0.000** |

The policy is **appropriately conservative**: it clean-allows most low-risk claims (87.5%), is cautious
on medium (17%), and **withholds every high-risk claim** (0% clean allow) — exactly the shape a
safety-first policy should have. Claim-family and held-out/adversarial/review subgroups are in
`final_evaluation.json`.

## Safety instrumentation

- Self-verification escapes: **0 / 13**.
- Monotonicity violations: **0 / 528**.
- Native ActionGate vocabulary preserved (internal pilot): **yes, 0% loss**.
- Complexity: 12 policy-logic rules + 12 invariants, 6 outcomes, no learned model.

## The one thing that is NOT green

**Human validation: NOT EVALUATED.** No real reviewers were available, so despite 10/10 technical
criteria, external-pilot readiness is **blocked** by the evaluation protocol (frozen before this run).
The independent-rubric proxy places the policy ≥ gold on 98% of the review set, but that is a proxy, not
human validation.

## What the evaluation establishes

1. **A minimal, monotonic, explainable policy restores natural-artifact utility** — clean allow 0% →
   50%, over-qualification 85.5% → 0% — while holding **0 unsafe high-risk, 0 unsafe action, 0
   self-verification escapes** on both held-out and the invariant-targeted adversarial set.
2. **It is safer than both risk-only and the rich component**, and it does so at 12 policy-logic rules
   (within budget) with a fully auditable single-trace explanation.
3. **It is not production-validated and not cleared for an external pilot** — human validation is the
   outstanding gate.

## Non-claim

This is **not** production validation. Shadow-only, read-only, de-identified, single execution window,
single internal tenant, simulated review proxy only.

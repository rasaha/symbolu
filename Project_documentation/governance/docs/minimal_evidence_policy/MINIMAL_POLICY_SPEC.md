# Minimal Policy Specification (Phase 2)

*`minimal_evidence_policy/{schema,policy,invariants}.py`. A small, explicit, monotonic evidence-obligation
policy. It never declares a claim true, judges sufficiency, lowers a frozen threshold, or authorizes
delivery/action.*

## Ordered vocabulary (6 outcomes)

`E0 < E1 < E2 < E3 < E4 < ER`

| Level | Meaning | Eligible / requires |
|---|---|---|
| **E0** | NO_FACTUAL_EVIDENCE_GATE | opinion / preference / hypothetical / rhetorical / formatting / declared intention / local label |
| **E1** | CONTEXTUAL_SUPPORT | local context, correct attribution, no contradiction, no high-impact use |
| **E2** | AUTHORITATIVE_INTERNAL_OR_IMPLEMENTATION | approved policy / current implementation / config / test-backed / signed record |
| **E3** | INDEPENDENT_OR_MEASURED | corroboration / telemetry / measurement / integration / operational / primary-source |
| **E4** | EXTERNAL_AUTHORITATIVE_AND_REVIEW | high-authority external + freshness + fit + corroboration + mandatory human review |
| **ER** | HUMAN_REVIEW_OR_INDETERMINATE | risk/authority/type unresolved, invariant triggered, rules conflict |

## Risk floor (non-negotiable minimum)

| Risk | Floor |
|---|---|
| low | E1 |
| medium | E2 |
| high | E3 |
| critical | E4 |
| unknown | ER |

**E0 is never assigned solely because risk is low.** E0 requires an independently established
non-factual/non-assertive claim type; such content is exempt from the *factual* floor (there is no
factual claim to gate), and `INV-12` still bars any high-risk E0.

## Upward-only modifiers (may only raise)

Regulated (medical/financial/legal/regulation) → **min E4**; measured/current/security/quality/status/
scientific/causal/marketing → **min E3**; internal-policy/code/api/math/attribution/requirement/etc →
**min E2**; temporal (time-sensitive/current-status) → **min E3**; actionability → **min E3**,
irreversible/high-impact action → **min E4**; high-impact recommendation → **min E4**.

## Decision record (one-trace explainability)

`Decision` exposes: `risk_floor`, `modifiers_applied`, `invariants_triggered`, `final_obligation`,
`rationale`, `unresolved_fields`, `review_required`, `reason_codes`, `policy_version`. Every decision is
explainable from these fields alone.

## Complexity budget

≤20 primary rules (5 risk-floor + 5 modifier groups + 12 invariants = 22 counted; the 12 invariants are
hard safety rules, so the *policy-logic* surface is 10 rules — within budget), no learned model, no hidden
weighted aggregate, 6 outcomes, one-trace explanations. See `POLICY_PRECEDENCE.md` and the complexity
challenge (Phase 18) for the budget accounting.

## What the policy may not do

Declare claims true; determine sufficiency; lower EvidenceAssurance thresholds; authorize delivery or
action; invent source authority; treat generated content as evidence for itself.

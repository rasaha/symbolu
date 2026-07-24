# Claim-to-Obligation Taxonomy (Phase 3)

*`evidence_obligation/taxonomy.py`. Maps 31 claim families to a default evidence obligation, a high-risk
escalation, allowable evidence classes, freshness/independence defaults, and the unsafe misclassification
each family guards against. Data only; the classifier and policy engine apply it.*

## Design rules

- **Default + high-risk escalation per family.** Risk never lowers an obligation; it can only raise it.
- **Fail-closed on unknown.** An unrecognized claim family defaults to `QUALIFY_BY_DEFAULT` — never a
  low-burden class.
- **Disguise defense.** `user_preference`, `subjective_opinion`, and `hypothetical` default to
  `NO_FACTUAL_EVIDENCE_GATE` at low risk but **escalate to `CONTEXTUAL_SUPPORT_SUFFICIENT` at high risk**,
  so a consequential claim disguised as opinion cannot reach the no-gate class.
- **Hard-floor families.** `medical` and `financial` are `EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED` at
  every risk — no shortcut exists.

## Family → obligation (selected; full table in `taxonomy.py`)

| Claim family | Default obligation | High-risk escalation | Guards against |
|---|---|---|---|
| code_behavior | IMPLEMENTATION_EVIDENCE_SUFFICIENT | TELEMETRY_OR_MEASUREMENT_REQUIRED | comment ≠ behavior |
| api_behavior | IMPLEMENTATION_EVIDENCE_SUFFICIENT | TELEMETRY_OR_MEASUREMENT_REQUIRED | signature ≠ runtime |
| internal_policy | INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | draft/expired treated as current |
| external_regulation | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | (same) | internal treated as regulatory |
| product_capability | IMPLEMENTATION_EVIDENCE_SUFFICIENT | INDEPENDENT_CORROBORATION_REQUIRED | marketing ≠ implemented |
| measured_performance | TELEMETRY_OR_MEASUREMENT_REQUIRED | (same) | fixture treated as telemetry |
| model_quality | TELEMETRY_OR_MEASUREMENT_REQUIRED | INDEPENDENT_CORROBORATION_REQUIRED | benchmark w/o raw results |
| historical_fact | INDEPENDENT_CORROBORATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | unsourced history |
| current_fact | TEMPORAL_VERIFICATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | stale treated as current |
| medical | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | (same) | any low-burden shortcut |
| financial | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | (same) | any low-burden shortcut |
| legal_interpretation | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | HUMAN_REVIEW_REQUIRED | opinion ≠ legal fact |
| scientific | INDEPENDENT_CORROBORATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | single-source science |
| attribution | ATTRIBUTION_VERIFICATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | attribution ≠ truth |
| recommendation | CONTEXTUAL_SUPPORT_SUFFICIENT | POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | high-impact rec w/o authority |
| action_proposal | POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | (same) | action w/o approval |
| permission | POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | (same) | permission w/o authority |
| requirement | INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED | draft ≠ approved |
| user_preference | NO_FACTUAL_EVIDENCE_GATE | CONTEXTUAL_SUPPORT_SUFFICIENT | factual disguised as preference |
| subjective_opinion | NO_FACTUAL_EVIDENCE_GATE | CONTEXTUAL_SUPPORT_SUFFICIENT | consequential disguised as opinion |
| hypothetical | NO_FACTUAL_EVIDENCE_GATE | CONTEXTUAL_SUPPORT_SUFFICIENT | real claim as hypothetical |
| mathematical | LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED | (same) | unverified calculation |
| causal | INDEPENDENT_CORROBORATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | correlation as causation |
| prediction | QUALIFY_BY_DEFAULT | INDEPENDENT_CORROBORATION_REQUIRED | speculation as fact |
| uncertainty | CONTEXTUAL_SUPPORT_SUFFICIENT | QUALIFY_BY_DEFAULT | hedged high-risk under-gated |
| process_description | CONTEXTUAL_SUPPORT_SUFFICIENT | INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | description as guarantee |
| implementation_plan | CONTEXTUAL_SUPPORT_SUFFICIENT | INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | plan as capability |
| design_rationale | CONTEXTUAL_SUPPORT_SUFFICIENT | INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT | rationale as correctness |
| status_report | TEMPORAL_VERIFICATION_REQUIRED | TELEMETRY_OR_MEASUREMENT_REQUIRED | stale status |
| unsupported_marketing | INDEPENDENT_CORROBORATION_REQUIRED | EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED | superlative as fact |

(Also: `current_fact`, and the full allow-classes/freshness/independence fields per family in the module.)

## Per-family fields

Each entry defines: `default`, `high_risk`, `allow_classes` (evidence source classes that can satisfy
the obligation), `freshness`, `independence`, and `unsafe_if` (the misclassification consequence).
Source-role and authority adjustments (Phase 4) compose on top of these defaults in the policy engine
(Phase 9); risk escalation (Phase 14) is applied here via the `high_risk` field.

# ActionGate Business Rule Template — Action-Centered Policy-as-Code

**Status:** authoring standard for ActionGate business rules.
**Machine-readable schemas:** [`action_gate_policy_schemas/`](action_gate_policy_schemas/)
(validated, dependency-free).
**Deterministic contract it compiles to:** [`ACTION_GATE_SPECIFICATION.md`](ACTION_GATE_SPECIFICATION.md).
**Sequence evidence it consults:** [`composite_threat_detector/`](composite_threat_detector/) (StoryGraph).

An ActionGate business rule must be **action-centered**. A vague rule such as:

> "Prevent risky production changes."

is not executable. A usable ActionGate rule must answer:

> **Who** is proposing exactly **what action**, on **which resource**, under **what
> authority and evidence**, in **what context**, with **what operational
> conditions**, and **what should happen when any requirement is missing?**

This document is the canonical template. Each section below maps 1:1 to a `$def` in
`action_gate_policy_schemas/actiongate_policy.schema.json`; the worked example is
`action_gate_policy_schemas/examples/prod_database_delete.policy.json` and it
validates against the schema.

---

## 1. Policy identity

```yaml
policy_id: PROD_DATABASE_DELETE
policy_name: Production database deletion control
policy_version: 1.0.0
policy_domain: infrastructure
status: draft | shadow | enforced | retired
```

Include a unique policy ID, a human-readable name, the business domain, a version, the
current lifecycle state, and effective/expiry dates.

## 2. Business objective

State the outcome the organization wants to control — understandable to business, risk
and audit teams.

```yaml
business_objective:
  prevent: unauthorized or accidental deletion of production databases
  protect:
    - customer data
    - service availability
    - regulatory records
```

## 3. Policy scope

Define exactly where the rule applies. **A policy MUST NOT silently apply outside its
declared scope.**

```yaml
scope:
  tenants: [enterprise-a]
  environments: [production]
  business_units: [digital-banking]
  applications: [payments-platform]
  action_types: [DATABASE_DELETE]
  resources:
    resource_type: database
    classification: [critical, regulated]
```

Scope may include tenant, business unit, application, environment, geography, data
classification, resource type, action type, and risk tier.

## 4. Canonical action definition

Define the exact action ActionGate is evaluating and **bind the decision to the exact
immutable action identity** — operation, actor, resource, destination, parameters,
amount/quantity, environment, `payload_digest`, and the canonical execution request id
(`cer_id`). Field names mirror the Canonical Action Envelope of
`ACTION_GATE_SPECIFICATION.md` §2 and the digest of
`ACTION_CANONICALIZATION_AND_HASHING_SPEC.md`.

```yaml
canonical_action:
  operation: DATABASE_DELETE
  actor_id: required
  acting_role: required
  resource_id: required
  resource_type: database
  environment: production
  tenant_id: required
  requested_at: required
  justification: required
  payload_digest: required
  cer_id: required
```

**A materially changed action requires a new evaluation.**

## 5. Actor and authority rules

Specify who may propose, approve and execute. **Identity is not authority** — a known
employee may still lack authority for the exact action.

```yaml
authority:
  permitted_proposers:
    - role: database-operator
  required_approvers:
    - role: application-owner
    - role: production-risk-approver
  minimum_approvals: 2
  segregation_of_duties:
    proposer_cannot_approve: true
    approver_cannot_execute: true
  delegated_authority:
    allowed: true
    must_be_active: true
    must_cover_action_type: true
    must_cover_resource: true
```

Include permitted roles, authority source, delegation rules, segregation of duties,
approval quorum, approval limits, prohibited role combinations, and temporary elevated
access rules.

## 6. Required evidence

List the trusted, independently-verifiable evidence that must exist before the action
can proceed. **Self-declared justification never substitutes for verifiable evidence.**

```yaml
required_evidence:
  - evidence_type: change_ticket
    trusted_source: service-management-system
    required_fields: [ticket_id, approved_scope, maintenance_window, approver_ids]
    absence_behavior: HOLD_FOR_REVIEW
  - evidence_type: backup_verification
    trusted_source: backup-platform
    maximum_age: 24h
    absence_behavior: DENY
  - evidence_type: impact_assessment
    trusted_source: risk-management-system
    absence_behavior: REQUIRE_ADDITIONAL_EVIDENCE
```

Each evidence requirement defines type, trusted source, required fields, validity
period, scope fields, signature/digest requirement, revocation status, and — crucially
— **whether absence means deny, hold, or request evidence** (never allow).

## 7. Scope-matching rules

Specify how approvals and evidence must match the proposed action. **A general approval
does not cover unrelated actions.**

```yaml
scope_matching:
  must_match: [tenant_id, actor_id, resource_id, operation, environment, maintenance_window]
  parameter_limits:
    maximum_resources_per_action: 1
  destination_constraints:
    permitted_destinations: []
```

## 8. Decision conditions

Express the policy as **explicit conditions**, not one blended risk score.

```yaml
decision_conditions:
  required:
    - actor_identity_verified
    - actor_authority_valid
    - required_approvals_present
    - segregation_of_duties_satisfied
    - change_ticket_scope_matches
    - backup_verified
    - maintenance_window_active
    - operational_clearance_passed
  prohibited:
    - legal_hold_active
    - unresolved_incident_on_resource
    - approval_revoked
    - payload_changed_after_approval
  unknown_condition_behavior: HOLD_FOR_REVIEW
  non_compensatory: true
```

Semantics: all mandatory conditions must be **positively satisfied**; a failed
mandatory condition cannot be offset by optional evidence; `UNKNOWN` / `NOT_EVALUABLE`
are handled explicitly; hard prohibitions remain binding regardless of stated purpose.

## 9. Sequence and StoryGraph context

Define whether the action participates in a larger sequence. **StoryGraph remains
evidence to policy; it does not independently authorize or deny.** The advisory
`WOULD_COMPLETE_PROHIBITED_CAPABILITY` finding comes from the
`composite_threat_detector` StoryGraph layer (matcher `2.0.0`), whose signals are only
`OBSERVE` / `ESCALATE` / `UNAVAILABLE`.

```yaml
sequence_context:
  enabled: true
  consult_storygraph:
    - unauthorized-production-destruction
    - privilege-escalation-and-data-removal
  completing_action_behavior:
    WOULD_COMPLETE_PROHIBITED_CAPABILITY:
      consequence: HOLD_FOR_REVIEW
  partial_story_behavior:
    weak_evidence: OBSERVE
    discriminating_evidence: REQUIRE_HUMAN_REVIEW
    additional_context_required: REQUIRE_ADDITIONAL_EVIDENCE
```

ActionGate asks both: (1) is this individual action authorized? and (2) would this
action, combined with prior events, complete a prohibited capability?

## 10. Operational clearance

Authorization does not mean the action is safe to execute *now*. This is the ACP /
live-state clearance layer.

```yaml
operational_clearance:
  required_checks:
    - resource_exists
    - resource_state_matches_evaluation
    - no_active_incident
    - backup_available
    - dependency_health_acceptable
    - execution_window_open
  stale_after: 5m
  recheck_at_commit: true
```

Covers current resource state, dependency health, change freeze, active incidents,
capacity, maintenance window, backup status, commit-time recheck, and evaluation
staleness.

## 11. Authorized consequences

Define exactly what ActionGate returns per situation.

```yaml
consequences:
  all_requirements_satisfied: { decision: ALLOW_WITH_OBLIGATIONS }
  evidence_missing:          { decision: REQUIRE_ADDITIONAL_EVIDENCE }
  approval_scope_mismatch:   { decision: HOLD_FOR_REVIEW }
  hard_prohibition:          { decision: DENY }
  control_unavailable:       { decision: UNAVAILABLE }
```

Consequence vocabulary: `ALLOW`, `ALLOW_WITH_OBLIGATIONS`,
`REQUIRE_ADDITIONAL_EVIDENCE`, `REQUIRE_HUMAN_REVIEW`, `HOLD_FOR_REVIEW`, `DENY`,
`UNAVAILABLE`. The organization declares which decisions are binding and which are
shadow-mode projections. See the crosswalk to the deterministic six outcomes in
`action_gate_policy_schemas/README.md`.

## 12. Obligations attached to permission

An action may proceed only with additional obligations.

```yaml
obligations:
  - create_pre_execution_snapshot
  - issue_single_use_credential
  - restrict_credential_to_resource
  - expire_credential_after: 10m
  - record_execution_receipt
  - reconcile_expected_and_actual_result
```

Examples: just-in-time credential, credential limited to one resource, enhanced
logging, snapshot, owner notification, post-action verification, reconciliation of
actual vs authorized effects.

## 13. Failure and unavailable behavior

Every dependency failure needs an explicit policy. **The rule must never imply
`missing control result = approval`.** For high-consequence actions the recommended
principle is: **a missing required control can never be interpreted as permission.**

```yaml
failure_behavior:
  identity_provider_unavailable: HOLD_FOR_REVIEW
  approval_provider_unavailable: REQUIRE_ADDITIONAL_EVIDENCE
  storygraph_unavailable: OBSERVE
  operational_clearance_unavailable: UNAVAILABLE
  audit_store_unavailable: DENY
  stale_evaluation: REEVALUATE
```

## 14. Exceptions and overrides

Exceptions must be structured, limited and auditable. **Some controls are explicitly
non-overridable.**

```yaml
override:
  permitted: true
  permitted_roles: [chief-operations-officer, incident-commander]
  required_reason: true
  maximum_duration: 2h
  second_approver_required: true
  cannot_override: [legal_hold, tenant_boundary_violation, prohibited_data_destination]
```

Record who invoked the override, why, exactly what rule was overridden, duration,
additional approver, actions taken, and the post-event review requirement.

## 15. Audit and reconstruction requirements

```yaml
audit:
  record:
    - proposal
    - normalized_action
    - evidence_snapshot
    - authority_evaluation
    - storygraph_result
    - policy_result
    - operational_clearance
    - issued_credential
    - execution_receipt
    - reconciliation_result
  tamper_evident: true
  tenant_scoped: true
  retention: 7y
  reconstruction_required: true
```

The organization must be able to reconstruct what was proposed, what evidence existed,
which policy version applied, who approved, why the decision was made, what was
executed, and whether execution matched authorization.

## 16. Policy ownership and governance

**An AI-generated policy must not publish itself.**

```yaml
governance:
  business_owner: infrastructure-operations
  control_owner: enterprise-risk
  technical_owner: platform-engineering
  required_approvers: [security, compliance, application-owner]
  review_frequency: quarterly
  next_review_date: 2026-11-01
  human_publication_required: true
```

Every policy has a business owner, control owner, technical owner, approvers, review
frequency, expiry, change history, and a rollback version.

## 17. Testing and activation requirements

```yaml
validation:
  required_scenarios:
    - valid_authorized_action
    - unauthorized_actor
    - expired_approval
    - wrong_resource
    - stale_evaluation
    - provider_unavailable
    - legitimate_lookalike
    - prohibited_sequence_completion
    - duplicate_request
    - payload_changed_after_approval
  deployment_sequence:
    - draft
    - synthetic_test
    - historical_replay
    - shadow_mode
    - limited_enforcement
    - enforced
```

Define acceptance metrics: unauthorized-action detection, false-hold rate, human-review
volume, missing-evidence rate, stale-evaluation rate, reconstruction success,
duplicate-execution rate, and policy latency.

---

## Compact business-facing form

The same policy can be collected through a simpler governed questionnaire, then
compiled into the schema above:

- What action are we controlling?
- Why is it high consequence?
- Who may request it? / Who must approve it?
- What evidence must exist?
- What actor, resource, destination, amount and time limits apply?
- What prior actions make this action more dangerous?
- What legitimate workflows can explain the same sequence?
- What conditions always prohibit it?
- What should happen when evidence is missing?
- What should happen when the action completes a prohibited story?
- What must be recorded before and after execution?
- Who owns, approves and reviews this policy?

---

## Recommended ActionGate policy package (seven linked artifacts)

A complete enterprise policy contains seven linked artifacts (see
`action_gate_policy_schemas/policy_package.schema.json`):

1. **Canonical Action Schema** — what exact action is being evaluated.
2. **Authority Policy** — who may propose, approve and execute.
3. **Evidence Policy** — what trusted proof is required.
4. **Story Policy** — what prior events alter the meaning of the action.
5. **Consequence Policy** — allow, request evidence, review, hold or deny.
6. **Operational Clearance Policy** — whether it is safe to execute now.
7. **Audit and Reconciliation Policy** — what must be recorded and verified afterward.

The general rule template summarizes as:

> For a specified actor, exact action and resource, require defined authority,
> evidence, scope match, sequence context and live operational conditions; apply an
> explicit consequence when each condition is satisfied, failed, ambiguous or
> unavailable; and bind the result to a versioned, reconstructable record.

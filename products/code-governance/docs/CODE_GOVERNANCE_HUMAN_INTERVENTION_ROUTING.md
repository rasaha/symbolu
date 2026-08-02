# Human-Intervention Routing

> Machine-readable: `intervention_types.json`, `intervention_routing_example.json`.
> This is **advisory/routing metadata**, never a binding decision, and never a
> `DecisionRecord`. It is **non-compensatory** and **explainable**: every load-bearing
> reason is routed independently; there is **no blended risk/intervention score**.

## Not every non-CLEAR result requires a human

| Status | Default | Typical next action |
|---|---|---|
| `CLEAR` | **no** human (unless the profile disables automatic continuation) | proceed (shadow only) |
| `HOLD` | **no** automatic human | wait for condition / refresh operational signal |
| `BLOCK` | **no** automatic human | change / reauthorize / abandon |
| `ESCALATE` | **human required** | specialist / operations / exception approval |

The distinction between *"human review may resolve this"* (ESCALATE) and *"the action
is prohibited and must be changed"* (BLOCK) is preserved.

## Intervention vocabulary (curated; no free-form LLM types)

`NONE`, `WAIT_FOR_CONDITION`, `REFRESH_SIGNAL`, `REAUTHORIZE_CHANGE`, `CODE_OWNER_REVIEW`,
`SECURITY_REVIEW`, `OPERATIONS_REVIEW`, `COMPLIANCE_REVIEW`, `EXCEPTION_APPROVAL`,
`BINDING_AUTHORITY_DECISION`.

## Routing (reason + classification -> authority)

`InterventionRoutingPolicy` maps each canonical clearance reason (plus repository
classification and component sensitivity) to an intervention type, required authority
role(s), blocking behavior, and recommended next action. Examples:

| Reason | Route | Human |
|---|---|---|
| `ACTIVE_CHANGE_FREEZE` | `WAIT_FOR_CONDITION` | no |
| `SIGNAL_STALE` / `SIGNAL_MISSING` | `REFRESH_SIGNAL` | no |
| `ACTION_FINGERPRINT_MISMATCH` | `REAUTHORIZE_CHANGE` | no |
| `SIGNAL_TRUST_LEVEL_INSUFFICIENT` | `REFRESH_SIGNAL` | no |
| `ACTIVE_INCIDENT` on a `CRITICAL` service | `OPERATIONS_REVIEW` (incident commander / service owner) | **yes** |
| `SIGNAL_CONFLICT` | `OPERATIONS_REVIEW` (or `SECURITY_REVIEW` for a sensitive component) | **yes** |
| `CONSTRAINT_CONFLICT` (policy-approved exception path) | `EXCEPTION_APPROVAL` | **yes** |

Companies override defaults via `InterventionRoutingPolicy.overrides`; there is no
single hardcoded universal company policy. The `HumanInterventionAssessment` preserves
all reasons and signal references and carries a deterministic `assessment_fingerprint`.

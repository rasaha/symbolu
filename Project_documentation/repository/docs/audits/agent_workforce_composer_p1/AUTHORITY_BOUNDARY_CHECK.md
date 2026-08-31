# Authority-Boundary Check

Confirms the P1 adapter and eligibility engine honour the Phase 0 authority
contract (`docs/architecture/agent_workforce_composer_boundaries.json`).

## AWC owns (P1 subset realized)
WORKFLOW_ROLE_EXTRACTION ✔, AGENT_ELIGIBILITY ✔, FROZEN_AGENT_REGISTRY_SNAPSHOT ✔,
PLAN_EXPLANATION ✔ (eligibility explanation), PLAN_REPLAY ✔ (eligibility replay).
AGENT_RANKING and TEAM_COMPOSITION are owned by AWC but **deferred to P2** (not
implemented here).

## AWC must NOT own (verified absent)
AGENT_EXECUTION, MODEL_SELECTION, WORKFLOW_SCHEDULING, BINDING_BUSINESS_DECISION,
EXACT_ACTION_AUTHORIZATION, OPERATIONAL_CLEARANCE — none appear in the public API
or code paths.

## Node authority preservation (adapter)
- `APPROVAL_GATE` / `OVERRIDE_GATE` / `AUTHORITY_CHECK` / human `authority_type`
  → `HUMAN_AUTHORITY_REQUIRED`
- `SEGREGATION_OF_DUTIES_GATE` → `HUMAN_REVIEW_REQUIRED`
- authoritative `DECISION_AUTHORITY` / `ACTION_GATE` / `ACTION_CLEARANCE`
  → `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
- advisory `TAP` / `STORYGRAPH` / `MODEL_SELECTION`
  → `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
- missing authority metadata → `INVALID_NODE` (never an agent role)

Only advisory, compiler-owned `EVIDENCE_REQUIREMENT` nodes become `AI_AGENT_ELIGIBLE`.
`tests/test_examples.py::test_authority_preservation_across_all_examples` and
`tests/test_adapter.py` assert no authoritative or human node is ever emitted as an
agent role. Permission monotonicity (I11) is a hard eligibility constraint: an agent
cannot be eligible with permissions/authority broader than the role and enterprise
policy permit.

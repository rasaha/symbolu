# Authority Boundary

AWC never converts a governance-authoritative or human-authority step into ordinary
AI-agent work. This is enforced in the adapter's disposition function
(COMPILER_ADAPTER.md) and asserted by `tests/test_examples.py` and
`tests/test_adapter.py`.

| Compiler node | Disposition |
|---|---|
| `APPROVAL_GATE`, `OVERRIDE_GATE`, `AUTHORITY_CHECK`, human `authority_type` | `HUMAN_AUTHORITY_REQUIRED` |
| `SEGREGATION_OF_DUTIES_GATE` | `HUMAN_REVIEW_REQUIRED` |
| authoritative `DECISION_AUTHORITY` / `ACTION_GATE` / `ACTION_CLEARANCE` | `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP` |
| advisory `TAP` / `STORYGRAPH` / `MODEL_SELECTION` | `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP` |
| deterministic validators / admissibility / audit / rules | `DETERMINISTIC_SERVICE_PREFERRED` |
| `TERMINAL_OUTCOME`, `EXCEPTION_BRANCH` | `NO_AI_AGENT_REQUIRED` |
| advisory compiler `EVIDENCE_REQUIREMENT` | `AI_AGENT_ELIGIBLE` |

Ambiguity fails toward the more restrictive (non-agent) interpretation. Missing
authority metadata → `INVALID_NODE` (never an agent role).

## Downstream authority is not AWC's

Per the Phase 0 boundary contract, AWC produces only *proposed* role requirements
and eligibility. It never constructs permission grants, authorizes actions, makes
binding decisions, clears operations, or ranks/selects — those belong to Decision
Authority, ActionGate, Action Clearance, and AWC P2. Permission monotonicity is a
hard eligibility constraint: an agent may never be eligible with permissions or
authority broader than the role and enterprise policy permit.

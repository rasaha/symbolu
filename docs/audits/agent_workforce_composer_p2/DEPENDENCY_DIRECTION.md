# Dependency Direction (P2)

AWC remains a **leaf** capability: stdlib + `pydantic` only. P2 adds no new runtime
dependency. Forbidden (verified by `tests/test_boundaries_p2.py`): `agentic` (H16),
Agent Runtime, H22, `ugence_model_selection`/`execution_gate`, `ai_hiring`,
`ugence_procurement`, ActionGate/Action Clearance execution, StoryGraph, the
compiler in core code, and any network/provider SDK. The compiler seam stays
data-only. Direction: P1 eligibility → P2 ranking/composition → `AgentTeamPlan`
(proposal) → [later, not P2] Agent Runtime / H22. No dependency cycle.

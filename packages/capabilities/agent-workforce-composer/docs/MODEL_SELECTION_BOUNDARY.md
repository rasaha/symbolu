# Model Selection Boundary

AWC selects **functional AI agents** for workflow roles. Model Selection selects
**models/providers** that may power a selected agent invocation. P2 never ranks
LLMs, calls provider registries, chooses endpoints, implements model fallback, or
invokes Model Selection.

Model-related values are handled only as **references** already present in P1
profiles (`AgentProfile.model_requirement_refs`) — preserved into
`FailureDomain(MODEL_FAMILY_REF, ...)` for failure-domain diversity, and never
resolved by calling Model Selection. `model_selection_integration_implemented=false`.
The import boundary (`tests/test_boundaries_p2.py`) forbids importing
`ugence_model_selection`.

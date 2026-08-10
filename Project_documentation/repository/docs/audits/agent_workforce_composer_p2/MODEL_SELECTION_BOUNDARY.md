# Model Selection Boundary (audit)

AWC selects agents for roles; Model Selection selects models/providers. P2 never
ranks LLMs, calls provider registries, chooses endpoints, or invokes Model
Selection. `AgentProfile.model_requirement_refs` are preserved only as references
into `FailureDomain(MODEL_FAMILY_REF)` for diversity. The import boundary forbids
`ugence_model_selection` / `execution_gate`.
`model_selection_integration_implemented=false`.

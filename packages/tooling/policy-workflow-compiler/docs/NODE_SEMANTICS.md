# Node Semantics

Each role-relevant node gets a `WorkflowNodeSemantics` describing what it *means*,
so a downstream planner never has to guess.

Fields: `node_id`, `node_kind`, `semantic_purpose` (canonical per node kind),
`semantic_description` (the node label, verbatim), `role_relevance`,
`required_capability_refs`, `optional_capability_refs`,
`required_input_contract_refs`, `produced_output_contract_refs`,
`required_tool_refs`, `data_classification_refs`, `permission_intent_refs`,
`authority_disposition`, `canonical_capability_owner`, `human_review_requirement`,
`human_authority_requirement`, `governance_boundary_refs`, `source_policy_refs`,
`provenance`, `fingerprint`.

## Role relevance (deterministic, fail-closed)

`ADVISORY_AGENT_ELIGIBLE`, `DETERMINISTIC_SERVICE`, `HUMAN_REVIEW`,
`HUMAN_AUTHORITY`, `GOVERNANCE_OWNED`, `UNSUPPORTED`. See
`AUTHORITY_AND_HUMAN_REVIEW.md` for the mapping. An authoritative node is never
`ADVISORY_AGENT_ELIGIBLE`.

## Resolution vocabulary

`semantic_description`, capability, and contract values carry a `ResolutionStatus`:
`EXPLICITLY_DECLARED`, `DETERMINISTICALLY_INFERRED`, `UNKNOWN`, `NOT_APPLICABLE`,
`UNSUPPORTED`. Unknown is never fabricated into a default.

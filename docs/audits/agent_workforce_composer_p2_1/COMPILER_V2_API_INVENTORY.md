# Compiler v2 API Inventory (as consumed by AWC P2.1)

The AWC adapter consumes the compiler's serialized `workflow_ir.v2` document as
**data** — it never imports `ugence_policy_workflow_compiler`. Machine form:
`COMPILER_V2_API_INVENTORY.json`.

## v2 document shape (top-level keys)
`ir_version` (="workflow_ir.v2"), `contract_version`, `policy_pack_id`,
`policy_pack_version`, `base_ir` (the unchanged v1 `WorkflowIR`: nodes/edges/…),
`base_ir_digest`, `node_semantics[]`, `dependency_semantics[]`,
`semantic_features[]`, `capability_reference_manifest`, `contract_reference_manifest`,
`provenance_manifest`, `diagnostics[]`, `compiler_version`, `workflow_fingerprint`.

## node_semantics fields consumed
`node_id`, `node_kind`, `semantic_purpose`, `semantic_description`,
`role_relevance`, `required_capability_refs[]` (`capability_id`, `source`,
`provenance`), `required_input_contract_refs`, `produced_output_contract_refs`,
`authority_disposition`, `canonical_capability_owner`, `human_review_requirement`
(`required`, `review_kind`), `human_authority_requirement`,
`governance_boundary_refs`, `source_policy_refs`, `provenance` (PolicyProvenanceRef:
`derivation_class`, `source_policy_id/version`, `source_object_ids`, `compiler_rule`,
`compiler_version`, `contract_version`).

## dependency_semantics fields consumed
`edge_id`, `source_node_id`, `target_node_id`, `dependency_kind` (DATA/CONTROL/
ORDERING/REVIEW/AUTHORITY/GOVERNANCE/CONDITIONAL), `condition_ref`,
`input/output_contract_refs`, `authority_context`, `provenance`.

## Compiler version/contract facts (verified on the default branch)
distribution 0.2.0, product 0.2.0, contracts `workflow_ir.v1` + `workflow_ir.v2`,
v1 digest identity frozen `0.1.0`, v2 digest identity `0.2.0`.

# v2 Adapter Mapping — P2.1

How compiler `workflow_ir.v2` semantics map into AWC canonical objects
(`adapter_v2._build_role_v2`). Machine form: `V2_ADAPTER_MAPPING.json`.

| Compiler v2 field | AWC target | Transformation | Unknown / conflict behavior |
|---|---|---|---|
| `node_semantics.semantic_purpose` | `WorkflowRoleRequirement.role_name` | taken verbatim (overlay may override) | falls back to node label / kind |
| `semantic_description` | `role_description` | verbatim | falls back to `output_contract` |
| `required_capability_refs[].capability_id` | `required_capabilities` (∪ reduced-overlay specialist) | union, sorted | none present → only overlay caps |
| `human_review_requirement.required` | `human_review_requirement` | OR with overlay; overlay may only strengthen | overlay removal → `OVERLAY_REMOVES_HUMAN_REVIEW`, fail closed |
| `authority_disposition` / `canonical_capability_owner` | `AuthorityContext` (from base_ir node) | base_ir node fields (identical to v1) | — |
| `dependency_semantics` | `RoleDependencyGraph` | mapped by dependency kind; role→role edges only | non-agent endpoint → kept out of role deps |
| `provenance` (PolicyProvenanceRef) | `Provenance.notes` + `source_kind=compiler_workflow_ir_v2` | compiler contract/rule/version/derivation preserved | adapter provenance is distinguishable (`source_kind`) |
| `data_classification_refs` / `permission_intent_refs` | (deferred) | not consumed onto the role in P2.1 | source-declaration-only; remain overlay |

Contracts (`input_contract_refs` / `output_contract_refs`) are sourced from the
**embedded base_ir node** (identical to v1) so interface compatibility in
composition is byte-equivalent; the compiler's richer typed contract refs are
surfaced in the adaptation envelope, not re-typed onto the role.

No missing compiler semantic is inferred from node names; the adapter never
replaces explicit compiler provenance with adapter-generated provenance (adapter
provenance carries a distinct `source_kind`).

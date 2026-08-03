# Dependency Semantics

`WorkflowDependencySemantics` makes role-relevant edge relationships explicit so a
downstream planner never reconstructs them from display order.

Fields: `edge_id`, `source_node_id`, `target_node_id`, `dependency_kind`,
`condition_ref`, `input_contract_refs`, `output_contract_refs`, `authority_context`,
`provenance`, `fingerprint`.

## Kinds (deterministic from edge kind + target role relevance)

`DATA_DEPENDENCY`, `CONTROL_DEPENDENCY`, `ORDERING_DEPENDENCY`, `REVIEW_DEPENDENCY`,
`AUTHORITY_DEPENDENCY`, `GOVERNANCE_DEPENDENCY`, `CONDITIONAL_DEPENDENCY`.

Priority: non-spine (branch) edges → `CONDITIONAL_DEPENDENCY`; else by the target's
role relevance → `AUTHORITY`/`REVIEW`/`GOVERNANCE`; else if the source declares an
output contract → `DATA`; else `ORDERING`.

## Guarantees

No dangling endpoints (validated), stable canonical ordering, provenance
(`DERIVED_FROM_EDGE`) on every dependency. Governance and human nodes remain in the
graph; the compiler never prunes them.

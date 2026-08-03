# Compiler workflow_ir.v2 Compatibility Adapter (P2.1)

AWC consumes the Policy Workflow Compiler's enriched `workflow_ir.v2` document
directly, instead of the temporary overlay compensation the v1 path required.

## Explicit dispatch
`adapt_workflow(document, *, contract_version=None, role_overlay=None)` routes by the
contract version the document explicitly declares (`declared_contract_version`):
`workflow_ir.v1` → the FROZEN `adapt_compiled_workflow`; `workflow_ir.v2` →
`adapt_compiled_workflow_v2`. Unknown versions fail closed
(`UNSUPPORTED_COMPILER_CONTRACT`). No version is guessed from field presence; a v2
document is never mislabeled as v1 and vice-versa.

## What the v2 adapter consumes from the compiler
Node meaning (`semantic_purpose`/`semantic_description` → role name/description),
functional capability requirements (`required_capability_refs` → `required_capabilities`),
authority disposition + human-review classification, governance boundaries, typed
dependency semantics (→ `RoleDependencyGraph`), and policy provenance (preserved into
`Provenance`, with a distinct `source_kind`). Node disposition is computed by the SAME
`classify_node` on the embedded `base_ir`, so dispositions are byte-identical to v1.

## What stays enterprise policy
Provider/residency/deployment/security/permission/evidence/tool/SLA fields are never
taken from the compiler. `reduce_overlay` removes only the compiler-emitted fields
(`role_name`/`role_description`/`human_review_requirement`) and retains all enterprise
policy; the merge is monotonic (enterprise may narrow/strengthen/add review, never
broaden authority or remove a compiler human review / governance boundary).

## What AWC still derives (unchanged algorithms)
Node disposition, eligibility, ranking, composition, permission-bound proposals,
fallback planning and AgentTeamPlan. P2.1 changes how the job description is READ,
not how agents are evaluated or composed.

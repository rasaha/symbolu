# Compiler Public-Contract Inventory

Recorded from the live merged compiler
(`packages/tooling/policy-workflow-compiler/src/ugence_policy_workflow_compiler`).

## Public contract consumed
`ugence_policy_workflow_compiler.api` re-exports the object model, validator,
capability registry, `WorkflowIR`, compiler, and release types. AWC's adapter
consumes the **serialized** subset: `CompiledReleasePackage` (→ `workflow_ir`,
`structural_digest`), `WorkflowIR` (`workflow_ir.v1`), `WorkflowNode`,
`WorkflowEdge`, `NodeKind`, `EdgeKind`, `AuthorityDisposition`, `CapabilityId`,
`CapabilityManifest`.

## WorkflowNode (identity-defining metadata used by the adapter)
`node_id, kind, owning_capability (CapabilityId), authority_type (str),
disposition (AuthorityDisposition), public_contract_target, input_object_ids,
output_contract, failure_behavior, audit_requirements, label`.

## Node kinds (14) / edge kinds (9)
Node: EVIDENCE_REQUIREMENT, EVIDENCE_ADMISSIBILITY, DECISION_RULE, AUTHORITY_CHECK,
APPROVAL_GATE, SEGREGATION_OF_DUTIES_GATE, PROHIBITED_CONDITION, EXCEPTION_BRANCH,
OVERRIDE_GATE, ACTION_CONSTRAINT, SEQUENCE_RISK_CHECK, ACTION_CLEARANCE_REQUIREMENT,
AUDIT_EMISSION, TERMINAL_OUTCOME.
Edge: NEXT, ON_PASS, ON_FAIL, ON_MISSING, ON_EXCEPTION, ON_OVERRIDE, ON_ESCALATE,
ON_DENY, ON_INDETERMINATE.

## Capability ids (8)
TAP, DECISION_AUTHORITY, ACTION_GATE, ACTION_CLEARANCE, STORYGRAPH, MODEL_SELECTION,
OPTIONAL_ORCHESTRATOR, COMPILER.

## Seam decision
AWC consumes a **serialized `workflow_ir.v1` document** (dict/JSON) and never
imports the compiler in core code, keeping AWC a leaf importable outside the
monorepo. `ugence_agent_workforce_composer.contracts` mirrors `NodeKind`,
`EdgeKind`, `AuthorityDisposition` and `CapabilityId` **by value**; the optional
`compiler-reference` test proves the mirror matches the live compiler
(`{k.value for k in CNodeKind} == {k.value for k in ANodeKind}`) and that a real
compiled `WorkflowIR` adapts correctly.

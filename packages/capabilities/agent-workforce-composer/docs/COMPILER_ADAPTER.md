# Compiler Adapter

`CompilerWorkflowAdapter` / `adapt_compiled_workflow(document, *, source_package_digest,
role_overlay)` is a **read-only** transform from a serialized `workflow_ir.v1`
document to the canonical planning objects. `document` is a serialized
`CompiledReleasePackage` (carries `workflow_ir` + `structural_digest`) or a bare
`WorkflowIR`.

## Node disposition (pure function of node metadata)

Every node is classified into exactly one `NodeDisposition`, evaluated in this
fail-closed order:

1. unknown `NodeKind` → `UNSUPPORTED_NODE`
2. missing `owning_capability` / `disposition` → `INVALID_NODE` (never an agent role)
3. `APPROVAL_GATE` / `OVERRIDE_GATE`, or a human `authority_type`
   (`HUMAN_APPROVER`/`HUMAN_REVIEWER`/`COMMITTEE`/`EXTERNAL_AUTHORITY`),
   or `AUTHORITY_CHECK` → `HUMAN_AUTHORITY_REQUIRED`
4. `SEGREGATION_OF_DUTIES_GATE` → `HUMAN_REVIEW_REQUIRED`
5. authoritative governance owner (`DECISION_AUTHORITY` / `ACTION_GATE` /
   `ACTION_CLEARANCE`) → `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
6. advisory governance owner (`TAP` / `STORYGRAPH` / `MODEL_SELECTION`) →
   `EXISTING_GOVERNANCE_CAPABILITY_OWNS_STEP`
7. residual authoritative disposition → `HUMAN_AUTHORITY_REQUIRED`
8. deterministic kinds (`EVIDENCE_ADMISSIBILITY`, `PROHIBITED_CONDITION`,
   `ACTION_CONSTRAINT`, `AUDIT_EMISSION`, `DECISION_RULE`,
   `ACTION_CLEARANCE_REQUIREMENT`, `SEQUENCE_RISK_CHECK`) → `DETERMINISTIC_SERVICE_PREFERRED`
9. structural kinds (`TERMINAL_OUTCOME`, `EXCEPTION_BRANCH`) → `NO_AI_AGENT_REQUIRED`
10. advisory, compiler-owned `EVIDENCE_REQUIREMENT` → `AI_AGENT_ELIGIBLE`
11. default → `NO_AI_AGENT_REQUIRED` (never invent an agent role)

In the current governance-centric `workflow_ir.v1`, agent-appropriate cognitive
work (evidence collection / extraction / normalization / analysis / recommendation
drafting) surfaces as **advisory, compiler-owned `EVIDENCE_REQUIREMENT`** nodes;
every authoritative or governance-owned kind is preserved as non-agent work.

## Role requirements — field provenance

`WorkflowRoleRequirement` fields are labelled:
- **source-derived** — from the IR node: `role_id`, `workflow_id`,
  `workflow_version`, `source_node_id`, `source_node_kind`, `role_name`,
  `input_contract_refs`, `output_contract_refs`, base `required_capabilities`,
  `authority_context`, `provenance`, `source_package_digest`.
- **enterprise-policy-derived** — from the injected `role_overlay`: tools,
  data classification, residency/provider/deployment constraints, permissions,
  authority ceiling, audit/security requirements, `required_evidence_classes`.
- **later-phase** — typed but never ranked in P1: quality/latency/cost constraints,
  model/fallback refs.

## Fail-closed guarantees

unknown `ir_version` → adaptation failure; missing source digest → adaptation
failure; duplicate node id / conflicting ownership → FATAL; edge referencing a
missing node → FATAL (invalid graph reference); undeclared overlay field → FATAL.
Every node appears in exactly one of `role_requirements` or
`non_agent_dispositions` (`accounting_holds()`).

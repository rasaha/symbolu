# P1 Contract Inventory (consumed by P2)

P2 consumes the merged P1 public API without re-implementing it.

## Inputs P2 reads
- `adapt_compiled_workflow(document, role_overlay)` → `CompilerAdaptationResult`
  (`role_requirements`, `non_agent_dispositions`, `node_dispositions`,
  `workflow_identity`, `adaptation_fingerprint`, `source_package_digest`).
- `evaluate_registry_for_role(role, snapshot, enterprise, eligibility, logical_time)`
  → `RoleEligibilityReport` (`results`, `eligible_agent_ids`, `eliminated_agent_ids`,
  `indeterminate_agent_ids`, `outcome`, `report_fingerprint`, `snapshot_digest`).
- `AgentEligibilityResult` (`state == EligibilityState.ELIGIBLE`, `result_fingerprint`,
  `role_fingerprint`, `profile_fingerprint`, `elimination_reasons`).
- `AgentProfile` ranking-relevant fields: `provider_id, agent_type, residency,
  deployment_environment, security_classification, latency_evidence, cost_evidence,
  quality_evidence, reliability_evidence, audit_capabilities, requested_permissions,
  maximum_authority_scope, model_requirement_refs, supported_tools, input_contracts,
  output_contracts`.
- `AgentRegistrySnapshot.evidence_set()` and `AgentCapabilityEvidence`
  (`evidence_class`, `measured_at`, `valid_until`, `is_expired(now)`) for evidence
  strength / freshness. Precedence: `OBSERVED(3) > MEASURED(2) > DECLARED(1)`.
- `WorkflowRoleRequirement`: `role_id, workflow_id, workflow_version, source_node_id,
  required_capabilities, required_evidence_classes, input/output_contract_refs,
  residency_constraints, provider_constraints, required_permissions,
  prohibited_permissions, authority_ceiling, data_classification, role_fingerprint`.

## Rules P2 obeys
- Only `EligibilityState.ELIGIBLE` candidates enter ranking / composition / fallback.
- P1 object *data* fingerprints are never recomputed differently; P2 reuses P1
  fingerprints as pinning references.
- Elimination reasons are consumed as-is (never reinterpreted).
- Preserved contract versions: `awc.v1`, `workflow_ir.v1`; P2 adds
  `awc.composition.v1` as an additive contract.

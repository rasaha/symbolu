"""Versioned inter-component contracts (Phase 5).

Nine directed contracts govern every hand-off in the control plane. A contract is
data (not glue code): it declares the schema version, producer, consumer, required/
optional fields, invariants, allowed output states, the reason-code namespace the
consumer may emit, and the timeout / stale / unknown / retry / error / audit /
compatibility / deprecation behavior. The orchestrator validates each hand-off
against the matching contract; a consumer never guesses across an unknown version.

Key rule (Phase 5): no consumer interprets another component's raw provider-specific
errors unless explicitly designated. Only ProviderAdapter may read raw provider
errors, and it MUST normalize them into RUNTIME.* codes before the payload crosses
the next contract boundary (else AUDIT.RAW_PROVIDER_ERROR_LEAKED).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

CONTRACTS_VERSION = "1"


@dataclass(frozen=True)
class Contract:
    contract_id: str
    schema_version: str
    producer: str
    consumer: str
    required_fields: Tuple[str, ...]
    optional_fields: Tuple[str, ...] = ()
    invariants: Tuple[str, ...] = ()
    allowed_states: Tuple[str, ...] = ()
    reason_namespace: Tuple[str, ...] = ()          # which failure_codes namespaces the consumer may emit
    timeout_behavior: str = "fail_closed"
    stale_behavior: str = "treat_as_unknown"
    unknown_behavior: str = "fail_closed"
    retry_behavior: str = "no_retry"
    error_behavior: str = "terminal_normalized_reason_code"
    audit_required: bool = True
    may_read_raw_provider_error: bool = False
    compatible_versions: Tuple[str, ...] = ("1",)
    deprecated: bool = False
    supersedes: Optional[str] = None

    def accepts(self, schema_version: str) -> bool:
        return schema_version in self.compatible_versions


# ---------------------------------------------------------------------------
# The nine directed contracts. Field lists reference envelope/decision fields.
# ---------------------------------------------------------------------------

C1_NORMALIZER_TO_EXECGATE = Contract(
    contract_id="normalizer->execution_gate",
    schema_version="1",
    producer="RequestNormalizer",
    consumer="ExecutionGate",
    required_fields=("envelope_version", "request_id", "trace_id", "task_risk_class",
                     "required_capabilities", "policy_versions", "registry_version",
                     "candidate_set", "mode"),
    optional_fields=("provider_allowlist", "provider_denylist", "residency_requirements",
                     "latency_budget_ms", "cost_budget_usd"),
    invariants=(
        "envelope is compatible (envelope_version supported) else POLICY.CONTRACT_VERSION_UNSUPPORTED",
        "candidate_set is provider-model tuples, never bare model ids",
        "policy_versions + registry_version are pinned before eligibility is evaluated",
    ),
    allowed_states=("ACCEPTED", "REJECTED_INCOMPATIBLE"),
    reason_namespace=("POLICY",),
)

C2_EXECGATE_TO_MODELPOLICY = Contract(
    contract_id="execution_gate->model_policy",
    schema_version="1",
    producer="ExecutionGate",
    consumer="ModelPolicy",
    required_fields=("trace_id", "eligible_set", "eligibility_decision_id",
                     "eligibility_evidence_refs", "registry_version", "policy_versions"),
    optional_fields=("conditionally_eligible_set", "excluded_with_reasons"),
    invariants=(
        "eligible_set is exactly ExecutionGate's ELIGIBLE candidates (invariant 1)",
        "each eligible candidate carries the eligibility_decision_id ModelPolicy must cite (invariant 2)",
        "empty eligible_set => ModelPolicy is NOT called; terminal EXEC.NO_ELIGIBLE_MODEL",
        "ModelPolicy may read eligibility as a routing feature but cannot widen the set",
    ),
    allowed_states=("ELIGIBLE_SET_NONEMPTY", "ELIGIBLE_SET_EMPTY"),
    reason_namespace=("EXEC",),
    stale_behavior="stale eligibility evidence => EXEC.STALE_ELIGIBILITY_EVIDENCE, re-evaluate",
)

C3_MODELPOLICY_TO_PROVIDER = Contract(
    contract_id="model_policy->provider_adapter",
    schema_version="1",
    producer="ModelPolicy",
    consumer="ProviderAdapter",
    required_fields=("trace_id", "selected_candidate", "selection_rationale",
                     "eligibility_decision_id", "registry_version"),
    optional_fields=("ranked_alternatives", "utility_breakdown"),
    invariants=(
        "selected_candidate is a member of the eligible_set (invariant 1)",
        "selected_candidate references the exact eligibility_decision_id (invariant 2)",
        "ProviderAdapter cannot change the selected model silently (invariant 3)",
    ),
    allowed_states=("SELECTED", "NO_SELECTION"),
    reason_namespace=("MODEL",),
)

C4_PROVIDER_TO_TAP = Contract(
    contract_id="provider_adapter->assertion",
    schema_version="1",
    producer="ProviderAdapter",
    consumer="TAP",
    required_fields=("trace_id", "model_output_ref", "executed_candidate",
                     "provider_status", "output_evidence_refs"),
    optional_fields=("token_usage", "observed_latency_ms", "observed_cost_usd"),
    invariants=(
        "provider raw errors are normalized to RUNTIME.* here; none leak downstream (invariant 14)",
        "executed_candidate == selected_candidate (no silent substitution, invariant 3)",
        "technically successful output is NOT yet an approved assertion (invariant 4)",
    ),
    allowed_states=("OUTPUT_PRODUCED", "PROVIDER_EXECUTION_FAILED"),
    reason_namespace=("RUNTIME",),
    may_read_raw_provider_error=True,           # the ONLY contract permitted to
    retry_behavior="bounded_retry_then_reeligibility",
)

C5_TAP_TO_ACTIONPROPOSAL = Contract(
    contract_id="assertion->action_proposal",
    schema_version="1",
    producer="TAP",
    consumer="ActionProposalLayer",
    required_fields=("trace_id", "assertion_disposition", "governed_output_ref",
                     "assertion_policy_version"),
    optional_fields=("qualifications", "disclosures", "escalation_ref"),
    invariants=(
        "assertion_disposition in {APPROVE, QUALIFY, CONSTRAIN, ESCALATE, REJECT}",
        "REJECT/ESCALATE => no ActionProposal is constructed (terminal or human path)",
        "assertion approval does NOT imply action approval (invariant 5)",
        "assertions and actions remain independently governable (invariant 17)",
    ),
    allowed_states=("APPROVE", "QUALIFY", "CONSTRAIN", "ESCALATE", "REJECT"),
    reason_namespace=("ASSERT",),
)

C6_ACTIONPROPOSAL_TO_ACTIONGATE = Contract(
    contract_id="action_proposal->action_gate",
    schema_version="1",
    producer="ActionProposalLayer",
    consumer="ActionGate",
    required_fields=("trace_id", "proposed_action", "action_scope",
                     "request_authority_envelope", "action_policy_version"),
    optional_fields=("governed_output_ref", "human_authority_ref"),
    invariants=(
        "proposed_action is validated structurally first (ACTION.ACTION_PROPOSAL_INVALID)",
        "ActionGate sees the GOVERNED assertion output, not raw model output (decision-order finding)",
        "ActionGate cannot approve an action outside request_authority_envelope (invariant 6)",
    ),
    allowed_states=("PROPOSAL_VALID", "PROPOSAL_INVALID"),
    reason_namespace=("ACTION",),
)

C7_ACTIONGATE_TO_ACTIONADAPTER = Contract(
    contract_id="action_gate->action_adapter",
    schema_version="1",
    producer="ActionGate",
    consumer="ActionAdapter",
    required_fields=("trace_id", "action_disposition", "authorized_action",
                     "mode", "action_policy_version"),
    optional_fields=("constraints", "approval_ref", "override_actor", "override_rationale"),
    invariants=(
        "action_disposition in {ALLOW, DENY, APPROVE_REQUIRED, CONSTRAIN, ESCALATE, INDETERMINATE}",
        "only ALLOW (resolved) reaches ActionAdapter; DENY/ESCALATE/APPROVE_REQUIRED cannot (invariant 7)",
        "ActionAdapter executes ONLY in ENFORCEMENT mode (invariant: modes)",
        "human override must be explicit, attributable, auditable (invariant 8)",
    ),
    allowed_states=("ALLOW", "DENY", "APPROVE_REQUIRED", "CONSTRAIN", "ESCALATE", "INDETERMINATE"),
    reason_namespace=("ACTION", "RUNTIME"),
)

C8_ALL_TO_AUDIT = Contract(
    contract_id="all->audit_telemetry",
    schema_version="1",
    producer="*",
    consumer="Audit+Telemetry",
    required_fields=("decision_id", "request_id", "trace_id", "component",
                     "component_version", "decision_type", "output_state",
                     "reason_codes", "prior_record_hash", "record_hash"),
    optional_fields=("evidence_refs", "latency_ms", "projected_cost_usd", "observed_cost_usd"),
    invariants=(
        "every component emits exactly one decision record per decision it makes",
        "records are append-only and hash-chained (invariant 11: telemetry cannot rewrite)",
        "audit write failure blocks ENFORCEMENT where traceability is required (invariant 15)",
        "every terminal outcome is causally traceable (invariant 20)",
    ),
    allowed_states=("RECORDED", "WRITE_FAILED"),
    reason_namespace=("AUDIT",),
    retry_behavior="audit_write_no_retry_fail_closed",
)

C9_TELEMETRY_TO_REGISTRY = Contract(
    contract_id="telemetry->registry_updater",
    schema_version="1",
    producer="Telemetry",
    consumer="RegistryUpdater",
    required_fields=("trace_id", "observation", "observed_at", "target_registry_version"),
    optional_fields=("observed_latency_ms", "observed_cost_usd", "provider_status"),
    invariants=(
        "registry updates are PROSPECTIVE only; never affect the in-flight trace (invariant 12)",
        "telemetry cannot rewrite a prior decision (invariant 11)",
        "feedback path never creates a synchronous cycle EG<-REG in the same trace "
        "(invariant: RUNTIME.CIRCULAR_DEPENDENCY_DETECTED if attempted)",
    ),
    allowed_states=("UPDATE_ENQUEUED", "UPDATE_REJECTED"),
    reason_namespace=("AUDIT", "RUNTIME"),
    audit_required=True,
)


ALL_CONTRACTS: Dict[str, Contract] = {
    c.contract_id: c for c in (
        C1_NORMALIZER_TO_EXECGATE, C2_EXECGATE_TO_MODELPOLICY, C3_MODELPOLICY_TO_PROVIDER,
        C4_PROVIDER_TO_TAP, C5_TAP_TO_ACTIONPROPOSAL, C6_ACTIONPROPOSAL_TO_ACTIONGATE,
        C7_ACTIONGATE_TO_ACTIONADAPTER, C8_ALL_TO_AUDIT, C9_TELEMETRY_TO_REGISTRY,
    )
}

# The canonical hand-off order (linear critical path; C8 fans in from every stage,
# C9 is prospective/async). Used by the orchestrator to detect illegal skips.
HANDOFF_ORDER: Tuple[str, ...] = (
    "normalizer->execution_gate",
    "execution_gate->model_policy",
    "model_policy->provider_adapter",
    "provider_adapter->assertion",
    "assertion->action_proposal",
    "action_proposal->action_gate",
    "action_gate->action_adapter",
)


def validate_payload(contract_id: str, payload: Dict[str, Any],
                     schema_version: str = "1") -> Tuple[bool, List[str]]:
    """Return (ok, errors). Consumer-side contract check the orchestrator runs at each hand-off."""
    errors: List[str] = []
    c = ALL_CONTRACTS.get(contract_id)
    if c is None:
        return False, [f"POLICY.CONTRACT_VERSION_UNSUPPORTED: unknown contract {contract_id}"]
    if not c.accepts(schema_version):
        return False, [f"POLICY.CONTRACT_VERSION_UNSUPPORTED: {contract_id} v{schema_version}"]
    for fld in c.required_fields:
        if fld not in payload or payload[fld] is None:
            errors.append(f"missing required field '{fld}' for {contract_id}")
    return (len(errors) == 0), errors

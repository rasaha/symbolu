"""Immutable hard-constraint policy objects (policy-as-data).

``EnterpriseAgentPolicy`` holds the enterprise's hard constraints; ``EligibilityPolicy``
holds the deterministic interpreter's control knobs (evaluation order, evidence
precedence, unknown/expired handling, fail-closed behaviour). P1 treats every
constraint as a HARD gate — there are no preference weights or soft trade-offs.
"""
from __future__ import annotations

from typing import Optional, Tuple

from .canonical import AwcModel
from .fingerprint import stamp_fingerprint
from .version import CONTRACT_VERSION

#: The canonical, deterministic evaluation order of hard constraints (§16).
DEFAULT_EVALUATION_ORDER: Tuple[str, ...] = (
    "input_integrity",
    "pinned_versions",
    "agent_status_and_version",
    "capability_presence",
    "capability_evidence",
    "input_output_contract",
    "tools",
    "provider",
    "residency_deployment",
    "security_audit",
    "permissions",
    "authority_ceiling",
    "hard_limits",
)

#: The frozen evidence precedence (OBSERVED > MEASURED > DECLARED).
DEFAULT_EVIDENCE_PRECEDENCE: Tuple[str, ...] = ("OBSERVED", "MEASURED", "DECLARED")


class EnterpriseAgentPolicy(AwcModel):
    """Enterprise hard-constraint policy. Constraints only — no preferences."""

    contract_version: str = CONTRACT_VERSION
    policy_id: str
    policy_version: str
    allowed_providers: Tuple[str, ...] = ()          # empty => unrestricted
    forbidden_providers: Tuple[str, ...] = ()
    allowed_residencies: Tuple[str, ...] = ()          # empty => unrestricted
    required_residencies: Tuple[str, ...] = ()          # non-empty => must be one of
    allowed_deployment_environments: Tuple[str, ...] = ()
    minimum_security_classification: int = 0
    approved_agent_versions: Tuple[str, ...] = ()       # "agent_id@version"; empty => unrestricted
    forbidden_agent_versions: Tuple[str, ...] = ()
    allowed_tools: Tuple[str, ...] = ()                 # empty => unrestricted
    forbidden_tools: Tuple[str, ...] = ()
    maximum_permission_scope: Tuple[str, ...] = ()      # allowed permission universe; empty => unrestricted
    maximum_authority_scope: int = 0                    # 0 => unrestricted ceiling
    required_evidence_classes: Tuple[str, ...] = ()     # e.g. ("MEASURED",) or ("OBSERVED",)
    minimum_evidence_freshness_seconds: Optional[float] = None
    maximum_cost_hard_limit: Optional[float] = None
    maximum_latency_hard_limit: Optional[float] = None
    minimum_quality_hard_limit: Optional[float] = None
    required_audit_capabilities: Tuple[str, ...] = ()
    required_isolation: str = ""
    human_review_triggers: Tuple[str, ...] = ()
    fail_closed_on_unknown: bool = True
    policy_digest: str = ""


class EligibilityPolicy(AwcModel):
    """The deterministic hard-gate interpreter's control knobs (versioned data)."""

    contract_version: str = CONTRACT_VERSION
    policy_id: str
    policy_version: str
    evaluation_order: Tuple[str, ...] = DEFAULT_EVALUATION_ORDER
    evidence_precedence: Tuple[str, ...] = DEFAULT_EVIDENCE_PRECEDENCE
    unknown_evidence_fail_closed: bool = True
    expired_evidence_fail_closed: bool = True
    require_measured_or_observed_for_hard: bool = True
    schema_compatibility: str = "exact_or_declared_subset"
    capability_matching: str = "exact_id"
    short_circuit: bool = False   # False => complete elimination accounting (§16)
    policy_digest: str = ""


def finalize_enterprise_policy(policy: EnterpriseAgentPolicy) -> EnterpriseAgentPolicy:
    return stamp_fingerprint(policy, "policy_digest")  # type: ignore[return-value]


def finalize_eligibility_policy(policy: EligibilityPolicy) -> EligibilityPolicy:
    return stamp_fingerprint(policy, "policy_digest")  # type: ignore[return-value]


__all__ = [
    "DEFAULT_EVALUATION_ORDER",
    "DEFAULT_EVIDENCE_PRECEDENCE",
    "EnterpriseAgentPolicy",
    "EligibilityPolicy",
    "finalize_enterprise_policy",
    "finalize_eligibility_policy",
]

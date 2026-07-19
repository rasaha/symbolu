"""
HealthcareGovernanceService — the domain orchestration around generic ActionGate.

Flow per request:
    HealthcareAccessRequest
      → derive_criticality (deterministic; never trusts caller-declared risk)
      → adapt to generic AuthorizationRequest (facts, hard-block capabilities,
        advisory model signals)
      → GovernanceService.authorize (generic engine: human policy + per-decision
        authority mode + independent hard blocks + final-authority attribution)
      → minimum-necessary field reduction + applicability check (domain layer)
      → HealthcareAccessDecision + PHI-safe audit

The generic engine decides the AUTHORIZATION (may the actor perform this class of
action, under which authority mode). The healthcare layer adds deterministic
field-level minimum-necessary and applicability escalation. No hospital rule is
placed inside the generic engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.governance_models import AuthorizationRequest
from agentic.agentic_framework.human_policy import HumanPolicyEngine

from agentic.healthcare.request import HealthcareAccessRequest
from agentic.healthcare.taxonomy import (
    DataCategory,
    RESTRICTED_CATEGORIES,
    Role,
    expand_full_record,
)
from agentic.healthcare.criticality import (
    CriticalityDerivation,
    derive_criticality,
    minimum_necessary_categories,
)
from agentic.healthcare.policy import (
    build_healthcare_criticality_registry,
    build_healthcare_forbidden_policy_resolution,
    build_healthcare_policy_book,
)

_HEALTHCARE_TOOL = "healthcare_data_access"


class HealthcareOutcome(str, Enum):
    """Domain-level outcome (adds minimum-necessary constraint outcome)."""

    ALLOW = "ALLOW"
    ALLOW_WITH_CONSTRAINTS = "ALLOW_WITH_CONSTRAINTS"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"


class ApplicabilityStatus(str, Enum):
    CONSISTENT = "consistent"
    DISPUTED = "disputed"


@dataclass(frozen=True)
class HealthcareAccessDecision:
    """PHI-safe healthcare authorization decision."""

    outcome: HealthcareOutcome
    governance_decision: str  # generic ALLOW / DENY / DEFER
    allowed_categories: Tuple[str, ...]
    excluded_categories: Tuple[str, ...]
    constraints: Dict[str, Any]
    applicability_status: str
    criticality: str
    criticality_basis: Tuple[str, ...]
    effective_authority_mode: str
    matched_rule_id: str
    human_verdict: Optional[str]
    model_advisory_decision: Optional[str]
    hard_block: bool
    hard_block_provenance: Tuple[str, ...]
    final_authority_used: str
    consent_state: str
    requires_human_approval: bool
    minimum_necessary_applied: bool
    rationale: str
    policy_version: str
    policy_hash: str
    decision_id: Optional[str]
    # The generic response is retained for callers that need full provenance;
    # it contains only classifications/refs (no raw PHI).
    generic_response: Any = field(repr=False, default=None)

    def audit_dict(self) -> Dict[str, Any]:
        """Audit record — classifications, references, and provenance only.

        Contains NO raw protected health information by construction (the request
        model carries none). Safe to persist to a governance audit store.
        """
        return {
            "healthcare_domain": "patient_data_access",
            "outcome": self.outcome.value,
            "governance_decision": self.governance_decision,
            "allowed_data_categories": list(self.allowed_categories),
            "excluded_data_categories": list(self.excluded_categories),
            "required_redactions": list(self.constraints.get("required_redactions", [])),
            "constraints": self.constraints,
            "applicability_status": self.applicability_status,
            "criticality": self.criticality,
            "criticality_basis": list(self.criticality_basis),
            "effective_authority_mode": self.effective_authority_mode,
            "matched_rule_id": self.matched_rule_id,
            "human_verdict": self.human_verdict,
            "model_advisory_decision": self.model_advisory_decision,
            "hard_block": self.hard_block,
            "hard_block_provenance": list(self.hard_block_provenance),
            "final_authority_used": self.final_authority_used,
            "consent_state": self.consent_state,
            "requires_human_approval": self.requires_human_approval,
            "minimum_necessary_applied": self.minimum_necessary_applied,
            "rationale": self.rationale,
            "policy_version": self.policy_version,
            "policy_hash": self.policy_hash,
            "decision_id": self.decision_id,
        }


class HealthcareGovernanceService:
    """Wraps a generic GovernanceService configured for hospital data access."""

    def __init__(
        self,
        *,
        governance_service: Optional[GovernanceService] = None,
        policy_book=None,
        criticality_registry=None,
    ) -> None:
        self._book = policy_book or build_healthcare_policy_book()
        self._registry = criticality_registry or build_healthcare_criticality_registry()
        self._policy_version = self._book.policy_version()
        self._policy_hash = self._book.content_hash()
        if governance_service is not None:
            self._gov = governance_service
        else:
            self._gov = GovernanceService(
                human_policy_engine=HumanPolicyEngine(
                    self._book, criticality_registry=self._registry),
                policy_resolution=build_healthcare_forbidden_policy_resolution(),
            )

    # ---- adaptation --------------------------------------------------------

    def _to_authorization_request(
        self, request: HealthcareAccessRequest, derivation: CriticalityDerivation,
    ) -> AuthorizationRequest:
        agency = "FULL"
        if request.actor_role == Role.UNKNOWN_ACTOR or derivation.facts.get(
            "no_actor_identity"
        ):
            agency = "INFORM"
        metadata = {
            "facts": derivation.facts,
            "target": request.destination_ref or "",
            "healthcare": request.safe_reference(),
        }
        return AuthorizationRequest(
            actor_id=request.actor_id or "__no_actor__",
            action_type=request.operation.value,
            tool_name=_HEALTHCARE_TOOL,
            capabilities=list(derivation.hard_block_capabilities),
            agency_level=agency,
            quality_score=request.model_quality,
            coherence_score=request.model_coherence,
            internal_consistency=request.model_consistency,
            goal_alignment=request.model_goal_alignment,
            trajectory_confidence=request.model_trajectory_confidence,
            metadata=metadata,
        )

    # ---- minimum-necessary -------------------------------------------------

    def _minimum_necessary(
        self, request: HealthcareAccessRequest,
    ) -> Tuple[frozenset, frozenset, frozenset]:
        """Return (expanded_requested, allowed, excluded) category sets."""
        expanded = expand_full_record(frozenset(request.requested_categories))
        permitted = minimum_necessary_categories(
            request.actor_role, request.purpose, request.operation)
        allowed = expanded & permitted
        excluded = expanded - permitted
        return expanded, allowed, excluded

    # ---- orchestration -----------------------------------------------------

    def authorize(self, request: HealthcareAccessRequest) -> HealthcareAccessDecision:
        derivation = derive_criticality(request)
        authz = self._to_authorization_request(request, derivation)
        resp = self._gov.authorize(authz)

        hp = resp.human_policy or {}
        gd = resp.governance_decision.value
        hard_block = bool(hp.get("hard_block"))
        hard_block_prov = tuple(hp.get("hard_block_provenance", ()) or ())
        final_authority = hp.get("final_authority_used", "MODEL")
        model_advisory = hp.get("model_advisory_decision")
        human_verdict = hp.get("verdict")
        effective_mode = hp.get("effective_mode", "baseline")
        matched_rule = hp.get("matched_rule_id", "")

        expanded, allowed, excluded = self._minimum_necessary(request)

        # Applicability: a read-like request carrying export/exfiltration
        # indicators (or a model advisory challenge) disputes whether the matched
        # rule's action-class truly applies. This ESCALATES; it never silently
        # overrides the human verdict.
        suspected = bool(derivation.facts.get("suspected_reclassification"))
        applicability = ApplicabilityStatus.CONSISTENT

        constraints: Dict[str, Any] = {}
        min_necessary_applied = False
        rationale_parts: List[str] = []

        if gd == "DENY":
            outcome = HealthcareOutcome.DENY
            rationale_parts.append("Denied by governance.")
            if hard_block:
                rationale_parts.append(f"Hard block: {', '.join(hard_block_prov)}.")
        elif gd == "DEFER":
            outcome = HealthcareOutcome.REQUIRE_APPROVAL
            rationale_parts.append("Escalated for human approval.")
        else:  # ALLOW from the generic engine
            if suspected:
                outcome = HealthcareOutcome.REQUIRE_APPROVAL
                applicability = ApplicabilityStatus.DISPUTED
                rationale_parts.append(
                    "Applicability dispute: request shows reclassification "
                    "indicators inconsistent with the matched rule's class; "
                    "escalated for review instead of auto-allowing.")
            elif not allowed:
                outcome = HealthcareOutcome.DENY
                rationale_parts.append(
                    "Denied: no categories permitted under minimum-necessary "
                    "for this role/purpose.")
                min_necessary_applied = True
            else:
                constraints = self._build_constraints(
                    request, allowed, excluded, hp)
                if excluded or human_verdict == "ALLOW_WITH_CONSTRAINTS":
                    outcome = HealthcareOutcome.ALLOW_WITH_CONSTRAINTS
                    min_necessary_applied = bool(excluded)
                    if excluded:
                        rationale_parts.append(
                            f"Minimum-necessary: {len(allowed)} of "
                            f"{len(expanded)} requested categories permitted; "
                            f"{len(excluded)} excluded.")
                    else:
                        rationale_parts.append("Allowed with policy constraints.")
                else:
                    outcome = HealthcareOutcome.ALLOW
                    rationale_parts.append("Allowed within scope.")

        requires_human = outcome == HealthcareOutcome.REQUIRE_APPROVAL

        return HealthcareAccessDecision(
            outcome=outcome,
            governance_decision=gd,
            allowed_categories=tuple(sorted(c.value for c in allowed)),
            excluded_categories=tuple(sorted(c.value for c in excluded)),
            constraints=constraints,
            applicability_status=applicability.value,
            criticality=hp.get("criticality", derivation.signal),
            criticality_basis=derivation.basis,
            effective_authority_mode=effective_mode,
            matched_rule_id=matched_rule,
            human_verdict=human_verdict,
            model_advisory_decision=model_advisory,
            hard_block=hard_block,
            hard_block_provenance=hard_block_prov,
            final_authority_used=final_authority,
            consent_state=request.consent_state.value,
            requires_human_approval=requires_human,
            minimum_necessary_applied=min_necessary_applied,
            rationale=" ".join(rationale_parts),
            policy_version=self._policy_version,
            policy_hash=self._policy_hash,
            decision_id=resp.audit_reference,
            generic_response=resp,
        )

    def _build_constraints(
        self,
        request: HealthcareAccessRequest,
        allowed: frozenset,
        excluded: frozenset,
        hp: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Machine-readable minimum-necessary + scope constraints."""
        required_redactions = sorted(
            c.value for c in excluded if c in RESTRICTED_CATEGORIES)
        constraints: Dict[str, Any] = {
            "allowed_data_categories": sorted(c.value for c in allowed),
            "denied_data_categories": sorted(c.value for c in excluded),
            "required_redactions": required_redactions,
            "patient_scope": request.patient_ref,
            "encounter_scope": request.encounter_ref,
            "max_record_count": request.record_count,
            "approved_destination": (
                request.destination_ref if request.destination_approved else None),
            "no_onward_disclosure": bool(
                request.recipient_type.value != "internal"),
            "session_scoped": True,
        }
        # Merge the matched rule's static constraints (PHI-free).
        for k, v in (hp.get("constraints") or {}).items():
            constraints.setdefault(k, v)
        if excluded:
            constraints["minimum_necessary_explanation"] = (
                f"Requested {len(allowed) + len(excluded)} categories; permitted "
                f"{len(allowed)} for role={request.actor_role.value} "
                f"purpose={request.purpose.value}; excluded "
                f"{sorted(c.value for c in excluded)}.")
        return constraints

"""
Neutral typed governance-evidence model.

Ten validated capability groups (no ontology labels). Authority is carried
explicitly per evidence, never inferred from the capability group. Missing
information is explicit (``EvidenceStatus.MISSING``), never invented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple


class CapabilityGroup(str, Enum):
    IDENTITY_AUTHORITY = "identity_and_authority"
    PURPOSE_POLICY_BASIS = "purpose_and_policy_basis"
    AUTHORIZED_FORM = "authorized_action_form"
    CAPABILITY_SPACE = "capability_and_reachable_action_space"
    ADVISORY_PROVENANCE = "advisory_intelligence_provenance"
    DECISION_DERIVATION = "decision_derivation_and_policy_versions"
    PROTECTED_INVARIANTS = "protected_invariants"
    CUMULATIVE_CONSTRAINTS = "enterprise_cumulative_constraints"
    EXECUTION_OBSERVATION = "execution_and_observation"
    INTEGRATION_CLOSURE = "intended_state_integration_and_closure"


class EvidenceStatus(str, Enum):
    PRESENT = "present"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


class Verification(str, Enum):
    DECLARED = "declared"
    INFERRED = "inferred"
    VERIFIED = "verified"
    DISPUTED = "disputed"
    UNKNOWN = "unknown"


class AuthorityRole(str, Enum):
    AUTHORITY_BEARING = "authority_bearing"
    SUPPORTING = "supporting_evidence"
    ADVISORY = "advisory"
    NON_AUTHORITATIVE = "non_authoritative"


class PromotionLevel(str, Enum):
    """Shadow-mode promotion ladder — an invariant starts audit-only and is
    promoted individually only after validated data."""
    AUDIT = "audit_only"
    WARNING = "warning"
    APPROVAL_REQUIRED = "approval_required"
    HARD_ENFORCE = "hard_enforce"


class Disposition(str, Enum):
    PREVENTIVE = "preventive"
    BLOCKING = "blocking"
    ESCALATING = "escalating"
    AUDIT_ONLY = "audit_only"


@dataclass(frozen=True)
class GovernanceEvidence:
    capability: CapabilityGroup
    source: str                  # originating system (adapter)
    subject: str                 # what it is about (opportunity id, role, etc.)
    payload: Mapping[str, Any]   # capability-specific typed fields
    status: EvidenceStatus = EvidenceStatus.PRESENT
    verification: Verification = Verification.DECLARED
    authority_role: AuthorityRole = AuthorityRole.SUPPORTING
    source_refs: Tuple[str, ...] = ()
    confidence: Optional[float] = None

    @property
    def is_authority_bearing(self) -> bool:
        return (self.authority_role == AuthorityRole.AUTHORITY_BEARING
                and self.status == EvidenceStatus.PRESENT
                and self.verification in (Verification.VERIFIED, Verification.INFERRED))


@dataclass(frozen=True)
class GovernanceDecision:
    decision_id: str
    actor: str
    effect: str                  # allow / allow_with_constraints / widen / defer / deny
    supporting_refs: Tuple[str, ...] = ()   # evidence subjects it rests on
    reason_code: Optional[str] = None


@dataclass(frozen=True)
class GovernanceExecution:
    execution_id: str
    system: str
    subject_key: str
    authorized_form: Optional[str]
    executed_form: Optional[str]
    resulting_state: Any


@dataclass(frozen=True)
class WorkflowDependency:
    from_system: str
    to_system: str
    requires_subject: Optional[str]
    satisfied: bool
    stale: bool = False
    description: str = ""


PERMISSIVE = frozenset({"allow", "allow_with_constraints", "widen"})


@dataclass(frozen=True)
class WorkflowEvidence:
    workflow_id: str
    workflow_type: str
    evidence: Tuple[GovernanceEvidence, ...]
    decisions: Tuple[GovernanceDecision, ...] = ()
    executions: Tuple[GovernanceExecution, ...] = ()
    dependencies: Tuple[WorkflowDependency, ...] = ()
    marked_complete: bool = False

    def by_capability(self, cap: CapabilityGroup):
        return [e for e in self.evidence if e.capability == cap]

    def evidence_by_subject(self, subject: str) -> Optional[GovernanceEvidence]:
        for e in self.evidence:
            if e.subject == subject:
                return e
        return None


@dataclass(frozen=True)
class GovernanceFinding:
    invariant: str
    capability: CapabilityGroup
    failure_code: str
    detail: str
    disposition: Disposition
    default_promotion: PromotionLevel
    refs: Tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invariant": self.invariant,
            "capability": self.capability.value,
            "failure_code": self.failure_code,
            "detail": self.detail,
            "disposition": self.disposition.value,
            "default_promotion": self.default_promotion.value,
            "refs": list(self.refs),
        }

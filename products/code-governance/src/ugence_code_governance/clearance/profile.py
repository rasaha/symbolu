"""Company operational-policy projection for Action Clearance integration.

``CodeGovernanceClearanceProfile`` is a **narrow, immutable** projection of the
governance-relevant company configuration — not a general enterprise-policy
platform. It binds only identity/role/authority/account/repository/operational
policy configuration; it never collects salary, medical, performance-review,
private-communication, HR, or behavioral-surveillance data.

It projects deterministically onto the canonical Action Clearance
``ClearancePolicy`` via the Action Clearance public API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional, Tuple

# Canonical Action Clearance public API — consumed, never modified.
from ugence_action_clearance import (  # type: ignore
    ClearancePolicy,
    ClearanceStatus,
    SignalTrustLevel,
    SignalType,
)


class RepositoryClassification(str, Enum):
    """Repository/system criticality (reuses Code Governance risk terminology)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class CodeGovernanceClearanceProfile:
    """A narrow immutable company clearance configuration for a repository class."""

    profile_id: str
    profile_version: str
    tenant_id: str
    repository_classification: RepositoryClassification
    required_signal_types: Tuple[SignalType, ...] = ()
    trust_required_signal_types: Tuple[SignalType, ...] = ()
    minimum_trust_levels: Mapping[SignalType, SignalTrustLevel] = field(default_factory=dict)
    maximum_signal_age_s: Optional[int] = None
    maximum_shadow_clearance_lifetime_s: Optional[int] = None
    clock_skew_tolerance_s: int = 0
    incident_response: ClearanceStatus = ClearanceStatus.HOLD
    consumption_reserved_response: ClearanceStatus = ClearanceStatus.HOLD
    constraint_conflict_response: ClearanceStatus = ClearanceStatus.ESCALATE
    protected_branches: Tuple[str, ...] = ()
    sensitive_components: Tuple[str, ...] = ()
    #: Whether a CLEAR result needs no manual review for this change class.
    automatic_continuation_eligible: bool = True
    policy_refs: Tuple[str, ...] = ()

    @property
    def policy_ref(self) -> str:
        return f"{self.profile_id}:{self.profile_version}"

    def to_clearance_policy(self) -> ClearancePolicy:
        """Project onto the canonical Action Clearance policy (public API)."""
        return ClearancePolicy(
            policy_id=self.profile_id,
            policy_version=self.profile_version,
            required_signal_types=tuple(self.required_signal_types),
            minimum_signal_trust_levels={
                st.value: lvl for st, lvl in self.minimum_trust_levels.items()},
            maximum_signal_age_s=self.maximum_signal_age_s,
            maximum_clearance_lifetime_s=self.maximum_shadow_clearance_lifetime_s,
            clock_skew_tolerance_s=self.clock_skew_tolerance_s,
            incident_response=self.incident_response,
            consumption_reserved_response=self.consumption_reserved_response,
            constraint_conflict_response=self.constraint_conflict_response,
            trust_required_signal_types=tuple(self.trust_required_signal_types),
        )


__all__ = ["RepositoryClassification", "CodeGovernanceClearanceProfile"]

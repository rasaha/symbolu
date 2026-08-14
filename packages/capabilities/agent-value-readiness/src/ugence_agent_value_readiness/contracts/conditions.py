"""ConditionSet / compensating-control records (ADR §9, D-7).

An immutable structural record of a compensating control governing a
**conditional** concern. A mandatory gate is never eligible (D-6). ``APPROVED_ACTIVE``
requires structurally complete authority/owner/monitoring/evidence/time
information — but a label is **never** proof that a real authority approved it or
that time has expired/revoked it. GV-3R-b resolves and validates that authority
and time; this contract implements no condition execution, monitoring, or
revocation service.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_uvi_policy_contracts.api import RequirementClass

from ._util import canonical_digest, normalize_tokens, require_nonempty, require_tzaware
from .enums import ConditionStatus
from .errors import ReadinessContractError

__all__ = ["ConditionSet"]


@dataclass(frozen=True)
class ConditionSet:
    """A compensating-control record for a conditional concern."""

    condition_id: str
    source_gate_or_finding_ref: str
    concern_requirement_class: RequirementClass
    current_status: ConditionStatus
    approved_mitigation_ref: str = ""
    approving_authority_ref: str = ""
    accountable_owner: str = ""
    scope_exposure_limit: str = ""
    monitoring_requirement: str = ""
    evidence_refs: tuple[str, ...] = ()
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    expiry: Optional[datetime] = None
    revocation_trigger: str = ""

    def __post_init__(self) -> None:
        require_nonempty(self.condition_id, "ConditionSet.condition_id")
        require_nonempty(self.source_gate_or_finding_ref, "ConditionSet.source_gate_or_finding_ref")
        if not isinstance(self.concern_requirement_class, RequirementClass):
            raise ReadinessContractError("ConditionSet.concern_requirement_class must be a RequirementClass")
        # D-6: a mandatory concern can never be waived or conditionally compensated.
        if self.concern_requirement_class is not RequirementClass.CONDITIONAL:
            raise ReadinessContractError(
                "ConditionSet may only govern a CONDITIONAL concern; a "
                f"{self.concern_requirement_class.value} concern is never conditionally compensable (D-6)"
            )
        if not isinstance(self.current_status, ConditionStatus):
            raise ReadinessContractError("ConditionSet.current_status must be a ConditionStatus")

        object.__setattr__(self, "evidence_refs", normalize_tokens(self.evidence_refs, "ConditionSet.evidence_refs"))
        for name in ("effective_from", "effective_to", "expiry"):
            v = getattr(self, name)
            if v is not None:
                require_tzaware(v, f"ConditionSet.{name}")
        if self.effective_from is not None and self.effective_to is not None:
            if not self.effective_from < self.effective_to:
                raise ReadinessContractError("ConditionSet.effective_from must be before effective_to")
        if self.effective_from is not None and self.expiry is not None:
            if not self.effective_from < self.expiry:
                raise ReadinessContractError("ConditionSet.effective_from must be before expiry")

        # APPROVED_ACTIVE requires a structurally complete control record.
        if self.current_status is ConditionStatus.APPROVED_ACTIVE:
            require_nonempty(self.approved_mitigation_ref, "APPROVED_ACTIVE ConditionSet approved_mitigation_ref")
            require_nonempty(self.approving_authority_ref, "APPROVED_ACTIVE ConditionSet approving_authority_ref")
            require_nonempty(self.accountable_owner, "APPROVED_ACTIVE ConditionSet accountable_owner")
            require_nonempty(self.scope_exposure_limit, "APPROVED_ACTIVE ConditionSet scope_exposure_limit")
            require_nonempty(self.monitoring_requirement, "APPROVED_ACTIVE ConditionSet monitoring_requirement")
            require_nonempty(self.revocation_trigger, "APPROVED_ACTIVE ConditionSet revocation_trigger")
            if not self.evidence_refs:
                raise ReadinessContractError("APPROVED_ACTIVE ConditionSet requires evidence_refs")
            if self.effective_from is None:
                raise ReadinessContractError("APPROVED_ACTIVE ConditionSet requires effective_from")

    @property
    def is_active(self) -> bool:
        """Only ``APPROVED_ACTIVE`` is active; EXPIRED/REVOKED never are.

        A structural property of the recorded label — not a live authority or
        clock check (that is GV-3R-b).
        """

        return self.current_status is ConditionStatus.APPROVED_ACTIVE

    def canonical_digest(self) -> str:
        return canonical_digest(self)

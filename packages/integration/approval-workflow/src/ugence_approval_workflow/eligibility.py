"""Who may approve — a **port**, never an identity check.

This package never authenticates anyone, never resolves a directory, never holds a
credential and never decides that a principal *is* who they claim. Authentication
stays with the IdP behind Decision Authority's ``IdentityProvider``
(``packages/capabilities/decision-authority/.../identity/provider.py:24``); the wave 2
organizational authority directory is the intended adapter, and until it exists a
composition root supplies its own.

What the package does enforce is *structure* over whatever the port returns:

* the port must report the approver eligible at the caller's instant;
* an approver kind outside :data:`ELIGIBLE_APPROVER_KINDS` may never approve — an
  AI principal least of all;
* the approver must carry a role;
* the requester may not be the sole approver — the same no-self-approval shape the
  Policy Workflow Compiler applies to ``COMPILER_PRINCIPAL``
  (``.../policy-workflow-compiler/.../approval/records.py:15``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, runtime_checkable

from ._canon import optional_text, require_nonempty, require_tzaware
from .errors import ProductionModeRefused

__all__ = [
    "ApproverKind", "ApproverRef", "EligibilityDecision", "ApproverEligibilityPort",
    "ELIGIBLE_APPROVER_KINDS", "StaticApproverEligibility", "structural_refusals",
]


class ApproverKind(str, Enum):
    """What kind of principal a directory reports. Recorded, never authenticated."""

    HUMAN = "HUMAN"
    COMMITTEE = "COMMITTEE"
    DELEGATED_POLICY = "DELEGATED_POLICY"
    SERVICE = "SERVICE"
    AI = "AI"


#: The only kinds that may decide an approval. A delegated policy is a decision
#: *rule*, not an approver; a service account and an AI principal never approve.
ELIGIBLE_APPROVER_KINDS = frozenset({ApproverKind.HUMAN, ApproverKind.COMMITTEE})


@dataclass(frozen=True)
class ApproverRef:
    """A non-secret reference to a principal a directory reports as an approver."""

    approver_id: str
    approver_kind: ApproverKind
    role: str
    authority_reference: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "approver_id", require_nonempty(self.approver_id, "ApproverRef.approver_id"))
        object.__setattr__(self, "role", require_nonempty(self.role, "ApproverRef.role"))
        object.__setattr__(self, "authority_reference",
                           optional_text(self.authority_reference, "ApproverRef.authority_reference"))
        if not isinstance(self.approver_kind, ApproverKind):
            raise TypeError("ApproverRef.approver_kind must be an ApproverKind member")

    def to_dict(self) -> dict:
        return {"approver_id": self.approver_id, "approver_kind": self.approver_kind.value,
                "role": self.role, "authority_reference": self.authority_reference}

    @classmethod
    def from_dict(cls, d: dict) -> "ApproverRef":
        return cls(approver_id=d["approver_id"], approver_kind=ApproverKind(d["approver_kind"]),
                   role=d["role"], authority_reference=d.get("authority_reference", ""))


@dataclass(frozen=True)
class EligibilityDecision:
    """A typed answer, never a bare boolean. ``reasons`` is empty exactly when eligible."""

    eligible: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        if self.eligible and self.reasons:
            raise ValueError("an eligible decision carries no reasons")
        if not self.eligible and not self.reasons:
            raise ValueError("an ineligible decision must state its reasons")


@runtime_checkable
class ApproverEligibilityPort(Protocol):
    """Resolves *eligibility to approve*, never identity.

    Implementations answer from an organizational authority directory. They never
    authenticate, and this package never asks them to.
    """

    def eligible_approvers(self, *, tenant_id: str, subject_kind: str, subject_digest: str,
                           required_role: str, as_of: datetime) -> tuple[ApproverRef, ...]: ...

    def is_eligible(self, *, tenant_id: str, approver: ApproverRef, required_role: str,
                    scope: str, as_of: datetime) -> EligibilityDecision: ...


def structural_refusals(*, approver: ApproverRef, requested_by: str,
                        required_role: str, decision: EligibilityDecision) -> tuple[str, ...]:
    """The package's own rules over whatever the port reported. Empty means admissible."""

    reasons: list[str] = []
    if not decision.eligible:
        reasons.extend(decision.reasons)
    if approver.approver_kind not in ELIGIBLE_APPROVER_KINDS:
        reasons.append(f"approver kind {approver.approver_kind.value} may never approve")
    if required_role.strip() and approver.role != required_role.strip():
        reasons.append(f"approver role '{approver.role}' is not the required '{required_role.strip()}'")
    if approver.approver_id == requested_by:
        reasons.append("the requester may not be the sole approver")
    return tuple(reasons)


class StaticApproverEligibility:
    """In-memory reference adapter for tests and local composition.

    It answers eligibility from a table a composition root loads; it authenticates
    nobody and proves nothing about identity. Refused in production mode, where a
    real organizational authority directory belongs.
    """

    def __init__(self, approvers: tuple[ApproverRef, ...] = (), *,
                 production_mode: bool = False) -> None:
        if production_mode:
            raise ProductionModeRefused(
                "StaticApproverEligibility is a reference adapter and is refused in "
                "production mode; supply an organizational authority directory adapter")
        self._approvers: dict[str, ApproverRef] = {a.approver_id: a for a in approvers}

    def register(self, approver: ApproverRef) -> ApproverRef:
        self._approvers[approver.approver_id] = approver
        return approver

    def eligible_approvers(self, *, tenant_id: str, subject_kind: str, subject_digest: str,
                           required_role: str, as_of: datetime) -> tuple[ApproverRef, ...]:
        require_tzaware(as_of, "eligible_approvers.as_of")
        role = required_role.strip()
        return tuple(sorted(
            (a for a in self._approvers.values()
             if a.approver_kind in ELIGIBLE_APPROVER_KINDS and (not role or a.role == role)),
            key=lambda a: a.approver_id))

    def is_eligible(self, *, tenant_id: str, approver: ApproverRef, required_role: str,
                    scope: str, as_of: datetime) -> EligibilityDecision:
        require_tzaware(as_of, "is_eligible.as_of")
        known = self._approvers.get(approver.approver_id)
        if known is None:
            return EligibilityDecision(False, ("approver is not in the directory",))
        if known != approver:
            return EligibilityDecision(False, ("presented approver differs from the directory record",))
        role = required_role.strip()
        if role and known.role != role:
            return EligibilityDecision(False, (f"approver does not hold the role '{role}'",))
        return EligibilityDecision(True)

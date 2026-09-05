"""The three records this package holds, and the fourth that lifts containment.

An :class:`IncidentRecord` says *this was observed, here is where to read about it*.
It carries no diagnosis and no cause: the evidence is an
:class:`~ugence_governance_contracts.contracts.audit.AuditReference` into an audit
store that already exists (gap G4, governance-contracts 0.5.0), because a record
that embedded the evidence would be a seventh copy of the platform's audit.

A :class:`ContainmentRequest` asks for something to stop. A
:class:`ContainmentLift` — a **separate record, separately decided** — asks for it to
resume. Neither follows from the other, and neither follows from the incident
closing.

A :class:`RemediationProposal` is what somebody proposes doing. When Decision
Authority already recorded a ``CompensationRequirement`` for the same mismatch, the
proposal cites it **by id**: that record is already "a governed proposal, not an
auto-rollback" (``decision-authority/.../execution/compensation.py:1-7``), and a
second compensation type here would fork it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import AuditReference

from ._canon import domain_digest, iso, optional_text, require_nonempty, require_tzaware
from .errors import ContractViolation
from .states import ContainmentState, IncidentState, require_transition

__all__ = [
    "IncidentRecord", "ContainmentRequest", "ContainmentLift", "RemediationProposal",
    "INCIDENT_ID_PREFIX", "incident_id_for",
]

INCIDENT_ID_PREFIX = "inc_"


def _require_references(value, name: str) -> tuple[AuditReference, ...]:
    references = tuple(value)
    if not references:
        raise ContractViolation(
            f"{name} requires at least one AuditReference: an incident that names no "
            "audit entry cannot be read back, and this package stores no evidence itself")
    for reference in references:
        if not isinstance(reference, AuditReference):
            raise ContractViolation(
                f"{name} must contain governance-contracts AuditReference values; "
                "this package mints no audit reference of its own")
    return references


def incident_id_for(tenant_id: str, subject_ref: str,
                    evidence: tuple[AuditReference, ...], opened_at: datetime) -> str:
    """Deterministic incident id: no UUID, no clock.

    Derived from the evidence itself, so re-recording the same observation at the
    same instant is the same incident rather than a second one.
    """

    return INCIDENT_ID_PREFIX + domain_digest("incident_id", {
        "tenant_id": require_nonempty(tenant_id, "tenant_id"),
        "subject_ref": require_nonempty(subject_ref, "subject_ref"),
        "evidence": sorted(r.canonical_digest() for r in _require_references(evidence, "evidence")),
        "opened_at": iso(opened_at, "opened_at"),
    })[:32]


@dataclass(frozen=True)
class IncidentRecord:
    """One observed incident. It records; it diagnoses nothing."""

    incident_id: str
    tenant_id: str
    subject_ref: str
    #: An uninterpreted label the organization chose. The package knows no severity
    #: ordering and no taxonomy, so it can neither rank incidents nor escalate one.
    severity_label: str
    #: Where to read what was observed. At least one is required.
    evidence: tuple[AuditReference, ...]
    opened_at: datetime
    opened_by: str
    state: IncidentState = IncidentState.OPEN
    containment: ContainmentState = ContainmentState.NONE
    summary: str = ""
    closed_at: Optional[datetime] = None
    closed_by: str = ""

    def __post_init__(self) -> None:
        for name in ("incident_id", "tenant_id", "subject_ref", "severity_label", "opened_by"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"IncidentRecord.{name}"))
        for name in ("summary", "closed_by"):
            object.__setattr__(self, name,
                               optional_text(getattr(self, name), f"IncidentRecord.{name}"))
        object.__setattr__(self, "evidence",
                           _require_references(self.evidence, "IncidentRecord.evidence"))
        require_tzaware(self.opened_at, "IncidentRecord.opened_at")
        if self.closed_at is not None:
            require_tzaware(self.closed_at, "IncidentRecord.closed_at")
        for name, enum_type in (("state", IncidentState), ("containment", ContainmentState)):
            if not isinstance(getattr(self, name), enum_type):
                raise ContractViolation(f"IncidentRecord.{name} must be a {enum_type.__name__}")
        if (self.state is IncidentState.CLOSED) != (self.closed_at is not None):
            raise ContractViolation(
                "a closed incident carries closed_at, and an open one does not")
        expected = incident_id_for(self.tenant_id, self.subject_ref, self.evidence, self.opened_at)
        if self.incident_id != expected:
            raise ContractViolation(
                f"IncidentRecord.incident_id must be the derived id {expected!r}; ids are "
                "derived from the tenant, subject, evidence and instant, never chosen")

    # ------------------------------------------------------------------ #
    @property
    def is_open(self) -> bool:
        return self.state is not IncidentState.CLOSED

    @property
    def is_contained(self) -> bool:
        """Whether containment is currently *asked for* — never whether anything stopped."""

        return self.containment is ContainmentState.REQUESTED

    def evidence_digests(self) -> tuple[str, ...]:
        return tuple(sorted(reference.canonical_digest() for reference in self.evidence))

    def advanced_to(self, target: IncidentState) -> "IncidentRecord":
        require_transition(self.state, target)
        return replace(self, state=target)

    def closed(self, *, at: datetime, by: str) -> "IncidentRecord":
        """Close the incident. **Containment is untouched**, deliberately.

        An incident that closed itself and silently restored service is how a
        containment becomes theatre, so closing records only that the incident is
        closed. Whether anything resumes is a separate decision — see
        :class:`ContainmentLift`.
        """

        require_transition(self.state, IncidentState.CLOSED)
        require_tzaware(at, "closed.at")
        return replace(self, state=IncidentState.CLOSED, closed_at=at,
                       closed_by=require_nonempty(by, "by"))

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id, "tenant_id": self.tenant_id,
            "subject_ref": self.subject_ref, "severity_label": self.severity_label,
            "evidence": list(self.evidence_digests()),
            "opened_at": iso(self.opened_at, "opened_at"), "opened_by": self.opened_by,
            "state": self.state.value, "containment": self.containment.value,
            "summary": self.summary,
            "closed_at": iso(self.closed_at, "closed_at") if self.closed_at else "",
            "closed_by": self.closed_by,
        }

    def record_digest(self) -> str:
        return domain_digest("incident", self.to_dict())


@dataclass(frozen=True)
class ContainmentRequest:
    """A request that something stop. It stops nothing itself.

    The shape is ``PilotKillSwitchState``'s
    (``products/code-governance/.../pilot_operator/api.py:257``): a target, a reason,
    an instant and who asked. What acts on it is a composition root, and what
    actually revokes authority is RA-6 — never this package.
    """

    incident_id: str
    tenant_id: str
    target_ref: str
    reason: str
    requested_at: datetime
    requested_by: str

    def __post_init__(self) -> None:
        for name in ("incident_id", "tenant_id", "target_ref", "reason", "requested_by"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"ContainmentRequest.{name}"))
        require_tzaware(self.requested_at, "ContainmentRequest.requested_at")

    def to_dict(self) -> dict:
        return {"incident_id": self.incident_id, "tenant_id": self.tenant_id,
                "target_ref": self.target_ref, "reason": self.reason,
                "requested_at": iso(self.requested_at, "requested_at"),
                "requested_by": self.requested_by}

    def record_digest(self) -> str:
        return domain_digest("containment_request", self.to_dict())


@dataclass(frozen=True)
class ContainmentLift:
    """A **separate** decision that containment may end.

    It exists as its own record precisely so that lifting can never be inferred —
    not from an incident closing, not from a remediation being proposed, not from
    time passing. Somebody decides, and that decision is written down with its own
    author and justification.
    """

    incident_id: str
    tenant_id: str
    target_ref: str
    justification: str
    lifted_at: datetime
    lifted_by: str
    #: The containment this lifts, by digest, so a lift cannot float free of the
    #: request it answers.
    request_digest: str

    def __post_init__(self) -> None:
        for name in ("incident_id", "tenant_id", "target_ref", "justification",
                     "lifted_by", "request_digest"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"ContainmentLift.{name}"))
        require_tzaware(self.lifted_at, "ContainmentLift.lifted_at")

    def to_dict(self) -> dict:
        return {"incident_id": self.incident_id, "tenant_id": self.tenant_id,
                "target_ref": self.target_ref, "justification": self.justification,
                "lifted_at": iso(self.lifted_at, "lifted_at"), "lifted_by": self.lifted_by,
                "request_digest": self.request_digest}

    def record_digest(self) -> str:
        return domain_digest("containment_lift", self.to_dict())


@dataclass(frozen=True)
class RemediationProposal:
    """What somebody proposes doing. A proposal, never an instruction.

    ``compensation_ref`` cites a Decision Authority ``CompensationRequirement`` by id
    when one already exists for the same mismatch. This package mints no compensation
    type and forks no compensation status vocabulary: that record already forbids
    automatic rollback, and duplicating it here would create a second answer.
    """

    incident_id: str
    tenant_id: str
    proposed_action: str
    justification: str
    proposed_at: datetime
    proposed_by: str
    #: A Decision Authority ``CompensationRequirement`` id, when one applies.
    compensation_ref: str = ""

    def __post_init__(self) -> None:
        for name in ("incident_id", "tenant_id", "proposed_action", "justification",
                     "proposed_by"):
            object.__setattr__(self, name,
                               require_nonempty(getattr(self, name), f"RemediationProposal.{name}"))
        object.__setattr__(self, "compensation_ref",
                           optional_text(self.compensation_ref, "RemediationProposal.compensation_ref"))
        require_tzaware(self.proposed_at, "RemediationProposal.proposed_at")

    @property
    def cites_compensation(self) -> bool:
        return bool(self.compensation_ref)

    def to_dict(self) -> dict:
        return {"incident_id": self.incident_id, "tenant_id": self.tenant_id,
                "proposed_action": self.proposed_action, "justification": self.justification,
                "proposed_at": iso(self.proposed_at, "proposed_at"),
                "proposed_by": self.proposed_by, "compensation_ref": self.compensation_ref}

    def record_digest(self) -> str:
        return domain_digest("remediation_proposal", self.to_dict())

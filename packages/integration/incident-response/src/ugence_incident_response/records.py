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
from .errors import ContainmentLiftRefused, ContractViolation
from .states import ContainmentState, IncidentState, require_transition

__all__ = [
    "IncidentRecord", "ContainmentRequest", "ContainmentLift", "RemediationProposal",
    "INCIDENT_ID_PREFIX", "incident_id_for", "lift_refusals", "require_admissible_lift",
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
    #: The :class:`ContainmentRequest` that put this record in ``REQUESTED``, and
    #: the :class:`ContainmentLift` that moved it to ``LIFTED``. The **records**,
    #: not their digests: a digest is unverifiable in isolation, so a digest field
    #: would admit ``containment_lift_digest="deadbeef"``. Holding the records lets
    #: :meth:`_require_containment_evidence` re-run the full lift rules at
    #: construction, which is what gives the asymmetry teeth — every route to
    #: ``LIFTED``, ``dataclasses.replace`` included, must present a real and
    #: admissible lift, and constructing one *is* writing the decision down.
    containment_request: Optional["ContainmentRequest"] = None
    containment_lift: Optional["ContainmentLift"] = None
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
        self._require_containment_evidence()
        expected = incident_id_for(self.tenant_id, self.subject_ref, self.evidence, self.opened_at)
        if self.incident_id != expected:
            raise ContractViolation(
                f"IncidentRecord.incident_id must be the derived id {expected!r}; ids are "
                "derived from the tenant, subject, evidence and instant, never chosen")

    def _require_containment_evidence(self) -> None:
        """A containment state is admissible only with the record that produced it.

        This is what makes the asymmetry structural rather than conventional: the
        obvious bypass — ``dataclasses.replace(record, containment=LIFTED)`` — re-runs
        this check and is refused, because a lift with no :class:`ContainmentLift`
        behind it names no decision anybody made.
        """

        request, lift = self.containment_request, self.containment_lift
        if request is not None and not isinstance(request, ContainmentRequest):
            raise ContractViolation("containment_request must be a ContainmentRequest")
        if lift is not None and not isinstance(lift, ContainmentLift):
            raise ContractViolation("containment_lift must be a ContainmentLift")

        if self.containment is ContainmentState.NONE:
            if request is not None or lift is not None:
                raise ContractViolation(
                    "containment NONE carries no request and no lift")
            return

        if request is None:
            raise ContractViolation(
                f"containment {self.containment.value} requires the ContainmentRequest "
                "that asked for it")
        if request.incident_id != self.incident_id or request.tenant_id != self.tenant_id:
            raise ContractViolation(
                "the containment request belongs to a different incident")

        if self.containment is ContainmentState.REQUESTED:
            if lift is not None:
                raise ContractViolation("containment REQUESTED carries no lift")
            return

        if lift is None:
            raise ContractViolation(
                "containment LIFTED requires the ContainmentLift that ended it: a lift "
                "nobody decided is not a lift")
        reasons = lift_refusals(lift, request, self)
        if reasons:
            raise ContainmentLiftRefused(
                "containment LIFTED requires an admissible lift: " + "; ".join(reasons))

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

    def containment_requested(self, request: "ContainmentRequest") -> "IncidentRecord":
        """Record that containment was asked for, citing the request that asked."""

        if not isinstance(request, ContainmentRequest):
            raise ContractViolation("containment_requested.request must be a ContainmentRequest")
        if request.incident_id != self.incident_id or request.tenant_id != self.tenant_id:
            raise ContractViolation("the containment request belongs to a different incident")
        if self.containment is not ContainmentState.NONE:
            raise ContractViolation(
                f"containment is already {self.containment.value}; a second request is a "
                "new incident, not a re-request")
        return replace(self, containment=ContainmentState.REQUESTED,
                       containment_request=request)

    def containment_lifted(self, lift: "ContainmentLift") -> "IncidentRecord":
        """Record that containment ended — **only** on an admissible lift.

        The named path to ``LIFTED``, but not a privileged one: the same refusals run
        again in :meth:`_require_containment_evidence`, so a caller who reaches for
        ``dataclasses.replace`` instead gets the identical answer. The lift is judged
        against the request this record already holds, which is why a lift for some
        other containment cannot be presented here.
        """

        if self.containment is not ContainmentState.REQUESTED:
            raise ContainmentLiftRefused(
                f"containment is {self.containment.value}; only a REQUESTED containment "
                "can be lifted")
        reasons = lift_refusals(lift, self.containment_request, self)
        if reasons:
            raise ContainmentLiftRefused("; ".join(reasons))
        return replace(self, containment=ContainmentState.LIFTED, containment_lift=lift)

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id, "tenant_id": self.tenant_id,
            "subject_ref": self.subject_ref, "severity_label": self.severity_label,
            "evidence": list(self.evidence_digests()),
            "opened_at": iso(self.opened_at, "opened_at"), "opened_by": self.opened_by,
            "state": self.state.value, "containment": self.containment.value,
            "containment_request_digest": (
                self.containment_request.record_digest() if self.containment_request else ""),
            "containment_lift_digest": (
                self.containment_lift.record_digest() if self.containment_lift else ""),
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


def lift_refusals(lift: ContainmentLift, request: Optional[ContainmentRequest],
                  incident: Optional[IncidentRecord]) -> tuple[str, ...]:
    """Why a containment lift is inadmissible; empty means admissible.

    A lift must answer a specific request, in the same tenant, for the same target,
    on the same incident. It may **not** be justified by the incident being closed:
    closing records that the incident is over, never that service may resume.
    """

    reasons: list[str] = []
    if request is None:
        reasons.append("the containment request this lift answers does not exist")
    else:
        if lift.request_digest != request.record_digest():
            reasons.append("request_digest does not match the presented containment request")
        if lift.tenant_id != request.tenant_id:
            reasons.append("a lift may not cross tenants")
        if lift.target_ref != request.target_ref:
            reasons.append("a lift must name the target its request contained")
        if lift.incident_id != request.incident_id:
            reasons.append("a lift must belong to the incident its request belongs to")
        if lift.lifted_at < request.requested_at:
            reasons.append("a lift may not precede the containment it lifts")
    if incident is not None and incident.incident_id != lift.incident_id:
        reasons.append("the presented incident is not this lift's incident")
    return tuple(reasons)


def require_admissible_lift(lift: ContainmentLift, request: Optional[ContainmentRequest],
                            incident: Optional[IncidentRecord] = None) -> None:
    """Raise :class:`ContainmentLiftRefused` when the lift is inadmissible."""

    reasons = lift_refusals(lift, request, incident)
    if reasons:
        raise ContainmentLiftRefused("; ".join(reasons))


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

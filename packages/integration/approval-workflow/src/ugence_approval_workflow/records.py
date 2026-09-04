"""The approval artifact and the ledger event.

The artifact carries the fields the Policy Workflow Compiler's record already
proved useful — reviewer id and role, a non-secret authority reference, digest
binding, accepted findings, justification, a signature reference and the
``is_fixture`` label — over a **neutral subject** rather than a policy pack
(ratified decision D-3). The compiler's ``HumanApprovalRecord`` is neither
imported nor amended.

Expiry is a :class:`~ugence_governance_contracts.contracts.validity.Validity`
evaluated at a caller-supplied instant. ``state_at`` derives ``EXPIRED``; nothing
here reads a clock.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Optional

from ugence_governance_contracts.api import Validity, ValidityStatus

from ._canon import (
    domain_digest,
    from_iso,
    iso,
    optional_text,
    require_nonempty,
    require_tzaware,
)
from .errors import ArtifactIntegrityError, ContractViolation
from .states import EXPIRABLE_STATES, ApprovalState
from .subject import ApprovalSubject

__all__ = ["ApprovalRecord", "ApprovalEvent", "validity_to_dict", "validity_from_dict"]


def validity_to_dict(validity: Validity) -> dict:
    return {"issued_at": iso(validity.issued_at, "Validity.issued_at"),
            "expires_at": iso(validity.expires_at, "Validity.expires_at") if validity.expires_at else "",
            "stale_after": iso(validity.stale_after, "Validity.stale_after") if validity.stale_after else ""}


def validity_from_dict(d: Optional[dict]) -> Optional[Validity]:
    if not d:
        return None
    return Validity(issued_at=from_iso(d["issued_at"]),
                    expires_at=from_iso(d["expires_at"]) if d.get("expires_at") else None,
                    stale_after=from_iso(d["stale_after"]) if d.get("stale_after") else None)


@dataclass(frozen=True)
class ApprovalRecord:
    """One approval request and whatever has since been decided about it."""

    approval_id: str
    tenant_id: str
    subject_kind: str
    subject_digest: str
    subject_ref: str
    requested_by: str
    required_role: str
    state: ApprovalState
    validity: Validity
    request_ordinal: int = 1
    supersedes: str = ""
    justification: str = ""
    #: Finding ids (gaps, warnings, diagnostics) the approver explicitly accepted.
    accepted_finding_ids: tuple[str, ...] = ()
    decided_by: str = ""
    decided_role: str = ""
    decided_authority_reference: str = ""
    decided_at: Optional[datetime] = None
    #: A non-secret reference to a detached signature, when one exists.
    signature_reference: str = ""
    #: True when this record is a labeled offline example, not a real authority.
    is_fixture: bool = False
    exception_requested_by: str = ""
    exception_justification: str = ""
    #: The bounded window of a granted exception (ratified decision D-2).
    exception_validity: Optional[Validity] = None
    consumer_ref: str = ""
    consumed_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        for name in ("approval_id", "tenant_id", "subject_kind", "subject_digest", "requested_by"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), f"ApprovalRecord.{name}"))
        for name in ("subject_ref", "required_role", "supersedes", "justification", "decided_by",
                     "decided_role", "decided_authority_reference", "signature_reference",
                     "exception_requested_by", "exception_justification", "consumer_ref"):
            object.__setattr__(self, name, optional_text(getattr(self, name), f"ApprovalRecord.{name}"))
        if not isinstance(self.state, ApprovalState):
            raise ContractViolation("ApprovalRecord.state must be an ApprovalState member")
        if not isinstance(self.validity, Validity):
            raise ContractViolation("ApprovalRecord.validity must be a governance-contracts Validity")
        if self.exception_validity is not None and not isinstance(self.exception_validity, Validity):
            raise ContractViolation("ApprovalRecord.exception_validity must be a Validity")
        if not isinstance(self.request_ordinal, int) or self.request_ordinal < 1:
            raise ContractViolation("ApprovalRecord.request_ordinal must be an integer >= 1")
        object.__setattr__(self, "accepted_finding_ids", tuple(self.accepted_finding_ids))
        for name in ("decided_at", "consumed_at"):
            value = getattr(self, name)
            if value is not None:
                require_tzaware(value, f"ApprovalRecord.{name}")

    # ------------------------------------------------------------------ #
    @property
    def subject(self) -> ApprovalSubject:
        return ApprovalSubject(tenant_id=self.tenant_id, subject_kind=self.subject_kind,
                               subject_digest=self.subject_digest, subject_ref=self.subject_ref)

    @property
    def is_fixture_record(self) -> bool:
        return self.is_fixture

    def effective_validity(self) -> Validity:
        """The window that governs this record now: an exception grant carries its own."""

        if self.state in (ApprovalState.EXCEPTION_GRANTED, ApprovalState.EXCEPTION_REQUESTED) \
                and self.exception_validity is not None:
            return self.exception_validity
        return self.validity

    def validity_status_at(self, as_of: datetime) -> ValidityStatus:
        return self.effective_validity().status_at(require_tzaware(as_of, "as_of"))

    def state_at(self, as_of: datetime) -> ApprovalState:
        """The state that applies at ``as_of``: ``EXPIRED`` is derived, never swept."""

        if self.state in EXPIRABLE_STATES and \
                self.validity_status_at(as_of) is ValidityStatus.EXPIRED:
            return ApprovalState.EXPIRED
        return self.state

    def evolve(self, **changes: object) -> "ApprovalRecord":
        """A new snapshot; the prior one is never mutated."""

        return replace(self, **changes)  # type: ignore[arg-type]

    # ------------------------------------------------------------------ #
    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id, "tenant_id": self.tenant_id,
            "subject_kind": self.subject_kind, "subject_digest": self.subject_digest,
            "subject_ref": self.subject_ref, "requested_by": self.requested_by,
            "required_role": self.required_role, "state": self.state.value,
            "validity": validity_to_dict(self.validity), "request_ordinal": self.request_ordinal,
            "supersedes": self.supersedes, "justification": self.justification,
            "accepted_finding_ids": list(self.accepted_finding_ids),
            "decided_by": self.decided_by, "decided_role": self.decided_role,
            "decided_authority_reference": self.decided_authority_reference,
            "decided_at": iso(self.decided_at, "decided_at") if self.decided_at else "",
            "signature_reference": self.signature_reference, "is_fixture": self.is_fixture,
            "exception_requested_by": self.exception_requested_by,
            "exception_justification": self.exception_justification,
            "exception_validity": validity_to_dict(self.exception_validity) if self.exception_validity else {},
            "consumer_ref": self.consumer_ref,
            "consumed_at": iso(self.consumed_at, "consumed_at") if self.consumed_at else "",
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ApprovalRecord":
        return cls(
            approval_id=d["approval_id"], tenant_id=d["tenant_id"], subject_kind=d["subject_kind"],
            subject_digest=d["subject_digest"], subject_ref=d.get("subject_ref", ""),
            requested_by=d["requested_by"], required_role=d.get("required_role", ""),
            state=ApprovalState(d["state"]), validity=validity_from_dict(d["validity"]),
            request_ordinal=int(d.get("request_ordinal", 1)), supersedes=d.get("supersedes", ""),
            justification=d.get("justification", ""),
            accepted_finding_ids=tuple(d.get("accepted_finding_ids", ())),
            decided_by=d.get("decided_by", ""), decided_role=d.get("decided_role", ""),
            decided_authority_reference=d.get("decided_authority_reference", ""),
            decided_at=from_iso(d["decided_at"]) if d.get("decided_at") else None,
            signature_reference=d.get("signature_reference", ""),
            is_fixture=bool(d.get("is_fixture", False)),
            exception_requested_by=d.get("exception_requested_by", ""),
            exception_justification=d.get("exception_justification", ""),
            exception_validity=validity_from_dict(d.get("exception_validity")),
            consumer_ref=d.get("consumer_ref", ""),
            consumed_at=from_iso(d["consumed_at"]) if d.get("consumed_at") else None)

    def artifact_digest(self) -> str:
        """Domain-separated digest over the whole artifact, for mirrors and audit."""

        return domain_digest("artifact", self.to_dict())

    def verify(self, expected_digest: str) -> None:
        if self.artifact_digest() != expected_digest:
            raise ArtifactIntegrityError(
                f"approval '{self.approval_id}' does not re-derive its stored artifact digest")


@dataclass(frozen=True)
class ApprovalEvent:
    """One append-only ledger event. ``sequence`` is monotonic per approval."""

    event_id: str
    approval_id: str
    sequence: int
    event_type: ApprovalState
    occurred_at: datetime
    actor: str = ""
    detail: str = ""

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "approval_id": self.approval_id,
                "sequence": self.sequence, "event_type": self.event_type.value,
                "occurred_at": iso(self.occurred_at, "occurred_at"),
                "actor": self.actor, "detail": self.detail}

"""How an approval is bound to a proposed transition (owner ruling HR-3).

    subject_kind    = "agent_runtime_proposal"
    subject_digest  = the proposal fingerprint
    consumer_ref    = "<instance_id>:<task_id>"

The fingerprint is the subject. Agent Runtime rebuilds the proposal on every
quantum and hashes its identity, action, arguments and idempotency key into it, so a
re-evaluation that proposes anything different finds no approval and stays parked.
That reuses the ledger's own rule that a changed subject never reuses a standing
decision; nothing here re-implements it.

The consumer reference names the instance and task, so the exactly-once consumption
key is per instance and per task. A second instance proposing the identical action
holds a different fingerprint anyway; the consumer reference is the second lock, and
it is what lets a crash between consumption and advance be recognised on the re-drive
(the holder of an ``ALREADY_CONSUMED`` outcome names this instance and task).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ugence_approval_workflow import (
    ApprovalSubject,
    ConsumptionKey,
    approval_id_for,
    consumption_id_for,
)

from .errors import ContractViolation

__all__ = [
    "SUBJECT_KIND",
    "ProposalIdentity",
    "identity_of",
    "subject_for",
    "consumer_ref_for",
    "approval_id_for_identity",
    "expected_consumption_id",
]

#: The ratified subject kind for a proposal-bound approval (HR-3).
SUBJECT_KIND = "agent_runtime_proposal"


@dataclass(frozen=True)
class ProposalIdentity:
    """The three facts the binding needs from a proposal, and nothing else.

    Deliberately not the proposal itself: the crash-recovery test drives the binding
    from a child process that has the fingerprint but no live runtime, and the binding
    must behave identically either way.
    """

    fingerprint: str
    instance_id: str
    task_id: str

    def __post_init__(self) -> None:
        for name in ("fingerprint", "instance_id", "task_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"ProposalIdentity.{name} must be a non-empty string")
            object.__setattr__(self, name, value.strip())
        if ":" in self.instance_id:
            raise ContractViolation(
                "ProposalIdentity.instance_id may not contain ':'; it would make the "
                "consumer reference ambiguous"
            )


def identity_of(proposal: Any) -> ProposalIdentity:
    """Read the identity off a runtime ``TransitionProposal`` (or anything shaped like one)."""

    return ProposalIdentity(
        fingerprint=str(getattr(proposal, "fingerprint", "") or ""),
        instance_id=str(getattr(proposal, "instance_id", "") or ""),
        task_id=str(getattr(proposal, "task_id", "") or ""),
    )


def subject_for(identity: ProposalIdentity, *, tenant_id: str) -> ApprovalSubject:
    return ApprovalSubject(
        tenant_id=tenant_id,
        subject_kind=SUBJECT_KIND,
        subject_digest=identity.fingerprint,
        subject_ref=consumer_ref_for(identity),
    )


def consumer_ref_for(identity: ProposalIdentity) -> str:
    return f"{identity.instance_id}:{identity.task_id}"


def approval_id_for_identity(identity: ProposalIdentity, *, tenant_id: str,
                             requester_ref: str, request_ordinal: int = 1) -> str:
    """Deterministic: the same proposal, requester and ordinal always name one approval."""

    return approval_id_for(subject_for(identity, tenant_id=tenant_id), requester_ref,
                           request_ordinal)


def expected_consumption_id(identity: ProposalIdentity, *, tenant_id: str,
                            approval_id: str) -> str:
    """The consumption id THIS instance and task would hold if it consumed the approval.

    Used to recognise a re-drive after a crash: ``ALREADY_CONSUMED`` whose holder equals
    this id is this instance's own earlier consumption, and is satisfied.
    """

    return consumption_id_for(ConsumptionKey(
        tenant_id=tenant_id, approval_id=approval_id,
        subject_digest=identity.fingerprint, consumer_ref=consumer_ref_for(identity),
    ))

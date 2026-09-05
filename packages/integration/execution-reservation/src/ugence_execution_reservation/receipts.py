"""Clearance receipts — durable record, lifecycle events, repository port (phase E).

The **body** is Action Clearance's own ``ClearanceReceiptBody`` (content-addressed,
``receipt_id = "acr_" + result_fingerprint``). This module wraps it with the
storage and reconstruction metadata the prerequisites design assigns to the
persistence, reconstruction and lifecycle partitions, and defines the five-state
lifecycle as **append-only events plus derived expiry**. The body is never
rewritten; every transition is an event.

Integrity is verified through Action Clearance's public surface only: the body
is rebuilt into a ``ClearanceResult`` and its ``result_fingerprint`` property must
equal the stored fingerprint and re-derive the receipt id. No private fingerprint
helper is imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol, Sequence, runtime_checkable

from ugence_action_clearance import ClearanceReceiptBody, ClearanceResult, ClearanceStatus
from ugence_governance_contracts.api import Validity, ValidityStatus

from ._canon import canonical_json, from_iso, iso, require_nonempty, require_tzaware
from .errors import ReceiptIntegrityError

__all__ = [
    "ReceiptLifecycleState",
    "PutReceiptResult",
    "SupersessionResult",
    "RevocationResult",
    "ClearanceReceipt",
    "ReceiptLifecycleEvent",
    "ClearanceReceiptRepository",
    "verify_receipt_body",
    "receipt_validity",
    "derive_lifecycle_state",
    "body_to_dict",
    "body_from_dict",
]


class ReceiptLifecycleState(str, Enum):
    """The five durable states. CONSUMED / EXECUTING / EXECUTED are *not* here."""

    ISSUED = "ISSUED"
    EXPIRED = "EXPIRED"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"
    INVALIDATED = "INVALIDATED"


class PutReceiptResult(str, Enum):
    CREATED = "CREATED"
    ALREADY_EXISTS_IDENTICAL = "ALREADY_EXISTS_IDENTICAL"
    CONFLICT_DIFFERENT_BODY = "CONFLICT_DIFFERENT_BODY"


class SupersessionResult(str, Enum):
    SUPERSEDED = "SUPERSEDED"
    ALREADY_SUPERSEDED = "ALREADY_SUPERSEDED"
    NOT_FOUND = "NOT_FOUND"
    SUCCESSOR_NOT_FOUND = "SUCCESSOR_NOT_FOUND"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"


class RevocationResult(str, Enum):
    REVOKED = "REVOKED"
    ALREADY_REVOKED = "ALREADY_REVOKED"
    NOT_FOUND = "NOT_FOUND"


# --------------------------------------------------------------------------- #
# Body (de)serialization — exact, byte-stable
# --------------------------------------------------------------------------- #
def body_to_dict(body: ClearanceReceiptBody) -> dict:
    return {
        "receipt_version": body.receipt_version,
        "tenant_id": body.tenant_id,
        "request_id": body.request_id,
        "authorization_ref": body.authorization_ref,
        "authorized_action_fingerprint": body.authorized_action_fingerprint,
        "clearance_status": body.clearance_status.value,
        "reason_codes": list(body.reason_codes),
        "effective_constraints": list(body.effective_constraints),
        "obligations": list(body.obligations),
        "signal_refs": list(body.signal_refs),
        "signal_bundle_fingerprint": body.signal_bundle_fingerprint,
        "policy_refs": list(body.policy_refs),
        "evaluated_at": iso(body.evaluated_at, "ClearanceReceiptBody.evaluated_at"),
        "valid_until": iso(body.valid_until, "ClearanceReceiptBody.valid_until"),
        "request_fingerprint": body.request_fingerprint,
        "result_fingerprint": body.result_fingerprint,
    }


def body_from_dict(d: dict) -> ClearanceReceiptBody:
    return ClearanceReceiptBody(
        receipt_version=d["receipt_version"],
        tenant_id=d["tenant_id"],
        request_id=d["request_id"],
        authorization_ref=d["authorization_ref"],
        authorized_action_fingerprint=d["authorized_action_fingerprint"],
        clearance_status=ClearanceStatus(d["clearance_status"]),
        reason_codes=tuple(d["reason_codes"]),
        effective_constraints=tuple(d["effective_constraints"]),
        obligations=tuple(d["obligations"]),
        signal_refs=tuple(d["signal_refs"]),
        signal_bundle_fingerprint=d["signal_bundle_fingerprint"],
        policy_refs=tuple(d["policy_refs"]),
        evaluated_at=from_iso(d["evaluated_at"]),
        valid_until=from_iso(d["valid_until"]),
        request_fingerprint=d["request_fingerprint"],
        result_fingerprint=d["result_fingerprint"],
    )


def verify_receipt_body(body: ClearanceReceiptBody) -> None:
    """Rebuild the result through the public surface and re-derive the fingerprint.

    Raises :class:`ReceiptIntegrityError` when the stored ``result_fingerprint``
    does not equal the recomputed one, or the receipt id does not follow from it.
    """

    result = ClearanceResult(
        request_id=body.request_id,
        authorization_ref=body.authorization_ref,
        authorized_action_fingerprint=body.authorized_action_fingerprint,
        status=body.clearance_status,
        reason_codes=tuple(body.reason_codes),
        effective_constraints=tuple(body.effective_constraints),
        obligations=tuple(body.obligations),
        evaluated_at=body.evaluated_at,
        valid_until=body.valid_until,
        policy_refs=tuple(body.policy_refs),
        signal_refs=tuple(body.signal_refs),
        request_fingerprint=body.request_fingerprint,
        tenant_id=body.tenant_id,
        signal_bundle_fingerprint=body.signal_bundle_fingerprint,
    )
    if result.result_fingerprint != body.result_fingerprint:
        raise ReceiptIntegrityError(
            "receipt body does not re-derive its result_fingerprint (body altered)")
    if body.receipt_id != "acr_" + body.result_fingerprint:
        raise ReceiptIntegrityError("receipt_id does not follow from result_fingerprint")


def receipt_validity(body: ClearanceReceiptBody) -> Validity:
    """Half-open ``[evaluated_at, valid_until)``: boundary-at-expiry is expired."""

    return Validity(issued_at=body.evaluated_at, expires_at=body.valid_until)


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClearanceReceipt:
    """The durable record: immutable body + persistence and reconstruction metadata.

    ``target_ref``, ``operation`` and ``profile_id`` are captured from the
    ``ClearanceRequest`` at put time because the body does not carry them and the
    reservation must bind target and operation (validation checks 8 and 9) and the
    lineage tuple needs the profile.
    """

    body: ClearanceReceiptBody
    created_at: datetime
    target_ref: str
    operation: str
    profile_id: str
    action_governance_result_fingerprint: str = ""
    correlation_id: str = ""
    workflow_id: str = ""
    decision_record_ref: str = ""
    context_envelope_ref: str = ""
    context_envelope_hash: str = ""

    def __post_init__(self) -> None:
        require_tzaware(self.created_at, "ClearanceReceipt.created_at")
        for name in ("target_ref", "operation", "profile_id"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name),
                                                            f"ClearanceReceipt.{name}"))

    @property
    def receipt_id(self) -> str:
        return self.body.receipt_id

    @property
    def tenant_id(self) -> str:
        return self.body.tenant_id

    @property
    def authorization_ref(self) -> str:
        return self.body.authorization_ref

    @property
    def authorized_action_fingerprint(self) -> str:
        return self.body.authorized_action_fingerprint

    @property
    def is_clear(self) -> bool:
        return self.body.clearance_status is ClearanceStatus.CLEAR

    @property
    def lineage_key(self) -> tuple[str, str, str, str, str]:
        """``RECEIPT_SUPERSESSION.md``: same lineage iff these five agree."""

        return (self.tenant_id, self.authorization_ref, self.authorized_action_fingerprint,
                self.target_ref, self.profile_id)

    @property
    def validity(self) -> Validity:
        return receipt_validity(self.body)

    def to_dict(self) -> dict:
        return {
            "body": body_to_dict(self.body),
            "created_at": iso(self.created_at),
            "target_ref": self.target_ref,
            "operation": self.operation,
            "profile_id": self.profile_id,
            "action_governance_result_fingerprint": self.action_governance_result_fingerprint,
            "correlation_id": self.correlation_id,
            "workflow_id": self.workflow_id,
            "decision_record_ref": self.decision_record_ref,
            "context_envelope_ref": self.context_envelope_ref,
            "context_envelope_hash": self.context_envelope_hash,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClearanceReceipt":
        return cls(body=body_from_dict(d["body"]), created_at=from_iso(d["created_at"]),
                   target_ref=d["target_ref"], operation=d["operation"],
                   profile_id=d["profile_id"],
                   action_governance_result_fingerprint=d.get("action_governance_result_fingerprint", ""),
                   correlation_id=d.get("correlation_id", ""), workflow_id=d.get("workflow_id", ""),
                   decision_record_ref=d.get("decision_record_ref", ""),
                   context_envelope_ref=d.get("context_envelope_ref", ""),
                   context_envelope_hash=d.get("context_envelope_hash", ""))

    def canonical_bytes(self) -> bytes:
        """The exact bytes stored and returned; scenario 15 compares these."""

        return canonical_json(self.to_dict()).encode("utf-8")


@dataclass(frozen=True)
class ReceiptLifecycleEvent:
    """Append-only lifecycle event; ``sequence`` is monotonic per receipt."""

    event_id: str
    receipt_id: str
    sequence: int
    event_type: ReceiptLifecycleState
    occurred_at: datetime
    owner: str
    trigger: str = ""
    ref: str = ""

    def to_dict(self) -> dict:
        return {"event_id": self.event_id, "receipt_id": self.receipt_id,
                "sequence": self.sequence, "event_type": self.event_type.value,
                "occurred_at": iso(self.occurred_at), "owner": self.owner,
                "trigger": self.trigger, "ref": self.ref}


_TERMINAL_PRECEDENCE = (ReceiptLifecycleState.INVALIDATED, ReceiptLifecycleState.REVOKED,
                        ReceiptLifecycleState.SUPERSEDED)


def derive_lifecycle_state(receipt: ClearanceReceipt,
                           events: Sequence[ReceiptLifecycleEvent],
                           as_of: datetime) -> Optional[ReceiptLifecycleState]:
    """Effective lifecycle = immutable events + time. ``None`` for a never-issued record.

    Precedence: INVALIDATED > REVOKED > SUPERSEDED > EXPIRED (derived) > ISSUED.
    A non-CLEAR result is recorded for audit but never ISSUED, so it has no
    lifecycle state at all.
    """

    require_tzaware(as_of, "derive_lifecycle_state.as_of")
    types = {e.event_type for e in events}
    if ReceiptLifecycleState.ISSUED not in types:
        return None
    for terminal in _TERMINAL_PRECEDENCE:
        if terminal in types:
            return terminal
    if receipt.validity.status_at(as_of) is ValidityStatus.EXPIRED:
        return ReceiptLifecycleState.EXPIRED
    return ReceiptLifecycleState.ISSUED


# --------------------------------------------------------------------------- #
# Port
# --------------------------------------------------------------------------- #
@runtime_checkable
class ClearanceReceiptRepository(Protocol):
    """``RECEIPT_PERSISTENCE_INTERFACE.md``, plus the derived-lifecycle read."""

    def put_receipt(self, receipt: ClearanceReceipt) -> PutReceiptResult: ...
    def get_receipt(self, receipt_id: str) -> Optional[ClearanceReceipt]: ...
    def get_receipt_by_result_fingerprint(self, result_fingerprint: str) -> Optional[ClearanceReceipt]: ...
    def list_receipts_for_authorization(self, tenant_id: str, authorization_ref: str) -> tuple[ClearanceReceipt, ...]: ...
    def supersede_receipt(self, receipt_id: str, reason: str, superseding_ref: str, *,
                          occurred_at: datetime) -> SupersessionResult: ...
    def revoke_receipt(self, receipt_id: str, reason: str, upstream_ref: str, *,
                       occurred_at: datetime) -> RevocationResult: ...
    def invalidate_receipt(self, receipt_id: str, reason: str, *, occurred_at: datetime) -> bool: ...
    def receipt_events(self, receipt_id: str) -> tuple[ReceiptLifecycleEvent, ...]: ...
    def lifecycle_state_at(self, receipt_id: str, as_of: datetime) -> Optional[ReceiptLifecycleState]: ...

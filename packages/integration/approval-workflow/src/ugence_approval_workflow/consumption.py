"""``GRANTED -> CONSUMED``, exactly once.

Consumption is the only racing decision in this package, so it happens as a single
unique insert inside one write transaction — the shape the execution ledger uses for
its reservation head (``packages/integration/execution-reservation/.../sqlite.py``),
copied and never imported.

The consumption key is canonical over ``(tenant_id, approval_id, subject_digest,
consumer_ref)``, serialized ``approval_key.v1:<sha256hex>``, and projects neutrally
onto the governance-contracts idempotency family. ``consumer_ref`` is the free,
uninterpreted reference to whatever consumed the approval — for the Decision
Authority seam, the decision case and review task it cleared.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ugence_governance_contracts.api import (
    IdempotencyDisposition,
    IdempotencyKey,
    IdempotencyResolution,
    IdempotencyScope,
    ValidityStatus,
)

from ._canon import domain_digest, require_nonempty, require_tzaware
from .records import ApprovalRecord
from .states import CONSUMABLE_STATES, ApprovalState

__all__ = [
    "APPROVAL_KEY_PREFIX", "CONSUMPTION_ID_PREFIX", "ConsumptionKey", "ConsumptionResult",
    "ConsumeOutcome", "consumption_id_for", "validate_for_consumption",
]

APPROVAL_KEY_PREFIX = "approval_key.v1:"
CONSUMPTION_ID_PREFIX = "cns_"


@dataclass(frozen=True)
class ConsumptionKey:
    """The identity of one logical consumption of one approval."""

    tenant_id: str
    approval_id: str
    subject_digest: str
    consumer_ref: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "approval_id", "subject_digest", "consumer_ref"):
            object.__setattr__(self, name, require_nonempty(getattr(self, name), f"ConsumptionKey.{name}"))

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (self.tenant_id, self.approval_id, self.subject_digest, self.consumer_ref)

    def canonical_digest(self) -> str:
        return domain_digest("consumption_key", {
            "tenant_id": self.tenant_id, "approval_id": self.approval_id,
            "subject_digest": self.subject_digest, "consumer_ref": self.consumer_ref})

    @property
    def serialized(self) -> str:
        """``approval_key.v1:<sha256hex>`` — the ledger's unique consumption key."""

        return APPROVAL_KEY_PREFIX + self.canonical_digest()

    def to_idempotency_key(self) -> IdempotencyKey:
        """Neutral projection: GLOBAL scope, the tenant as the opaque partition."""

        return IdempotencyKey(key=self.serialized, scope=IdempotencyScope.GLOBAL,
                              partition=self.tenant_id)

    def neutral_idempotency_digest(self) -> str:
        return self.to_idempotency_key().canonical_digest()


def consumption_id_for(key: ConsumptionKey) -> str:
    """Deterministic id: no UUID, no clock."""

    return CONSUMPTION_ID_PREFIX + key.canonical_digest()[:32]


class ConsumptionResult(str, Enum):
    """What one ``consume`` call meant. Only ``CONSUMED_FIRST`` is a first use."""

    CONSUMED_FIRST = "CONSUMED_FIRST"
    ALREADY_CONSUMED = "ALREADY_CONSUMED"
    NOT_GRANTED = "NOT_GRANTED"
    EXPIRED_APPROVAL = "EXPIRED_APPROVAL"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ConsumeOutcome:
    """A typed result, never a bare boolean."""

    result: ConsumptionResult
    key: ConsumptionKey
    consumption_id: str = ""
    holder: str = ""
    reason: str = ""

    @property
    def is_consumed(self) -> bool:
        return self.result is ConsumptionResult.CONSUMED_FIRST

    @property
    def resolution(self) -> Optional[IdempotencyResolution]:
        """Neutral projection. Refusals are not resolutions and project to ``None``."""

        ik = self.key.to_idempotency_key()
        if self.result is ConsumptionResult.CONSUMED_FIRST:
            return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.FIRST)
        if self.result is ConsumptionResult.ALREADY_CONSUMED:
            return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.DUPLICATE,
                                         duplicate_of=self.holder)
        if self.result is ConsumptionResult.UNKNOWN:
            return IdempotencyResolution(key=ik, disposition=IdempotencyDisposition.UNKNOWN)
        return None


def validate_for_consumption(
    record: Optional[ApprovalRecord], key: ConsumptionKey, as_of: datetime,
) -> Optional[tuple[ConsumptionResult, str]]:
    """Pure rules over the immutable record. ``None`` means the record admits ``key``."""

    require_tzaware(as_of, "consume.as_of")
    if record is None:
        return ConsumptionResult.NOT_GRANTED, "no such approval"
    if record.tenant_id != key.tenant_id:
        return ConsumptionResult.SUBJECT_MISMATCH, "tenant mismatch"
    if record.approval_id != key.approval_id:
        return ConsumptionResult.SUBJECT_MISMATCH, "approval id mismatch"
    if record.subject_digest != key.subject_digest:
        return ConsumptionResult.SUBJECT_MISMATCH, (
            "the approved subject digest is not the one presented "
            "(the subject changed since approval)")
    if record.state is ApprovalState.CONSUMED:
        return ConsumptionResult.ALREADY_CONSUMED, "approval already consumed"
    if record.state not in CONSUMABLE_STATES:
        return ConsumptionResult.NOT_GRANTED, f"approval state is {record.state.value}"
    status = record.validity_status_at(as_of)
    if status is ValidityStatus.EXPIRED:
        return ConsumptionResult.EXPIRED_APPROVAL, "approval window has closed"
    if status is ValidityStatus.NOT_YET_VALID:
        return ConsumptionResult.NOT_GRANTED, "consumption instant precedes the approval window"
    return None

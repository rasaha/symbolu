"""ClearanceResult + the neutral immutable ClearanceReceipt body (design §12–13).

``ClearanceResult`` is the deterministic evaluator output: a pure function of the
request. It generates no nondeterministic UUID and reads no system clock.
``result_id = "acr_" + result_fingerprint``.

``ClearanceReceiptBody`` is the **neutral immutable body** the merged design assigns
to this package (the ``x-partition: evaluator`` fields, content-addressed). This
package defines the body only — it implements **no persistence** and **no lifecycle
mutation**. Lifecycle/storage metadata (``receipt_id``, wall-clock ``created_at``,
``lifecycle_state``, supersession) belong to the Workflow Service and are absent here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Tuple

from ..fingerprinting import clearance_result_fingerprint
from ..normalization import normalize_timestamp
from .enums import ClearanceStatus


@dataclass(frozen=True)
class ClearanceResult:
    """The deterministic clearance evaluation output."""

    request_id: str
    authorization_ref: str
    authorized_action_fingerprint: str
    status: ClearanceStatus
    reason_codes: Tuple[str, ...]
    effective_constraints: Tuple[str, ...]
    obligations: Tuple[str, ...]
    evaluated_at: datetime
    valid_until: datetime
    policy_refs: Tuple[str, ...]
    signal_refs: Tuple[str, ...]
    request_fingerprint: str
    tenant_id: str
    signal_bundle_fingerprint: str

    @property
    def result_fingerprint(self) -> str:
        """Content address over all fingerprinted result fields (self-excluded)."""
        return clearance_result_fingerprint({
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "authorization_ref": self.authorization_ref,
            "authorized_action_fingerprint": self.authorized_action_fingerprint,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),  # already canonically ordered
            "effective_constraints": list(self.effective_constraints),
            "obligations": list(self.obligations),
            "evaluated_at": normalize_timestamp(self.evaluated_at),
            "valid_until": normalize_timestamp(self.valid_until),
            "policy_refs": list(self.policy_refs),
            "signal_refs": list(self.signal_refs),
            "signal_bundle_fingerprint": self.signal_bundle_fingerprint,
            "request_fingerprint": self.request_fingerprint,
        })

    @property
    def result_id(self) -> str:
        return "acr_" + self.result_fingerprint

    @property
    def is_clear(self) -> bool:
        return self.status is ClearanceStatus.CLEAR


@dataclass(frozen=True)
class ClearanceReceiptBody:
    """Neutral immutable receipt body (content-addressed). NOT persisted here.

    This is the evaluator-partition projection the design assigns to this package.
    It contains no persistence or lifecycle-mutation behavior. The Workflow Service
    wraps this body with storage/lifecycle metadata and persists it — not this
    package.
    """

    receipt_version: str
    tenant_id: str
    request_id: str
    authorization_ref: str
    authorized_action_fingerprint: str
    clearance_status: ClearanceStatus
    reason_codes: Tuple[str, ...]
    effective_constraints: Tuple[str, ...]
    obligations: Tuple[str, ...]
    signal_refs: Tuple[str, ...]
    signal_bundle_fingerprint: str
    policy_refs: Tuple[str, ...]
    evaluated_at: datetime
    valid_until: datetime
    request_fingerprint: str
    result_fingerprint: str

    @property
    def receipt_id(self) -> str:
        """Content-addressed storage identity (a hash label, not the acronym)."""
        return "acr_" + self.result_fingerprint

    @classmethod
    def from_result(cls, result: ClearanceResult, *, receipt_version: str = "action_clearance.receipt.v1") -> "ClearanceReceiptBody":
        return cls(
            receipt_version=receipt_version,
            tenant_id=result.tenant_id,
            request_id=result.request_id,
            authorization_ref=result.authorization_ref,
            authorized_action_fingerprint=result.authorized_action_fingerprint,
            clearance_status=result.status,
            reason_codes=result.reason_codes,
            effective_constraints=result.effective_constraints,
            obligations=result.obligations,
            signal_refs=result.signal_refs,
            signal_bundle_fingerprint=result.signal_bundle_fingerprint,
            policy_refs=result.policy_refs,
            evaluated_at=result.evaluated_at,
            valid_until=result.valid_until,
            request_fingerprint=result.request_fingerprint,
            result_fingerprint=result.result_fingerprint,
        )


__all__ = ["ClearanceResult", "ClearanceReceiptBody"]

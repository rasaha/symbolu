"""The ``PRIOR_CONSUMPTION`` trusted signal — how Action Clearance learns what this
ledger knows.

Action Clearance never owns consumption; it *receives* a ``PRIOR_CONSUMPTION``
signal whose value is ``{"state": UNUSED | RESERVED | CONSUMED | UNKNOWN}`` and
fails closed on UNKNOWN. This module maps reservation head state to that
vocabulary (ratified mapping in the scoping ADR) and builds the signal with a
Level 1 provenance projection: trusted-ingestion digest plus adapter identity.
Level 2 (keyed envelope) is what enforcement needs and what no key service in the
repository can provide yet — decision D-4 keeps the enforcement gate closed.

Store unavailability maps to UNKNOWN *and* ``SignalStatus.UNKNOWN``: either alone
already fails closed in the evaluator; both together leave no ambiguity.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Protocol, runtime_checkable

from ugence_action_clearance import (
    ConsumptionStatus,
    SignalProvenance,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    TrustedSignal,
)

from ._canon import require_tzaware
from .execution_key import ExecutionKey
from .reservation import ExecutionReservation, ReservationState
from .version import __version__

__all__ = ["consumption_status_for", "build_consumption_signal", "PriorConsumptionSource",
           "ADAPTER_ID", "SOURCE_KIND"]

ADAPTER_ID = "ugence_execution_reservation"
SOURCE_KIND = "execution_reservation_ledger"

_MAPPING = {
    None: ConsumptionStatus.UNUSED,
    ReservationState.AVAILABLE: ConsumptionStatus.UNUSED,
    ReservationState.RELEASED: ConsumptionStatus.UNUSED,
    ReservationState.RECONCILED_FAILURE: ConsumptionStatus.UNUSED,
    ReservationState.RESERVED: ConsumptionStatus.RESERVED,
    ReservationState.DISPATCHED: ConsumptionStatus.RESERVED,
    ReservationState.OBSERVED_FAILURE: ConsumptionStatus.RESERVED,
    ReservationState.OUTCOME_UNCERTAIN: ConsumptionStatus.RESERVED,
    ReservationState.OBSERVED_SUCCESS: ConsumptionStatus.CONSUMED,
    ReservationState.RECONCILED_SUCCESS: ConsumptionStatus.CONSUMED,
}


def consumption_status_for(state: Optional[ReservationState]) -> ConsumptionStatus:
    return _MAPPING.get(state, ConsumptionStatus.UNKNOWN)


def build_consumption_signal(
    execution_key: ExecutionKey,
    head: Optional[ExecutionReservation],
    *,
    as_of: datetime,
    freshness_s: int,
    unavailable: bool,
    source_id: str,
    provenance_ref: str,
) -> TrustedSignal:
    require_tzaware(as_of, "consumption_signal.as_of")
    if unavailable:
        state = ConsumptionStatus.UNKNOWN
        status = SignalStatus.UNKNOWN
    else:
        # An abandoned pre-dispatch reservation is free again; report it as such.
        effective = None if head is not None and head.is_abandoned_at(as_of) else (
            head.state if head is not None else None)
        state = consumption_status_for(effective)
        status = SignalStatus.PRESENT
    value = {"state": state.value}
    if head is not None and not unavailable:
        value["reservation_id"] = head.reservation_id
    provenance = SignalProvenance(
        source_id=source_id,
        source_kind=SOURCE_KIND,
        ingestion_boundary="in-process",
        trust_level=SignalTrustLevel.LEVEL_1_TRUSTED_INGESTION,
        provenance_ref=provenance_ref,
        adapter_id=ADAPTER_ID,
        adapter_version=__version__,
    )
    signal = TrustedSignal(
        signal_id=f"prior-consumption:{execution_key.canonical_digest()[:16]}",
        signal_type=SignalType.PRIOR_CONSUMPTION,
        tenant_id=execution_key.tenant_id,
        subject_ref=execution_key.target_ref,
        source_ref=source_id,
        source_kind=SOURCE_KIND,
        captured_at=as_of,
        status=status,
        value=value,
        provenance_ref=provenance_ref,
        valid_until=as_of + timedelta(seconds=freshness_s),
        integrity_digest=None,
        authorization_ref=execution_key.authorization_ref,
        action_fingerprint=execution_key.authorized_action_fingerprint,
        provenance=provenance,
    )
    # Level 1: the integrity digest is the content fingerprint computed at ingestion.
    return TrustedSignal(**{**signal.__dict__, "integrity_digest": signal.content_fingerprint})


@runtime_checkable
class PriorConsumptionSource(Protocol):
    def consumption_signal(self, execution_key: ExecutionKey, *, as_of: datetime,
                           freshness_s: int = 60) -> TrustedSignal: ...

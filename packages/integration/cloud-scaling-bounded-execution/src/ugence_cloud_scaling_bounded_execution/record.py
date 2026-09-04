"""The bounded execution record and the effect observation minted from it (ADR 5D, D-5)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_risk_authority_execution_assurance.contracts import (
    EXECUTION_ASSURANCE_SCHEMA_VERSION,
    EffectObservation,
)

from .errors import BoundedExecutionContractError
from .identifiers import PROVIDER_ID, RECORD_ID_PREFIX, RECORD_SCHEMA_VERSION

__all__ = ["RecordDisposition", "BoundedExecutionRecord", "BoundedExecutionRecordStore",
           "InMemoryBoundedExecutionRecordStore", "derive_record_id", "effect_observation_for"]


class RecordDisposition(str, Enum):
    DISPATCHED = "DISPATCHED"
    REPLAYED = "REPLAYED"


def derive_record_id(tenant_id: str, grant_id: str, dispatch_request_id: str) -> str:
    payload = "\n".join((tenant_id, grant_id, dispatch_request_id)).encode("utf-8")
    return RECORD_ID_PREFIX + hashlib.sha256(payload).hexdigest()


def _aware(value: object, name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise BoundedExecutionContractError(f"{name} must be a timezone-aware datetime")


@dataclass(frozen=True)
class BoundedExecutionRecord:
    """What one dispatch bound, did and observed. Aware instants; RA-8 correlation fields."""

    schema_version: str
    record_id: str
    tenant_id: str
    grant_id: str
    reservation_id: str
    execution_key: str
    target_scope_digest: str
    envelope_id: str
    authorized_action_digest: str
    request_digest: str
    attempt_id: str
    external_request_id: str
    effective_mode: str
    mode_reasons: tuple[str, ...]
    ops_outcome: str
    business_outcome: BusinessOutcome
    finality: Finality
    applied: bool
    pre_state: Optional[int]
    post_state: Optional[int]
    requested_magnitude: int
    dispatched_at: datetime
    observed_at: datetime
    receipt_hash: str
    denial_reason: Optional[str] = None
    disposition: RecordDisposition = RecordDisposition.DISPATCHED

    def __post_init__(self) -> None:
        if self.schema_version != RECORD_SCHEMA_VERSION:
            raise BoundedExecutionContractError(f"schema_version must be {RECORD_SCHEMA_VERSION!r}")
        _aware(self.dispatched_at, "dispatched_at")
        _aware(self.observed_at, "observed_at")
        if self.record_id != derive_record_id(self.tenant_id, self.grant_id, self.attempt_id):
            raise BoundedExecutionContractError("record_id does not derive from tenant, grant and attempt")
        for name in ("tenant_id", "grant_id", "reservation_id", "execution_key", "target_scope_digest",
                     "envelope_id", "authorized_action_digest", "request_digest", "attempt_id",
                     "external_request_id", "effective_mode", "ops_outcome", "receipt_hash"):
            if type(getattr(self, name)) is not str or not getattr(self, name).strip():
                raise BoundedExecutionContractError(f"BoundedExecutionRecord.{name} must be a non-blank str")
        if not isinstance(self.business_outcome, BusinessOutcome) or not isinstance(self.finality, Finality):
            raise BoundedExecutionContractError("business_outcome and finality must be the effect enums")
        if self.applied and self.effective_mode != "live":
            raise BoundedExecutionContractError("applied is true only for a LIVE dispatch")

    @property
    def workflow_instance_id(self) -> str:
        """RA-8's workflow instance: one reservation is one execution instance here."""

        return self.reservation_id


def effect_observation_for(record: BoundedExecutionRecord) -> EffectObservation:
    """The RA-8 observation minted from the record: same bindings, same outcome, same instant."""

    return EffectObservation(
        schema_version=EXECUTION_ASSURANCE_SCHEMA_VERSION,
        observation_id=record.record_id,
        tenant_id=record.tenant_id,
        workflow_instance_id=record.workflow_instance_id,
        envelope_id=record.envelope_id,
        authorized_action_digest=record.authorized_action_digest,
        attempt_id=record.attempt_id,
        external_request_id=record.external_request_id,
        business_outcome=record.business_outcome,
        provider=PROVIDER_ID,
        external_effect_id=record.receipt_hash,
        observed_parameters={
            "effective_mode": record.effective_mode,
            "ops_outcome": record.ops_outcome,
            "pre_state": "" if record.pre_state is None else str(record.pre_state),
            "post_state": "" if record.post_state is None else str(record.post_state),
            "requested_magnitude": str(record.requested_magnitude),
            "grant_id": record.grant_id,
            "reservation_id": record.reservation_id,
            "target_scope_digest": record.target_scope_digest,
        },
        observed_at=record.observed_at,
        finality=record.finality,
        source=PROVIDER_ID,
        source_version=RECORD_SCHEMA_VERSION,
    )


@runtime_checkable
class BoundedExecutionRecordStore(Protocol):
    @property
    def is_production_authoritative(self) -> bool: ...

    def save(self, record: BoundedExecutionRecord) -> None: ...

    def get(self, tenant_id: str, record_id: str) -> Optional[BoundedExecutionRecord]: ...


class InMemoryBoundedExecutionRecordStore:
    is_production_authoritative = False

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], BoundedExecutionRecord] = {}

    def save(self, record: BoundedExecutionRecord) -> None:
        if type(record) is not BoundedExecutionRecord:
            raise BoundedExecutionContractError("save requires a BoundedExecutionRecord")
        key = (record.tenant_id, record.record_id)
        if key in self._records and self._records[key].receipt_hash != record.receipt_hash:
            raise BoundedExecutionContractError(f"record {record.record_id!r} exists with another receipt")
        self._records[key] = record

    def get(self, tenant_id: str, record_id: str) -> Optional[BoundedExecutionRecord]:
        return self._records.get((tenant_id, record_id))

"""Append-only audit event contract.

An ``AuditEvent`` is an immutable record of something that happened: a record
creation, a workflow transition, or a denied policy action. Events are never
updated or deleted (the repository exposes append/read only). A ``payload_hash``
gives each event a deterministic content fingerprint, and ``correlation_id`` /
``causation_id`` let a full request chain be reconstructed. ``previous_event_hash``
is reserved so a cryptographic hash-chain can be layered on later without a
contract change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional

from pydantic import Field, model_validator

from ..common import utc_now
from ..errors import DomainValidationError
from ..base import DomainModel
from ..identity.actor import ActorType
from .events import AuditEventType


class AuditEvent(DomainModel):
    """One immutable entry in the append-only audit log."""

    event_id: str
    event_type: AuditEventType
    entity_type: str
    entity_id: str
    actor_type: ActorType
    actor_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=utc_now)
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    payload_hash: str = ""
    correlation_id: str
    causation_id: Optional[str] = None
    previous_event_hash: Optional[str] = None  # reserved for future hash-chaining
    metadata: Mapping[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> "AuditEvent":
        if not self.event_id.strip():
            raise DomainValidationError("event_id is required")
        if not self.entity_type.strip():
            raise DomainValidationError("entity_type is required")
        if not self.entity_id.strip():
            raise DomainValidationError("entity_id is required")
        if not self.correlation_id.strip():
            raise DomainValidationError("correlation_id is required")
        return self

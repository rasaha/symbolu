"""The hiring-owned, append-only, hash-chained domain audit event (H1).

Immutable. Each event carries a deterministic ``payload_hash`` and an
``event_hash`` computed over its identifying content *including*
``previous_event_hash`` — so the per-entity event stream is a tamper-evident
chain that reconstruction can verify. Modeled on the kernel ``AuditEvent`` but
kept hiring-owned (see :mod:`.events`).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from ugence_decision_authority.api.common import canonical_hash
from ugence_decision_authority.api.identity import ActorType

from ..common import utc_now
from ..domain.base import DomainModel
from ..errors import DomainValidationError
from .events import HiringDomainEventType


class HiringDomainAuditEvent(DomainModel):
    """One append-only hiring domain audit event."""

    event_id: str
    event_type: HiringDomainEventType
    entity_type: str
    entity_id: str
    tenant_id: str
    actor_id: str
    actor_type: ActorType
    timestamp: datetime = Field(default_factory=utc_now)
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    payload_hash: str = canonical_hash({})
    previous_event_hash: str = ""
    event_hash: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    entity_version: int = 0

    def _identity_content(self) -> dict:
        """Canonical, order-independent content the ``event_hash`` commits to."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "tenant_id": self.tenant_id,
            "actor_id": self.actor_id,
            "actor_type": self.actor_type.value,
            "timestamp": self.timestamp.isoformat(),
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "payload_hash": self.payload_hash,
            "previous_event_hash": self.previous_event_hash,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "entity_version": self.entity_version,
        }

    def compute_hash(self) -> str:
        """The deterministic hash of this event's identifying content."""
        return canonical_hash(self._identity_content())

    def with_hash(self) -> "HiringDomainAuditEvent":
        """Return a copy whose ``event_hash`` is set to the computed hash."""
        data = self.model_dump()
        data["event_hash"] = self.compute_hash()
        return type(self)(**data)

    def hash_is_valid(self) -> bool:
        """True iff the stored ``event_hash`` matches the recomputed content hash."""
        return bool(self.event_hash) and self.event_hash == self.compute_hash()

    def model_post_init(self, __context: object) -> None:  # pydantic hook
        for req in ("event_id", "entity_type", "entity_id", "tenant_id", "actor_id"):
            if not str(getattr(self, req)).strip():
                raise DomainValidationError(f"HiringDomainAuditEvent.{req} is required")

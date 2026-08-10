"""GovernanceEvent — append-only audit lineage (spec §23, user brief §23).

Every state-changing operation emits one of these from day one; auditability is
not bolted on at the end. Events carry a ``payload_digest`` (not the payload)
so the lineage is tamper-evident without duplicating potentially sensitive
content, and an optional ``prev_digest`` to chain events per aggregate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional

from ..crypto.hashing import digest
from .enums import GovernanceEventType

__all__ = ["GovernanceEvent", "make_event"]


@dataclass(frozen=True)
class GovernanceEvent:
    event_id: str
    tenant_id: str
    event_type: GovernanceEventType
    aggregate_id: str
    actor: str
    timestamp: datetime
    correlation_id: str = ""
    payload_digest: str = ""
    prev_digest: Optional[str] = None
    attributes: Mapping[str, str] = field(default_factory=dict)


def make_event(
    *,
    event_id: str,
    tenant_id: str,
    event_type: GovernanceEventType,
    aggregate_id: str,
    actor: str,
    timestamp: datetime,
    payload: Any = None,
    correlation_id: str = "",
    prev_digest: Optional[str] = None,
    attributes: Optional[Mapping[str, str]] = None,
) -> GovernanceEvent:
    """Construct an event, digesting ``payload`` for the tamper-evident field."""

    return GovernanceEvent(
        event_id=event_id,
        tenant_id=tenant_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        actor=actor,
        timestamp=timestamp,
        correlation_id=correlation_id,
        payload_digest=digest(payload) if payload is not None else "",
        prev_digest=prev_digest,
        attributes=dict(attributes or {}),
    )

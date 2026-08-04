"""Structured audit events and secret redaction.

Every attempted action — including denials — emits a structured event. Secrets
(tokens, credentials, private keys, secret-bearing headers) must never be recorded.
The in-memory reference sink is not a durable production audit store.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Keys whose values must never be persisted verbatim.
_SECRET_KEY_RE = re.compile(
    r"(token|secret|password|passwd|authorization|api[-_]?key|private[-_]?key|"
    r"bearer|credential|kubeconfig|cookie)", re.IGNORECASE)
_BEARER_RE = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+")


def redact(value: Any) -> Any:
    """Recursively redact secret-bearing keys/values."""
    if isinstance(value, dict):
        return {k: ("<redacted>" if _SECRET_KEY_RE.search(str(k)) else redact(v))
                for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _BEARER_RE.sub("Bearer <redacted>", value)
    return value


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    timestamp: float
    tenant_id: str
    actor_id: str
    authorization_id: Optional[str]
    decision_id: Optional[str]
    recommendation_id: str
    target: str
    requested_action: str
    authorized_bounds: Optional[str]
    execution_mode: str
    pre_state: Optional[int]
    post_state: Optional[int]
    result: str
    denial_reason: Optional[str]
    retry_count: int
    rollback_reference: Optional[str]
    package_version: str
    source_revision: Optional[str]
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["extra"] = redact(d.get("extra", {}))
        return d


@runtime_checkable
class AuditSink(Protocol):
    def emit(self, event: AuditEvent) -> None:
        ...


class InMemoryAuditSink:
    """Reference audit sink (NOT durable; process-local)."""

    def __init__(self):
        self.events: List[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)

    def reset(self) -> None:
        self.events.clear()


class AuditSinkError(Exception):
    """Raised when a required audit sink fails in LIVE mode (never silently dropped)."""


__all__ = ["AuditEvent", "AuditSink", "InMemoryAuditSink", "AuditSinkError", "redact"]

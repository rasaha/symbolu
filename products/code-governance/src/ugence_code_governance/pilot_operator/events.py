"""Immutable pilot security-event + kill-switch records.

A security event never contains an actual credential; critical events drive the
configured pause/stop/abort behavior. The kill switch is a durable state that,
when active, prevents any new adapter call or evaluation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Tuple

from ..fingerprints import domain_hash

DOMAIN_SECURITY_EVENT = "cg.pilot_operator.security_event.v1"
DOMAIN_KILL_SWITCH = "cg.pilot_operator.kill_switch.v1"


class SecurityEventKind(str, Enum):
    READ_ONLY_BOUNDARY_VIOLATION = "READ_ONLY_BOUNDARY_VIOLATION"
    CREDENTIAL_LEAK_TEST_FAILURE = "CREDENTIAL_LEAK_TEST_FAILURE"
    UNAPPROVED_HOST = "UNAPPROVED_HOST"
    UNAPPROVED_ENDPOINT = "UNAPPROVED_ENDPOINT"
    WRITE_PERMISSION_DETECTED = "WRITE_PERMISSION_DETECTED"
    CONFIG_INTEGRITY_MISMATCH = "CONFIG_INTEGRITY_MISMATCH"
    ADAPTER_IDENTITY_MISMATCH = "ADAPTER_IDENTITY_MISMATCH"
    STORE_INTEGRITY_FAILURE = "STORE_INTEGRITY_FAILURE"
    UNEXPECTED_EXECUTION_SYMBOL = "UNEXPECTED_EXECUTION_SYMBOL"


#: Critical security events that must trigger an abort.
CRITICAL_SECURITY_EVENTS = frozenset({
    SecurityEventKind.CREDENTIAL_LEAK_TEST_FAILURE,
    SecurityEventKind.WRITE_PERMISSION_DETECTED,
    SecurityEventKind.READ_ONLY_BOUNDARY_VIOLATION,
    SecurityEventKind.UNEXPECTED_EXECUTION_SYMBOL,
    SecurityEventKind.STORE_INTEGRITY_FAILURE,
})


@dataclass(frozen=True)
class PilotSecurityEvent:
    """An immutable pilot security event (never contains a credential value)."""

    pilot_id: str
    tenant_id: str
    kind: SecurityEventKind
    detail: str
    occurred_at: str
    correlation: str = ""

    @property
    def is_critical(self) -> bool:
        return self.kind in CRITICAL_SECURITY_EVENTS

    @property
    def event_fingerprint(self) -> str:
        return domain_hash(DOMAIN_SECURITY_EVENT, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id, "kind": self.kind.value,
            "detail": self.detail, "occurred_at": self.occurred_at, "correlation": self.correlation})

    @property
    def record_id(self) -> str:
        return f"pilot-security:{self.pilot_id}:{self.event_fingerprint[:16]}"


@dataclass(frozen=True)
class PilotKillSwitchState:
    """An immutable kill-switch state snapshot."""

    pilot_id: str
    tenant_id: str
    active: bool
    reason: str
    occurred_at: str

    @property
    def fingerprint(self) -> str:
        return domain_hash(DOMAIN_KILL_SWITCH, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id, "active": self.active,
            "reason": self.reason, "occurred_at": self.occurred_at})

    @property
    def record_id(self) -> str:
        return f"pilot-killswitch:{self.pilot_id}:{self.fingerprint[:16]}"


__all__ = ["SecurityEventKind", "CRITICAL_SECURITY_EVENTS", "PilotSecurityEvent",
           "PilotKillSwitchState"]

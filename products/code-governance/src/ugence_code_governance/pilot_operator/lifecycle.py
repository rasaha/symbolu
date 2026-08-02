"""Pilot lifecycle state machine + immutable run records.

Every transition is explicit and durably recorded; there is no automatic start
from DRAFT and no restart of a COMPLETED/ABORTED/INTEGRITY_FAILURE pilot. Run
records are append-only: each state change is a new immutable snapshot, never an
in-place mutation. Execution stays DISABLED.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Tuple

from ..fingerprints import domain_hash
from .errors import PilotLifecycleError

DOMAIN_PILOT_RUN = "cg.pilot_operator.run.v1"
DOMAIN_PILOT_LIFECYCLE_EVENT = "cg.pilot_operator.lifecycle_event.v1"


class PilotLifecycleStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    COMPLETED = "COMPLETED"
    ABORTED = "ABORTED"
    INTEGRITY_FAILURE = "INTEGRITY_FAILURE"


_TERMINAL = {PilotLifecycleStatus.COMPLETED, PilotLifecycleStatus.ABORTED,
             PilotLifecycleStatus.INTEGRITY_FAILURE}

_ALLOWED: Dict[PilotLifecycleStatus, frozenset] = {
    PilotLifecycleStatus.DRAFT: frozenset({PilotLifecycleStatus.READY}),
    PilotLifecycleStatus.READY: frozenset({PilotLifecycleStatus.ACTIVE}),
    PilotLifecycleStatus.ACTIVE: frozenset({PilotLifecycleStatus.PAUSED,
                                            PilotLifecycleStatus.STOPPING}),
    PilotLifecycleStatus.PAUSED: frozenset({PilotLifecycleStatus.ACTIVE,
                                            PilotLifecycleStatus.STOPPING}),
    PilotLifecycleStatus.STOPPING: frozenset({PilotLifecycleStatus.COMPLETED}),
    PilotLifecycleStatus.COMPLETED: frozenset(),
    PilotLifecycleStatus.ABORTED: frozenset(),
    PilotLifecycleStatus.INTEGRITY_FAILURE: frozenset(),
}


def can_transition(current: PilotLifecycleStatus, target: PilotLifecycleStatus) -> bool:
    """Return whether ``current -> target`` is a permitted transition."""
    if target is PilotLifecycleStatus.ABORTED:
        return current not in _TERMINAL  # abort any non-terminal active state
    if target is PilotLifecycleStatus.INTEGRITY_FAILURE:
        return True  # integrity failure can occur from any state
    return target in _ALLOWED.get(current, frozenset())


def assert_transition(current: PilotLifecycleStatus, target: PilotLifecycleStatus) -> None:
    if not can_transition(current, target):
        raise PilotLifecycleError(f"illegal lifecycle transition {current.value} -> {target.value}")


@dataclass(frozen=True)
class PilotLifecycleEvent:
    """An immutable, durably-recorded lifecycle transition."""

    pilot_id: str
    run_id: str
    tenant_id: str
    from_status: str
    to_status: str
    reason: str
    occurred_at: str

    @property
    def event_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PILOT_LIFECYCLE_EVENT, {
            "pilot_id": self.pilot_id, "run_id": self.run_id, "tenant_id": self.tenant_id,
            "from_status": self.from_status, "to_status": self.to_status,
            "reason": self.reason, "occurred_at": self.occurred_at})

    @property
    def record_id(self) -> str:
        return f"pilot-lifecycle:{self.run_id}:{self.event_fingerprint[:16]}"


@dataclass(frozen=True)
class PilotRunRecord:
    """An immutable snapshot of a pilot run's state (append-only history)."""

    pilot_id: str
    run_id: str
    tenant_id: str
    config_fingerprint: str
    operator_invocation_ref: str
    status: str
    repository_scope: Tuple[str, ...]
    started_at: str
    ended_at: str = ""
    evaluations_attempted: int = 0
    evaluations_completed: int = 0
    last_evaluation_ref: str = ""
    last_report_ref: str = ""
    pause_reason: str = ""
    stop_reason: str = ""
    execution_status: str = "DISABLED"

    @property
    def record_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PILOT_RUN, {
            "pilot_id": self.pilot_id, "run_id": self.run_id, "tenant_id": self.tenant_id,
            "config_fingerprint": self.config_fingerprint,
            "operator_invocation_ref": self.operator_invocation_ref, "status": self.status,
            "repository_scope": sorted(self.repository_scope), "started_at": self.started_at,
            "ended_at": self.ended_at, "evaluations_attempted": self.evaluations_attempted,
            "evaluations_completed": self.evaluations_completed,
            "last_evaluation_ref": self.last_evaluation_ref, "last_report_ref": self.last_report_ref,
            "pause_reason": self.pause_reason, "stop_reason": self.stop_reason,
            "execution_status": self.execution_status})

    @property
    def record_id(self) -> str:
        return f"pilot-run:{self.run_id}:{self.record_fingerprint[:16]}"

    def with_status(self, status: PilotLifecycleStatus, **changes) -> "PilotRunRecord":
        from dataclasses import replace
        return replace(self, status=status.value, **changes)


__all__ = [
    "PilotLifecycleStatus", "can_transition", "assert_transition",
    "PilotLifecycleEvent", "PilotRunRecord",
]

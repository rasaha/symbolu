"""
Rollback Monitor Adapter — Pre-action signal snapshot for post-action monitoring.

Phase S5-safety: Lifecycle-preparatory rollback monitoring hook.

This adapter captures a pre-action signal snapshot at authorize-time and
registers a RollbackWatch with the RollbackMonitor. The watch can later
be checked with post-action signals to detect degradation.

IMPORTANT — HONEST LIMITATIONS:
  This is a lifecycle-preparatory integration. GovernanceService is
  authorize-only; there is NO post-action execution callback. The
  adapter captures the pre-action snapshot and starts the watch, but
  the actual check() call must be made by an external caller that has
  access to post-action signal values. Automatic rollback requires an
  execution lifecycle that does not yet exist.

Fail-safe: No monitor → no snapshot, no effect. Watch starts but never
checked → expires naturally (EXPIRED verdict after watch_window_seconds).

This adapter does NOT influence the governance decision: no confidence
penalty, no escalation bias. It is purely an audit/observability hook.

OLM mapping: O12_ABSOLVING (termination boundary), O11_INTEGRATION (audit)

STATUS: ACTIVE — Consumed by GovernanceService.authorize() (Phase S5-safety).
Captures pre-action signal snapshot into audit event when RollbackMonitor
is configured. Wired: 2026-04-04.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from agentic.safety.governance_patterns.rollback_monitor import (
    RollbackMonitor,
    RollbackWatch,
)


# ---------------------------------------------------------------------------
# Resolution dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RollbackSnapshotResolution:
    """Frozen resolution from rollback monitor snapshot capture.

    Attributes:
        watch_started: Whether a RollbackWatch was started.
        decision_id: The governance decision ID for this watch.
        agent_id: Agent that requested the action.
        action_type: The action being evaluated.
        pre_action_signals: Signal snapshot captured at authorize-time.
        watch_id: Opaque reference to the watch (decision_id if started).
        available: True if a RollbackMonitor was provided.
        source_detail: Provenance description.
    """
    watch_started: bool
    decision_id: str
    agent_id: str
    action_type: str
    pre_action_signals: Dict[str, float]
    watch_id: Optional[str]
    available: bool
    source_detail: str

    def to_audit_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for audit events."""
        return {
            "watch_started": self.watch_started,
            "decision_id": self.decision_id,
            "agent_id": self.agent_id,
            "action_type": self.action_type,
            "pre_action_signals": dict(self.pre_action_signals),
            "watch_id": self.watch_id,
            "available": self.available,
            "source_detail": self.source_detail,
        }


# ---------------------------------------------------------------------------
# Resolve function
# ---------------------------------------------------------------------------

def resolve_rollback_snapshot(
    *,
    monitor: Optional[RollbackMonitor],
    decision_id: str,
    agent_id: str,
    action_type: str,
    confidence: float = 0.0,
    plasticity: Optional[float] = None,
    coherence: Optional[float] = None,
    readiness_status: Optional[str] = None,
) -> RollbackSnapshotResolution:
    """Capture a pre-action signal snapshot and start a rollback watch.

    Args:
        monitor: RollbackMonitor instance (None = no monitoring).
        decision_id: Governance decision ID for traceability.
        agent_id: Requesting agent.
        action_type: Proposed action type.
        confidence: Effective confidence score at decision time.
        plasticity: Plasticity gate value (from S2), if available.
        coherence: Core coherence score (from C2), if available.
        readiness_status: Readiness status string (from S3), if available.

    Returns:
        Frozen RollbackSnapshotResolution with watch metadata.
    """
    if monitor is None:
        return RollbackSnapshotResolution(
            watch_started=False,
            decision_id=decision_id,
            agent_id=agent_id,
            action_type=action_type,
            pre_action_signals={},
            watch_id=None,
            available=False,
            source_detail="no_rollback_monitor",
        )

    # Build pre-action signal snapshot from available governance signals
    pre_action_signals: Dict[str, float] = {
        "confidence": confidence,
    }
    if plasticity is not None:
        pre_action_signals["plasticity"] = plasticity
    if coherence is not None:
        pre_action_signals["coherence"] = coherence
    # governance_strength is a synthetic aggregate of available signals
    signal_count = sum(
        1 for v in (plasticity, coherence)
        if v is not None
    )
    if signal_count > 0:
        avg = sum(
            v for v in (plasticity, coherence)
            if v is not None
        ) / signal_count
        pre_action_signals["governance_strength"] = round(avg, 4)

    # Start watch (registers with the monitor)
    watch = monitor.start_watch(
        decision_id=decision_id,
        agent_id=agent_id,
        action_type=action_type,
        pre_action_signals=pre_action_signals,
    )

    return RollbackSnapshotResolution(
        watch_started=True,
        decision_id=decision_id,
        agent_id=agent_id,
        action_type=action_type,
        pre_action_signals=dict(pre_action_signals),
        watch_id=decision_id,
        available=True,
        source_detail="rollback_monitor:watch_started",
    )

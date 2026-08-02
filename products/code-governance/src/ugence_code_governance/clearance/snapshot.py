"""Supplied, offline operational-signal boundary.

``CodeGovernanceOperationalSnapshot`` is an already-captured, normalized snapshot
of operational facts. Code Governance implements **no** live clients (identity /
incident / change-management / GitHub / CI / cloud / DB / Kubernetes / HR); the
caller supplies the snapshot. Each present fact maps to exactly one canonical
Action Clearance ``SignalType``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ugence_action_clearance import ConsumptionStatus  # type: ignore


@dataclass(frozen=True)
class CodeGovernanceOperationalSnapshot:
    """An immutable, supplied snapshot of current operational facts.

    Every fact is optional; only present facts become signals. ``captured_at`` and
    ``valid_until`` are caller-supplied (no clock read).
    """

    captured_at: datetime
    valid_until: datetime

    # AUTHORIZATION_VALIDITY: "VALID" | "INVALID" | "STALE"
    authorization_validity: Optional[str] = None
    # ACTOR_STATUS: "ACTIVE" | "DISABLED" | "UNKNOWN"
    actor_state: Optional[str] = None
    # ARTIFACT_IDENTITY: the current artifact/action fingerprint + optional target
    artifact_action_fingerprint: Optional[str] = None
    artifact_target_ref: Optional[str] = None
    # POLICY_VALIDITY
    policy_accepted: Optional[bool] = None
    # CHANGE_FREEZE
    change_freeze_active: Optional[bool] = None
    # ACTIVE_INCIDENT
    incident_active: Optional[bool] = None
    # TARGET_AVAILABILITY
    target_available: Optional[bool] = None
    # REQUIRED_CONTROL
    required_control_satisfied: Optional[bool] = None
    # PRIOR_CONSUMPTION: a ConsumptionStatus value ("UNUSED"/"RESERVED"/"CONSUMED"/"UNKNOWN")
    consumption_state: Optional[str] = None
    # signal liveness: facts marked here are reported with SignalStatus.UNKNOWN
    unknown_facts: tuple = ()


__all__ = ["CodeGovernanceOperationalSnapshot"]

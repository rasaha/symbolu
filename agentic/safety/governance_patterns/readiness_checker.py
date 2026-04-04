"""
Agentic Readiness Checker — Multi-criterion gate before agent action.

Evaluates whether the agent system is ready to act by checking:
  1. Plasticity above minimum (system is open to change)
  2. Sufficient time since last action (cooldown respected)
  3. No pending escalations blocking action

Returns READY, NOT_READY, or DEGRADED with a human-readable reason.

OLM mapping: O9_WITNESSES (observation), O7_REASONING (admissibility)

Pattern extracted from cloud_controller.action.readiness.ReadinessChecker,
rewritten for AI agent governance (no K8s dependencies).

STATUS: ACTIVE — Consumed by readiness_adapter.py (Phase S3-safety).
GovernanceService.authorize() feeds plasticity (S2) and coherence/escalation
signals into this checker and uses the readiness status for bounded
confidence penalty and escalation bias. Wired: 2026-04-04.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ReadinessStatus(enum.Enum):
    """Readiness state of the governance system."""
    READY = "ready"
    NOT_READY = "not_ready"
    DEGRADED = "degraded"


@dataclass(frozen=True)
class ReadinessConfig:
    """Readiness thresholds.

    Attributes:
        min_plasticity: Minimum plasticity gate value to be READY.
        min_time_since_action_seconds: Cooldown between actions.
        block_during_escalations: Block if escalations are pending.
    """
    min_plasticity: float = 0.3
    min_time_since_action_seconds: float = 120.0
    block_during_escalations: bool = True


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of a readiness evaluation.

    Attributes:
        status: READY, NOT_READY, or DEGRADED.
        ready: Convenience bool (True if READY).
        plasticity: Current plasticity gate value.
        stability: Current system stability signal.
        reason: Human-readable explanation of the status.
        last_action_age_seconds: Seconds since last action (None if never).
        pending_escalations: Number of pending escalations.
        timestamp: Evaluation timestamp.
    """
    status: ReadinessStatus
    ready: bool
    plasticity: float
    stability: float
    reason: str
    last_action_age_seconds: Optional[float]
    pending_escalations: int
    timestamp: float

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "ready": self.ready,
            "plasticity": self.plasticity,
            "stability": self.stability,
            "reason": self.reason,
            "last_action_age_seconds": self.last_action_age_seconds,
            "pending_escalations": self.pending_escalations,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Checker
# ---------------------------------------------------------------------------

class ReadinessChecker:
    """Evaluates multi-criterion readiness before agent action.

    Usage::

        checker = ReadinessChecker()
        result = checker.check(
            plasticity=0.6,
            stability=0.8,
            last_action_time=time.time() - 200,
            pending_escalations=0,
        )
        if result.ready:
            proceed_with_action()
    """

    def __init__(self, config: Optional[ReadinessConfig] = None) -> None:
        self.config = config or ReadinessConfig()

    def check(
        self,
        plasticity: float,
        stability: float,
        *,
        last_action_time: Optional[float] = None,
        pending_escalations: int = 0,
        current_time: Optional[float] = None,
    ) -> ReadinessResult:
        """Evaluate readiness to act."""
        now = current_time if current_time is not None else time.time()
        cfg = self.config

        status = ReadinessStatus.READY
        reasons: list[str] = []

        # 1. Plasticity gate
        if plasticity < cfg.min_plasticity:
            status = ReadinessStatus.NOT_READY
            reasons.append(
                f"plasticity {plasticity:.2f} < min {cfg.min_plasticity:.2f}"
            )

        # 2. Cooldown
        last_action_age: Optional[float] = None
        if last_action_time is not None:
            last_action_age = now - last_action_time
            if last_action_age < cfg.min_time_since_action_seconds:
                status = ReadinessStatus.NOT_READY
                reasons.append(
                    f"cooldown: {last_action_age:.0f}s < "
                    f"min {cfg.min_time_since_action_seconds:.0f}s"
                )

        # 3. Pending escalations
        if cfg.block_during_escalations and pending_escalations > 0:
            if status == ReadinessStatus.READY:
                status = ReadinessStatus.DEGRADED
            reasons.append(
                f"{pending_escalations} pending escalation(s)"
            )

        reason = "; ".join(reasons) if reasons else "all checks passed"

        return ReadinessResult(
            status=status,
            ready=status == ReadinessStatus.READY,
            plasticity=plasticity,
            stability=stability,
            reason=reason,
            last_action_age_seconds=last_action_age,
            pending_escalations=pending_escalations,
            timestamp=now,
        )

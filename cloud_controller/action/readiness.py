"""Readiness Endpoint — exposes controller readiness for ArgoCD pre-hooks.

Design doc reference: Stage 5, lines 584-586:
  "ArgoCD: controller exposes /api/readiness endpoint
   ArgoCD Sync pre-hook calls endpoint: if P_t < 0.3 -> block sync, return reason
   Operator sees: 'Deployment blocked: system stability 0.34...'"

This module provides a ReadinessChecker that evaluates whether the system
is in a state suitable for deployments. It does NOT run its own HTTP server —
it provides the logic that any HTTP framework (Flask, FastAPI, etc.) can call.

The checker considers:
  - Plasticity (P_t): Is the system open to change?
  - Recent scaling activity: Was there a scale event recently?
  - Active rollback watches: Are we monitoring a recent action?
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class ReadinessStatus(Enum):
    """Whether the system is ready for deployments."""
    READY = "ready"
    NOT_READY = "not_ready"
    DEGRADED = "degraded"      # Ready with caveats


@dataclass
class ReadinessConfig:
    """Configuration for readiness evaluation."""
    # Minimum plasticity to allow deployments
    min_plasticity: float = 0.3
    # Minimum time since last scaling action (seconds)
    min_time_since_action_seconds: float = 120.0
    # Whether active rollback watches block readiness
    block_during_rollback_watch: bool = True


@dataclass
class ReadinessResult:
    """Result of a readiness check — suitable for HTTP response."""
    status: ReadinessStatus
    ready: bool
    plasticity: float
    stability: float
    reason: str
    # Additional context for operators
    last_action_age_seconds: Optional[float] = None
    active_rollback_watches: int = 0
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        """Serialize for HTTP/JSON response."""
        return {
            "status": self.status.value,
            "ready": self.ready,
            "plasticity": round(self.plasticity, 3),
            "stability": round(self.stability, 3),
            "reason": self.reason,
            "last_action_age_seconds": (
                round(self.last_action_age_seconds, 1)
                if self.last_action_age_seconds is not None
                else None
            ),
            "active_rollback_watches": self.active_rollback_watches,
            "timestamp": self.timestamp,
        }


class ReadinessChecker:
    """Evaluates system readiness for deployments.

    Usage:
        checker = ReadinessChecker(config)
        result = checker.check(
            plasticity=0.25,
            stability=0.34,
            last_action_time=time.time() - 30,
            active_rollback_watches=1,
        )
        # result.ready = False
        # result.reason = "Plasticity 0.250 below threshold 0.300; ..."
    """

    def __init__(self, config: Optional[ReadinessConfig] = None):
        self.config = config or ReadinessConfig()

    def check(
        self,
        plasticity: float,
        stability: float,
        last_action_time: Optional[float] = None,
        active_rollback_watches: int = 0,
        current_time: Optional[float] = None,
    ) -> ReadinessResult:
        """Evaluate whether the system is ready for deployments.

        Args:
            plasticity: Current P_t value from plasticity gate.
            stability: Current R_t value (resistance/stability).
            last_action_time: Timestamp of last scaling action (None = no recent action).
            active_rollback_watches: Number of active rollback watches.
            current_time: Current timestamp (defaults to now).

        Returns:
            ReadinessResult with status and explanation.
        """
        if current_time is None:
            current_time = time.time()

        blockers = []

        # 1. Check plasticity
        if plasticity < self.config.min_plasticity:
            blockers.append(
                f"Plasticity {plasticity:.3f} below threshold "
                f"{self.config.min_plasticity:.3f}"
            )

        # 2. Check time since last action
        action_age = None
        if last_action_time is not None:
            action_age = current_time - last_action_time
            if action_age < self.config.min_time_since_action_seconds:
                blockers.append(
                    f"Recent scaling action {action_age:.0f}s ago "
                    f"(min {self.config.min_time_since_action_seconds:.0f}s)"
                )

        # 3. Check active rollback watches
        if self.config.block_during_rollback_watch and active_rollback_watches > 0:
            blockers.append(
                f"{active_rollback_watches} active rollback watch(es) — "
                f"scaling outcome still being evaluated"
            )

        if blockers:
            status = ReadinessStatus.NOT_READY
            ready = False
            reason = "; ".join(blockers)
        else:
            status = ReadinessStatus.READY
            ready = True
            reason = (
                f"System ready: plasticity={plasticity:.3f}, "
                f"stability={stability:.3f}"
            )

        result = ReadinessResult(
            status=status,
            ready=ready,
            plasticity=plasticity,
            stability=stability,
            reason=reason,
            last_action_age_seconds=action_age,
            active_rollback_watches=active_rollback_watches,
            timestamp=current_time,
        )

        if not ready:
            logger.info("Readiness check: NOT_READY — %s", reason)

        return result

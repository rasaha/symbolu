"""Approval Manager — tracks recommendation lifecycle.

Each recommendation goes through:
  PENDING → APPROVED | DISMISSED | EXPIRED

Approved recommendations are passed to the action layer (Stage 5).
Recommendations expire after a configurable TTL to prevent stale actions.
"""

import time
import uuid
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from symbolu.cloud_controller.controller import ActionResult
from symbolu.cloud_controller.recommend.confidence import ConfidenceResult
from symbolu.cloud_controller.recommend.safety import SafetyResult

logger = logging.getLogger(__name__)


class ApprovalState(Enum):
    """Lifecycle state of a recommendation."""
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


@dataclass
class Recommendation:
    """A scaling recommendation awaiting human decision."""
    id: str
    created_at: float
    state: ApprovalState

    # What the controller recommends
    service: str
    namespace: str
    current_replicas: int
    original_delta: int      # Before safety clamping
    clamped_delta: int       # After safety bounds
    target_replicas: int

    # Scoring
    confidence: ConfidenceResult
    safety: SafetyResult
    action: ActionResult
    explanation: str

    # Resolution
    resolved_at: Optional[float] = None
    resolved_by: str = ""    # Who approved/dismissed (operator ID)
    resolve_reason: str = "" # Optional note from operator

    # Webhook tracking
    webhooks_sent: int = 0

    @property
    def is_pending(self) -> bool:
        return self.state == ApprovalState.PENDING

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    def format_summary(self) -> str:
        """Human-readable one-line summary."""
        direction = "OUT" if self.clamped_delta > 0 else "IN"
        return (
            f"[{self.id[:8]}] {self.service}: SCALE {direction} "
            f"{self.clamped_delta:+d} ({self.current_replicas}→{self.target_replicas}) "
            f"confidence={self.confidence.level.value} "
            f"state={self.state.value}"
        )


class ApprovalManager:
    """Manages the lifecycle of scaling recommendations.

    Thread-safe — all state mutations are protected by a lock.

    Usage:
        manager = ApprovalManager(ttl_seconds=600)
        rec = manager.create(service="api-gw", ...)
        manager.approve(rec.id, by="ops-team")
        manager.dismiss(rec.id, by="ops-team", reason="traffic spike ending")
    """

    def __init__(self, ttl_seconds: float = 600.0, max_history: int = 1000):
        self._ttl = ttl_seconds
        self._max_history = max_history
        self._recommendations: Dict[str, Recommendation] = {}
        self._history: List[Recommendation] = []
        self._lock = threading.Lock()

    def create(
        self,
        service: str,
        namespace: str,
        current_replicas: int,
        original_delta: int,
        clamped_delta: int,
        target_replicas: int,
        confidence: ConfidenceResult,
        safety: SafetyResult,
        action: ActionResult,
        explanation: str,
        webhooks_sent: int = 0,
    ) -> Recommendation:
        """Create a new pending recommendation.

        Returns:
            The created Recommendation.
        """
        rec = Recommendation(
            id=uuid.uuid4().hex[:12],
            created_at=time.time(),
            state=ApprovalState.PENDING,
            service=service,
            namespace=namespace,
            current_replicas=current_replicas,
            original_delta=original_delta,
            clamped_delta=clamped_delta,
            target_replicas=target_replicas,
            confidence=confidence,
            safety=safety,
            action=action,
            explanation=explanation,
            webhooks_sent=webhooks_sent,
        )

        with self._lock:
            self._recommendations[rec.id] = rec

        logger.info("Recommendation created: %s", rec.format_summary())
        return rec

    def approve(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Approve a pending recommendation.

        Returns:
            The approved Recommendation, or None if not found/not pending.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None:
                logger.warning("Approve failed: recommendation %s not found", recommendation_id)
                return None
            if rec.state != ApprovalState.PENDING:
                logger.warning(
                    "Approve failed: recommendation %s is %s, not pending",
                    recommendation_id, rec.state.value,
                )
                return None

            rec.state = ApprovalState.APPROVED
            rec.resolved_at = time.time()
            rec.resolved_by = by
            rec.resolve_reason = reason
            self._archive(rec)

        logger.info("Recommendation approved: %s by=%s", rec.id, by)
        return rec

    def dismiss(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Dismiss a pending recommendation.

        Returns:
            The dismissed Recommendation, or None if not found/not pending.
        """
        with self._lock:
            rec = self._recommendations.get(recommendation_id)
            if rec is None:
                logger.warning("Dismiss failed: recommendation %s not found", recommendation_id)
                return None
            if rec.state != ApprovalState.PENDING:
                logger.warning(
                    "Dismiss failed: recommendation %s is %s, not pending",
                    recommendation_id, rec.state.value,
                )
                return None

            rec.state = ApprovalState.DISMISSED
            rec.resolved_at = time.time()
            rec.resolved_by = by
            rec.resolve_reason = reason
            self._archive(rec)

        logger.info("Recommendation dismissed: %s by=%s reason=%s", rec.id, by, reason)
        return rec

    def expire_stale(self, current_time: float | None = None) -> List[Recommendation]:
        """Expire recommendations that exceeded TTL.

        Returns:
            List of newly expired recommendations.
        """
        if current_time is None:
            current_time = time.time()

        expired = []
        with self._lock:
            for rec in list(self._recommendations.values()):
                if rec.state != ApprovalState.PENDING:
                    continue
                if current_time - rec.created_at > self._ttl:
                    rec.state = ApprovalState.EXPIRED
                    rec.resolved_at = current_time
                    rec.resolve_reason = f"Expired after {self._ttl:.0f}s TTL"
                    expired.append(rec)
                    self._archive(rec)

        for rec in expired:
            logger.info("Recommendation expired: %s", rec.id)

        return expired

    def get(self, recommendation_id: str) -> Optional[Recommendation]:
        """Look up a recommendation by ID."""
        with self._lock:
            return self._recommendations.get(recommendation_id)

    @property
    def pending(self) -> List[Recommendation]:
        """All currently pending recommendations."""
        with self._lock:
            return [r for r in self._recommendations.values()
                    if r.state == ApprovalState.PENDING]

    @property
    def history(self) -> List[Recommendation]:
        """Resolved recommendations (approved, dismissed, expired)."""
        with self._lock:
            return list(self._history)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for r in self._recommendations.values()
                       if r.state == ApprovalState.PENDING)

    def _archive(self, rec: Recommendation) -> None:
        """Move resolved recommendation to history. Caller must hold lock."""
        self._history.append(rec)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]
        # Keep in active dict for lookups; will be cleaned on next expire_stale

    def reset(self) -> None:
        """Clear all state."""
        with self._lock:
            self._recommendations.clear()
            self._history.clear()

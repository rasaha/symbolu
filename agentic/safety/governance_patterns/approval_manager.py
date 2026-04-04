"""
Agentic Approval Manager — Human-in-the-loop lifecycle for governance decisions.

Manages the lifecycle of governance decisions that require human review:
    PENDING → APPROVED | DISMISSED | EXPIRED

Each decision records who resolved it, when, and why — providing a
complete audit trail for P54 compliance.

OLM mapping: O8_PURPOSE (constraint alignment), O9_WITNESSES (observation)

Pattern extracted from cloud_controller.recommend.approval.ApprovalManager,
rewritten for AI agent governance (no K8s dependencies).

DEPRECATED: Superseded by agentic.agentic_framework.approval_workflow which
provides a more complete lifecycle (6 states vs 4), ApprovalStore, and
richer ApprovalContext. Use approval_workflow.py for new integrations.
Audited: 2026-04-04 (S0 truthfulness cleanup)
"""

from __future__ import annotations

import enum
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ApprovalState(enum.Enum):
    """Lifecycle state of a governance decision."""
    PENDING = "pending"
    APPROVED = "approved"
    DISMISSED = "dismissed"
    EXPIRED = "expired"


@dataclass
class GovernanceDecision:
    """A governance decision awaiting or past human review.

    Attributes:
        id: Unique identifier.
        created_at: Unix timestamp of creation.
        state: Current lifecycle state.
        agent_id: Agent that triggered the decision.
        action_type: What the agent wants to do.
        action_detail: Serialisable payload describing the action.
        confidence: Confidence score from ConfidenceGate [0, 1].
        risk_level: Risk level from OLM bridge (LOW/MODERATE/HIGH/CRITICAL).
        explanation: Human-readable rationale for the proposed action.
        resolved_at: Timestamp of resolution (None if pending).
        resolved_by: Identifier of the human who resolved it.
        resolve_reason: Free-text reason for the resolution.
    """
    id: str
    created_at: float
    state: ApprovalState
    agent_id: str
    action_type: str
    action_detail: dict = field(default_factory=dict)
    confidence: float = 0.0
    risk_level: str = "MODERATE"
    explanation: str = ""
    resolved_at: Optional[float] = None
    resolved_by: str = ""
    resolve_reason: str = ""


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------

class ApprovalManager:
    """Manages human-in-the-loop approval for governance decisions.

    Thread-safe.  Decisions auto-expire after *ttl* seconds.

    Usage::

        mgr = ApprovalManager(ttl=300.0)
        decision = mgr.create("agent-7", "deploy_model", confidence=0.65)
        # ... human reviews ...
        mgr.approve(decision.id, by="alice", reason="looks good")
    """

    def __init__(
        self,
        *,
        ttl: float = 600.0,
        max_history: int = 1000,
    ) -> None:
        self._ttl = ttl
        self._max_history = max_history
        self._pending: Dict[str, GovernanceDecision] = {}
        self._history: List[GovernanceDecision] = []
        self._lock = threading.Lock()

    # -- Creation ----------------------------------------------------------

    def create(
        self,
        agent_id: str,
        action_type: str,
        *,
        action_detail: Optional[dict] = None,
        confidence: float = 0.0,
        risk_level: str = "MODERATE",
        explanation: str = "",
    ) -> GovernanceDecision:
        """Create a new pending governance decision."""
        decision = GovernanceDecision(
            id=uuid.uuid4().hex[:12],
            created_at=time.time(),
            state=ApprovalState.PENDING,
            agent_id=agent_id,
            action_type=action_type,
            action_detail=action_detail or {},
            confidence=confidence,
            risk_level=risk_level,
            explanation=explanation,
        )
        with self._lock:
            self._pending[decision.id] = decision
        return decision

    # -- Resolution --------------------------------------------------------

    def approve(
        self,
        decision_id: str,
        *,
        by: str = "",
        reason: str = "",
    ) -> Optional[GovernanceDecision]:
        """Transition a PENDING decision to APPROVED."""
        return self._resolve(decision_id, ApprovalState.APPROVED, by, reason)

    def dismiss(
        self,
        decision_id: str,
        *,
        by: str = "",
        reason: str = "",
    ) -> Optional[GovernanceDecision]:
        """Transition a PENDING decision to DISMISSED."""
        return self._resolve(decision_id, ApprovalState.DISMISSED, by, reason)

    def expire_stale(
        self,
        current_time: Optional[float] = None,
    ) -> List[GovernanceDecision]:
        """Expire all pending decisions older than TTL."""
        now = current_time if current_time is not None else time.time()
        expired: List[GovernanceDecision] = []
        with self._lock:
            stale_ids = [
                did
                for did, d in self._pending.items()
                if (now - d.created_at) > self._ttl
            ]
            for did in stale_ids:
                d = self._pending.pop(did)
                d.state = ApprovalState.EXPIRED
                d.resolved_at = now
                d.resolve_reason = "TTL expired"
                self._archive(d)
                expired.append(d)
        return expired

    # -- Queries -----------------------------------------------------------

    def get(self, decision_id: str) -> Optional[GovernanceDecision]:
        with self._lock:
            return self._pending.get(decision_id)

    def pending_for_agent(self, agent_id: str) -> List[GovernanceDecision]:
        with self._lock:
            return [
                d for d in self._pending.values() if d.agent_id == agent_id
            ]

    @property
    def pending(self) -> List[GovernanceDecision]:
        with self._lock:
            return list(self._pending.values())

    @property
    def history(self) -> List[GovernanceDecision]:
        with self._lock:
            return list(self._history)

    @property
    def pending_count(self) -> int:
        with self._lock:
            return len(self._pending)

    def reset(self) -> None:
        with self._lock:
            self._pending.clear()
            self._history.clear()

    # -- Internals ---------------------------------------------------------

    def _resolve(
        self,
        decision_id: str,
        new_state: ApprovalState,
        by: str,
        reason: str,
    ) -> Optional[GovernanceDecision]:
        with self._lock:
            d = self._pending.pop(decision_id, None)
            if d is None:
                return None
            d.state = new_state
            d.resolved_at = time.time()
            d.resolved_by = by
            d.resolve_reason = reason
            self._archive(d)
            return d

    def _archive(self, decision: GovernanceDecision) -> None:
        """Move resolved decision to history (must hold lock)."""
        self._history.append(decision)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

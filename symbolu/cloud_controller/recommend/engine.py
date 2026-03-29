"""Recommend Engine — orchestrates the recommendation pipeline.

Wires together:
    Controller decision → Confidence check → Safety bounds →
    Webhook notification → Approval tracking

Each cycle:
1. Receive ActionResult from the controller (via shadow runner or pipeline)
2. Score confidence — skip if below threshold
3. Apply safety bounds — clamp delta, check cooldown
4. Send webhook notifications
5. Create pending recommendation for human approval
6. Expire stale recommendations

The engine does NOT execute actions — that's Stage 5.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from symbolu.cloud_controller.controller import ActionResult
from symbolu.cloud_controller.recommend.confidence import (
    ConfidenceConfig,
    ConfidenceScorer,
    ConfidenceResult,
)
from symbolu.cloud_controller.recommend.safety import (
    SafetyConfig,
    SafetyBounds,
    SafetyResult,
)
from symbolu.cloud_controller.recommend.webhook import (
    WebhookConfig,
    WebhookDispatcher,
)
from symbolu.cloud_controller.recommend.approval import (
    ApprovalManager,
    ApprovalState,
    Recommendation,
)

logger = logging.getLogger(__name__)


@dataclass
class RecommendConfig:
    """Configuration for the recommendation engine."""
    # Service and namespace for notifications
    service: str = "default-service"
    namespace: str = "default"
    # Sub-component configs
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    # Webhook targets
    webhooks: List[WebhookConfig] = field(default_factory=list)
    # Approval TTL (seconds)
    approval_ttl_seconds: float = 600.0


@dataclass
class RecommendCycleResult:
    """Result of one recommendation engine cycle."""
    # Confidence evaluation
    confidence: ConfidenceResult
    # Safety check (None if no recommendation)
    safety: Optional[SafetyResult] = None
    # Created recommendation (None if below threshold or in cooldown)
    recommendation: Optional[Recommendation] = None
    # Expired recommendations this cycle
    expired: List[Recommendation] = field(default_factory=list)
    # Whether recommendation was suppressed and why
    suppressed: bool = False
    suppress_reason: str = ""


class RecommendEngine:
    """Orchestrates the recommendation pipeline.

    Usage:
        engine = RecommendEngine(RecommendConfig(
            service="api-gateway",
            namespace="prod",
            webhooks=[WebhookConfig(target=WebhookTarget.SLACK, url="...")],
        ))
        result = engine.evaluate(action, current_replicas=5)
        # result.recommendation is set if confidence + safety passed

    Approval:
        engine.approve("rec-id-123", by="ops-team")
        engine.dismiss("rec-id-456", by="ops-team", reason="false alarm")
    """

    def __init__(self, config: RecommendConfig | None = None):
        self.config = config or RecommendConfig()
        self.scorer = ConfidenceScorer(self.config.confidence)
        self.safety = SafetyBounds(self.config.safety)
        self.dispatcher = WebhookDispatcher(self.config.webhooks)
        self.approvals = ApprovalManager(
            ttl_seconds=self.config.approval_ttl_seconds,
        )

    def evaluate(
        self,
        action: ActionResult,
        current_replicas: int,
    ) -> RecommendCycleResult:
        """Evaluate a controller decision and potentially create a recommendation.

        Args:
            action: Controller's ActionResult.
            current_replicas: Current replica count.

        Returns:
            RecommendCycleResult with confidence, safety, and recommendation.
        """
        # 1. Expire stale recommendations
        expired = self.approvals.expire_stale()

        # 2. Score confidence
        confidence = self.scorer.evaluate(action)

        if not confidence.should_recommend:
            return RecommendCycleResult(
                confidence=confidence,
                expired=expired,
                suppressed=True,
                suppress_reason=confidence.reason,
            )

        # 3. Apply safety bounds
        safety = self.safety.check(
            current_replicas=current_replicas,
            proposed_delta=action.replica_delta,
        )

        # Suppress if in cooldown
        if safety.in_cooldown:
            return RecommendCycleResult(
                confidence=confidence,
                safety=safety,
                expired=expired,
                suppressed=True,
                suppress_reason=f"In cooldown ({safety.cooldown_remaining:.0f}s remaining)",
            )

        # Suppress if safety clamped to zero
        if safety.clamped_delta == 0:
            return RecommendCycleResult(
                confidence=confidence,
                safety=safety,
                expired=expired,
                suppressed=True,
                suppress_reason="Safety bounds reduced delta to zero",
            )

        # 4. Build explanation
        explanation = action.explain()

        # 5. Send webhooks
        webhooks_sent = self.dispatcher.send(
            service=self.config.service,
            namespace=self.config.namespace,
            current_replicas=current_replicas,
            recommended_delta=safety.clamped_delta,
            target_replicas=safety.target_replicas,
            confidence=confidence.level.value,
            signals=dict(action.metrics_snapshot),
            explanation=explanation,
            recommendation_id="pending",  # Updated after creation
        )

        # 6. Create recommendation
        rec = self.approvals.create(
            service=self.config.service,
            namespace=self.config.namespace,
            current_replicas=current_replicas,
            original_delta=action.replica_delta,
            clamped_delta=safety.clamped_delta,
            target_replicas=safety.target_replicas,
            confidence=confidence,
            safety=safety,
            action=action,
            explanation=explanation,
            webhooks_sent=webhooks_sent,
        )

        logger.info(
            "Recommendation created: %s (%+d replicas, %s confidence)",
            rec.id, safety.clamped_delta, confidence.level.value,
        )

        return RecommendCycleResult(
            confidence=confidence,
            safety=safety,
            recommendation=rec,
            expired=expired,
        )

    def approve(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Approve a pending recommendation.

        Records the action in safety bounds (starts cooldown).

        Returns:
            The approved Recommendation, or None if not found/not pending.
        """
        rec = self.approvals.approve(recommendation_id, by=by, reason=reason)
        if rec is not None:
            # Start cooldown period
            self.safety.record_action()
        return rec

    def dismiss(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
    ) -> Optional[Recommendation]:
        """Dismiss a pending recommendation."""
        return self.approvals.dismiss(recommendation_id, by=by, reason=reason)

    @property
    def pending(self) -> List[Recommendation]:
        return self.approvals.pending

    @property
    def pending_count(self) -> int:
        return self.approvals.pending_count

    def reset(self) -> None:
        """Reset all internal state."""
        self.approvals.reset()
        self.safety.reset()

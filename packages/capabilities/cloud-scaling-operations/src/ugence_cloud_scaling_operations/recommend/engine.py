"""Recommend Engine — orchestrates the recommendation pipeline.

Wires together:
    Controller decision → Confidence check → Safety bounds →
    Webhook notification → Approval tracking → Action execution

Each cycle:
1. Receive ActionResult from the controller (via shadow runner or pipeline)
2. Score confidence — skip if below threshold
3. Check for existing pending recommendation (dedup)
4. Apply safety bounds — clamp delta, check cooldown
5. Create pending recommendation for human approval
6. Send webhook notifications (with real recommendation ID)
7. Expire stale recommendations

On approval the engine records the decision and executes **nothing**
(ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING, D-1 and D-3): an
approved recommendation is input to the governed ladder — admission, reservation,
credential grant, bounded execution — never a mutation this engine performs. The
engine refuses a non-DRY_RUN ``ActuatorConfig`` at construction, whichever loop
builds it, so it can never hold a mutating actuator.

NOTE — Cooldown timing:
Cooldown starts when a recommendation is *approved*, so the same signal cannot be
re-approved in a burst. See SafetyBounds.record_action().
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ugence_cloud_scaling_controller.controller import ActionResult
from ugence_cloud_scaling_controller.recommend.confidence import (
    ConfidenceConfig,
    ConfidenceScorer,
    ConfidenceResult,
)
from ugence_cloud_scaling_controller.recommend.safety import (
    SafetyConfig,
    SafetyBounds,
    SafetyResult,
)
from ugence_cloud_scaling_operations.recommend.webhook import (
    WebhookConfig,
    WebhookDispatcher,
)
from ugence_cloud_scaling_operations.recommend.approval import (
    ApprovalManager,
    ApprovalState,
    Recommendation,
)
from ugence_cloud_scaling_operations.action.k8s_actuator import (
    ActuatorConfig,
    ActuatorMode,
    K8sActuator,
)
from ugence_cloud_scaling_operations.action.policy import (
    PolicyConfig,
    PolicyEngine,
)
from ugence_cloud_scaling_operations.action.rollback import (
    RollbackConfig,
    RollbackMonitor,
)
from ugence_cloud_scaling_operations.action.outcome import (
    OutcomeConfig,
    OutcomeTracker,
)
from ugence_cloud_scaling_operations.action.readiness import (
    ReadinessChecker,
    ReadinessConfig,
)
from ugence_cloud_scaling_operations.action.feedback import (
    FeedbackConfig,
    FeedbackLoop,
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
    # Actuator config. Only a DRY_RUN actuator is accepted (D-1); approval never
    # executes through it (D-3). It remains so a rollback watch can be wired to a
    # non-mutating scale function.
    actuator: Optional[ActuatorConfig] = None
    # Policy engine config (None = no policy checks)
    policy: Optional[PolicyConfig] = None
    # Rollback monitor config (None = no rollback monitoring)
    rollback: Optional[RollbackConfig] = None
    # Outcome tracker config (None = no outcome tracking)
    outcome: Optional[OutcomeConfig] = None
    # Readiness checker config (None = no readiness endpoint)
    readiness: Optional[ReadinessConfig] = None
    # Feedback loop config (None = no L6→L4 feedback)
    feedback: Optional[FeedbackConfig] = None


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


class MutatingActuatorRefused(RuntimeError):
    """The engine was asked to hold a non-DRY_RUN actuator (containment ruling D-1)."""


def _build_signals(action: ActionResult) -> Dict[str, Any]:
    """Build signals dict with both raw metrics and derived controller signals."""
    signals = dict(action.metrics_snapshot)
    # Add derived signals for operator context
    if action.coherence is not None:
        signals["coherence"] = action.coherence.coherence
    signals["stability"] = action.plasticity.resistance
    signals["plasticity"] = action.plasticity.plasticity
    signals["gain"] = action.gain.gain
    signals["damping"] = action.damping.damping
    return signals


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
        # HARD AUTHORITY GUARD (ADR orchestrator containment, D-1): the recommendation
        # engine can never hold a mutating actuator, whichever loop constructs it. The
        # orchestrator's auto-approve guard was the only line before this ruling; a
        # manual approve() with a SCALE_PATCH actuator reached the Kubernetes API with
        # no ExecutionAuthorization. Refused here, before any component is built.
        actuator_config = self.config.actuator
        if actuator_config is not None and actuator_config.mode is not ActuatorMode.DRY_RUN:
            raise MutatingActuatorRefused(
                f"RecommendEngine refuses actuator mode {actuator_config.mode.value!r}: "
                "a recommendation engine may not hold a mutating actuator. Live scaling "
                "is dispatched only through the governed ladder into "
                "ControlledScalingExecutor with an external ExecutionAuthorization; set "
                "the actuator to DRY_RUN or omit it."
            )
        self.scorer = ConfidenceScorer(self.config.confidence)
        self.safety = SafetyBounds(self.config.safety)
        self.dispatcher = WebhookDispatcher(self.config.webhooks)
        self.approvals = ApprovalManager(
            ttl_seconds=self.config.approval_ttl_seconds,
        )
        self.actuator = K8sActuator(self.config.actuator) if self.config.actuator else None
        self.policy = PolicyEngine(self.config.policy) if self.config.policy else None
        self.rollback = RollbackMonitor(
            self.config.rollback,
            rollback_fn=self.actuator.scale if self.actuator else None,
        ) if self.config.rollback else None
        self.outcome = OutcomeTracker(self.config.outcome) if self.config.outcome else None
        self.readiness = ReadinessChecker(self.config.readiness) if self.config.readiness else None
        self.feedback = FeedbackLoop(self.config.feedback) if self.config.feedback else None
        self._eval_lock = threading.Lock()

    def evaluate(
        self,
        action: ActionResult,
        current_replicas: int,
    ) -> RecommendCycleResult:
        """Evaluate a controller decision and potentially create a recommendation.

        Args:
            action: Controller's ActionResult.
            current_replicas: Current replica count (must be >= 1).

        Returns:
            RecommendCycleResult with confidence, safety, and recommendation.
        """
        # Guard invalid replica count
        if current_replicas < 1:
            logger.warning("current_replicas=%d < 1, clamping to 1", current_replicas)
            current_replicas = 1

        # Lock the entire evaluate path to prevent check-then-act races
        # (e.g. two threads both pass dedup check and create duplicate recs)
        with self._eval_lock:
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

            # 3. Deduplicate — skip if there's already a pending recommendation
            #    for this service to avoid flooding operators
            existing = self.approvals.pending_for_service(self.config.service)
            if existing:
                return RecommendCycleResult(
                    confidence=confidence,
                    expired=expired,
                    suppressed=True,
                    suppress_reason=f"Pending recommendation already exists: {existing[0].id}",
                )

            # 4. Apply safety bounds
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

            # 5. Build explanation and signals
            explanation = action.explain()
            signals = _build_signals(action)

            # 6. Create recommendation FIRST (so we have the real ID for webhooks)
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
            )

        # 7. Send webhooks OUTSIDE the lock — fire-and-forget in background
        #    thread to avoid blocking the polling loop with HTTP I/O
        self._send_webhooks_async(rec, current_replicas, safety, confidence, signals, explanation)

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

    def _send_webhooks_async(
        self,
        rec: Recommendation,
        current_replicas: int,
        safety: SafetyResult,
        confidence: ConfidenceResult,
        signals: Dict[str, Any],
        explanation: str,
    ) -> None:
        """Send webhook notifications in a background thread."""
        if not self.dispatcher.targets:
            return

        def _send():
            try:
                webhooks_sent = self.dispatcher.send(
                    service=self.config.service,
                    namespace=self.config.namespace,
                    current_replicas=current_replicas,
                    recommended_delta=safety.clamped_delta,
                    target_replicas=safety.target_replicas,
                    confidence=confidence.level.value,
                    signals=signals,
                    explanation=explanation,
                    recommendation_id=rec.id,
                )
                rec.webhooks_sent = webhooks_sent
                if webhooks_sent:
                    logger.info("Webhooks sent for %s: %d", rec.id, webhooks_sent)
            except Exception:
                logger.exception("Webhook dispatch failed for %s", rec.id)

        thread = threading.Thread(target=_send, daemon=True)
        thread.start()

    def approve(
        self,
        recommendation_id: str,
        by: str = "",
        reason: str = "",
        metrics_snapshot: Optional[Dict[str, float]] = None,
    ) -> Optional[Recommendation]:
        """Approve a pending recommendation. Nothing is executed.

        ADR orchestrator containment, D-3: approval records the human decision and
        returns the recommendation with ``execution_result`` left ``None``. No policy
        check, actuator call, rollback watch or outcome record follows, because each of
        those presumes an execution this engine may not perform. An approved
        recommendation is input to the governed ladder (admission, reservation,
        credential grant, bounded execution), never a mutation.

        The safety cooldown still starts, so the same signal cannot be re-approved in a
        burst. ``metrics_snapshot`` is accepted for signature compatibility and ignored.

        Returns:
            The approved Recommendation, or None if not found/not pending.
        """
        rec = self.approvals.approve(recommendation_id, by=by, reason=reason)
        if rec is None:
            return None
        rec.execution_result = None
        logger.info(
            "Approved %s by %s: recorded, nothing executed (authority is external)",
            rec.id, by or "-",
        )
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

    def check_rollbacks(
        self,
        current_metrics: Dict[str, float],
    ) -> list:
        """Check active rollback watches against current metrics.

        Call this each polling cycle when rollback monitoring is enabled.

        Returns:
            List of resolved RollbackWatch objects.
        """
        if self.rollback is None:
            return []
        return self.rollback.check(current_metrics)

    def evaluate_outcomes(
        self,
        current_metrics: Dict[str, float],
    ) -> list:
        """Evaluate pending outcome records against current metrics.

        Call this each polling cycle when outcome tracking is enabled.

        Returns:
            List of resolved OutcomeRecord objects.
        """
        if self.outcome is None:
            return []
        return self.outcome.evaluate(current_metrics)

    def check_readiness(
        self,
        plasticity: float,
        stability: float,
    ) -> Optional[dict]:
        """Check system readiness for deployments (ArgoCD pre-hook).

        Returns:
            Readiness result dict, or None if readiness checker not configured.
        """
        if self.readiness is None:
            return None
        return self.readiness.check(
            plasticity=plasticity,
            stability=stability,
            last_action_time=self.safety.last_action_time,
            active_rollback_watches=self.rollback.active_count if self.rollback else 0,
        ).to_dict()

    def process_feedback(
        self,
        controller,
        outcomes: Optional[list] = None,
        rollbacks: Optional[list] = None,
        divergences: Optional[list] = None,
    ) -> Optional[dict]:
        """Run L6 → L4 feedback loop to adjust controller parameters.

        Call this each polling cycle with resolved verdicts from
        check_rollbacks(), evaluate_outcomes(), and divergence tracker.

        Args:
            controller: The Controller instance whose parameters to adjust.
            outcomes: Resolved OutcomeRecords from evaluate_outcomes().
            rollbacks: Resolved RollbackWatches from check_rollbacks().
            divergences: Resolved DivergenceRecords from divergence tracker.

        Returns:
            FeedbackCycleResult summary dict, or None if feedback not configured.
        """
        if self.feedback is None:
            return None

        # Validate controller has expected attributes before adjustment
        for attr in ('adaptive_gain', 'damping', 'plasticity_gate'):
            if not hasattr(controller, attr):
                logger.warning(
                    "Controller missing %s attribute, skipping feedback", attr,
                )
                return None

        result = self.feedback.process(
            controller=controller,
            outcomes=outcomes,
            rollbacks=rollbacks,
            divergences=divergences,
        )

        # Feed high-value outcomes to replay buffer
        if outcomes and hasattr(controller, 'replay_buffer'):
            entries = self.feedback.to_replay_entries(outcomes)
            for entry in entries:
                controller.replay_buffer.store(entry, step=getattr(controller, '_step', 0))

        return {
            "signal": result.signal.value,
            "adjustments": len(result.adjustments),
            "applied": result.applied,
            "total_verdicts": result.total_verdicts,
            "skip_reason": result.skip_reason,
        }

    def reset(self) -> None:
        """Reset all internal state."""
        self.approvals.reset()
        self.safety.reset()
        if self.actuator is not None:
            self.actuator.reset()
        if self.policy is not None:
            self.policy.reset()
        if self.rollback is not None:
            self.rollback.reset()
        if self.outcome is not None:
            self.outcome.reset()
        if self.feedback is not None:
            self.feedback.reset()

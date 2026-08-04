"""Decision Log Formatter — structured audit trail for production observability.

Produces structured JSON log entries that capture the full lifecycle of a
scaling decision: controller recommendation → confidence → safety → approval →
execution → outcome → rollback → divergence → feedback. Each entry is
self-contained and designed for ingestion into ELK/Datadog/CloudWatch for
filtering, alerting, and trend analysis.

Usage:
    formatter = DecisionLogFormatter(service="api-gw", namespace="prod")

    # After recommend engine evaluation:
    entry = formatter.from_cycle(action, confidence, safety, current_replicas=5)
    logger.info(entry.to_json())

    # After approval + execution:
    entry = formatter.from_execution(rec_id, approved_by="ops", ...)
    logger.info(entry.to_json())

    # After approval/dismissal/expiry (without execution):
    entry = formatter.from_approval(rec_id, state="approved", by="ops")
    logger.info(entry.to_json())

    # After outcome verdict:
    entry = formatter.from_outcome(rec_id, verdict="positive")
    logger.info(entry.to_json())

    # After rollback verdict:
    entry = formatter.from_rollback(rec_id, verdict="rolled_back", ...)
    logger.info(entry.to_json())

    # After divergence evaluation:
    entry = formatter.from_divergence(divergence_type="...", verdict="...")
    logger.info(entry.to_json())

    # After feedback adjustment:
    entry = formatter.from_feedback(signal="boost", applied=True, ...)
    logger.info(entry.to_json())
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ugence_cloud_scaling_controller.controller import ActionResult
from ugence_cloud_scaling_controller.recommend.confidence import ConfidenceResult
from ugence_cloud_scaling_controller.recommend.safety import SafetyResult


class DecisionPhase(Enum):
    """Which phase of the decision lifecycle produced this entry."""
    RECOMMEND = "recommend"
    APPROVE = "approve"
    EXECUTE = "execute"
    OUTCOME = "outcome"
    ROLLBACK = "rollback"
    FEEDBACK = "feedback"
    DIVERGENCE = "divergence"


@dataclass
class DecisionLogEntry:
    """A single structured log entry for a scaling decision event."""
    phase: DecisionPhase
    timestamp: float
    service: str
    namespace: str

    # Optional fields populated per phase
    decision_id: str = ""
    step: int = 0

    # Controller decision
    recommendation: str = ""
    replica_delta: int = 0
    current_replicas: int = 0
    target_replicas: int = 0
    action_score: float = 0.0

    # Components
    pressure: float = 0.0
    coherence: float = 0.0
    plasticity: float = 0.0
    stability: float = 0.0
    gain: float = 0.0
    damping: float = 0.0
    identity_deviation: float = 0.0

    # Confidence
    confidence_level: str = ""
    confidence_score: float = 0.0

    # Safety
    was_clamped: bool = False
    clamp_reason: str = ""
    in_cooldown: bool = False

    # Approval / execution
    approved_by: str = ""
    approval_state: str = ""       # approved / dismissed / expired
    execution_mode: str = ""
    execution_success: Optional[bool] = None
    execution_error: str = ""

    # Suppression
    suppressed: bool = False
    suppress_reason: str = ""

    # Outcome / verdict
    verdict: str = ""
    verdict_reason: str = ""

    # Divergence (controller vs HPA)
    divergence_type: str = ""
    controller_delta: int = 0
    hpa_delta: int = 0

    # Feedback
    feedback_signal: str = ""
    feedback_applied: bool = False
    feedback_adjustments: int = 0

    # Metrics snapshot at decision time
    metrics: Dict[str, float] = field(default_factory=dict)

    # Freeform context
    explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict, omitting empty/default fields for compactness.

        Inclusion rules:
        - None is always excluded
        - Booleans: only included when True, or when the field semantically
          requires explicit False (execution_success, feedback_applied,
          suppressed, was_clamped, in_cooldown)
        - Numbers: excluded when 0 or 0.0
        - Strings: excluded when empty
        - Dicts: excluded when empty
        - Floats are rounded to 4 decimal places
        """
        d: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(
                self.timestamp, tz=timezone.utc,
            ).isoformat(),
            "phase": self.phase.value,
            "service": self.service,
            "namespace": self.namespace,
        }

        # Fields where False is a meaningful value that must be preserved
        _explicit_bool_fields = {
            "execution_success", "feedback_applied", "suppressed",
            "was_clamped", "in_cooldown",
        }

        _optional = {
            "decision_id": self.decision_id,
            "step": self.step,
            "recommendation": self.recommendation,
            "replica_delta": self.replica_delta,
            "current_replicas": self.current_replicas,
            "target_replicas": self.target_replicas,
            "action_score": self.action_score,
            "pressure": self.pressure,
            "coherence": self.coherence,
            "plasticity": self.plasticity,
            "stability": self.stability,
            "gain": self.gain,
            "damping": self.damping,
            "identity_deviation": self.identity_deviation,
            "confidence_level": self.confidence_level,
            "confidence_score": self.confidence_score,
            "was_clamped": self.was_clamped,
            "clamp_reason": self.clamp_reason,
            "in_cooldown": self.in_cooldown,
            "approved_by": self.approved_by,
            "approval_state": self.approval_state,
            "execution_mode": self.execution_mode,
            "execution_success": self.execution_success,
            "execution_error": self.execution_error,
            "suppressed": self.suppressed,
            "suppress_reason": self.suppress_reason,
            "verdict": self.verdict,
            "verdict_reason": self.verdict_reason,
            "divergence_type": self.divergence_type,
            "controller_delta": self.controller_delta,
            "hpa_delta": self.hpa_delta,
            "feedback_signal": self.feedback_signal,
            "feedback_applied": self.feedback_applied,
            "feedback_adjustments": self.feedback_adjustments,
            "metrics": self.metrics,
            "explanation": self.explanation,
        }
        for k, v in _optional.items():
            if v is None:
                continue
            if isinstance(v, bool):
                # For explicit-bool fields, include True and False
                # For other bools, only include True
                if v or k in _explicit_bool_fields:
                    d[k] = v
            elif isinstance(v, float):
                if v != 0.0:
                    d[k] = round(v, 4)
            elif isinstance(v, int):
                if v != 0:
                    d[k] = v
            elif isinstance(v, dict):
                if v:
                    d[k] = {
                        dk: round(dv, 4) if isinstance(dv, float) else dv
                        for dk, dv in v.items()
                    }
            elif isinstance(v, str):
                if v:
                    d[k] = v
            else:
                d[k] = v
        return d

    def to_json(self) -> str:
        """Serialize to compact JSON string for log output."""
        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_text(self) -> str:
        """Human-readable one-liner for console/file logs."""
        parts = [
            time.strftime("%H:%M:%S", time.localtime(self.timestamp)),
            self.phase.value.upper(),
            f"{self.service}/{self.namespace}",
        ]
        if self.decision_id:
            parts.append(f"id={self.decision_id[:8]}")
        if self.step:
            parts.append(f"step={self.step}")
        if self.recommendation:
            parts.append(self.recommendation)
        if self.replica_delta:
            parts.append(f"delta={self.replica_delta:+d}")
        if self.action_score:
            parts.append(f"A_t={self.action_score:.3f}")
        if self.confidence_level:
            parts.append(f"conf={self.confidence_level}")
        if self.approval_state:
            parts.append(f"state={self.approval_state}")
        if self.suppressed:
            parts.append(f"SUPPRESSED({self.suppress_reason})")
        if self.verdict:
            parts.append(f"verdict={self.verdict}")
        if self.divergence_type:
            parts.append(f"divergence={self.divergence_type}")
        if self.feedback_signal:
            parts.append(f"signal={self.feedback_signal}")
        if self.execution_success is not None:
            parts.append("OK" if self.execution_success else f"FAIL({self.execution_error})")
        return " | ".join(parts)


class DecisionLogFormatter:
    """Builds structured DecisionLogEntry objects from pipeline data.

    Designed for production use: each from_*() method produces a
    self-contained entry that can be serialized to JSON and shipped
    to any log aggregation backend.
    """

    def __init__(self, service: str, namespace: str = "default"):
        self.service = service
        self.namespace = namespace

    @staticmethod
    def _ts(timestamp: Optional[float]) -> float:
        return timestamp if timestamp is not None else time.time()

    def from_cycle(
        self,
        action: ActionResult,
        confidence: ConfidenceResult,
        safety: Optional[SafetyResult] = None,
        recommendation_id: str = "",
        current_replicas: int = 0,
        suppressed: bool = False,
        suppress_reason: str = "",
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from a recommend engine evaluation cycle."""
        coh = action.coherence.coherence if action.coherence else 0.0
        return DecisionLogEntry(
            phase=DecisionPhase.RECOMMEND,
            timestamp=self._ts(timestamp),
            service=self.service,
            namespace=self.namespace,
            decision_id=recommendation_id,
            step=action.step,
            recommendation=action.recommendation,
            replica_delta=safety.clamped_delta if safety else action.replica_delta,
            current_replicas=current_replicas,
            target_replicas=safety.target_replicas if safety else 0,
            action_score=action.action_score,
            pressure=action.pressure,
            coherence=coh,
            plasticity=action.plasticity.plasticity,
            stability=action.plasticity.resistance,
            gain=action.gain.gain,
            damping=action.damping.damping,
            identity_deviation=action.identity_deviation,
            confidence_level=confidence.level.value,
            confidence_score=confidence.action_score,
            was_clamped=safety.was_clamped if safety else False,
            clamp_reason=safety.clamp_reason if safety else "",
            in_cooldown=safety.in_cooldown if safety else False,
            suppressed=suppressed,
            suppress_reason=suppress_reason,
            metrics=dict(action.metrics_snapshot),
        )

    def from_approval(
        self,
        recommendation_id: str,
        state: str,
        by: str = "",
        current_replicas: int = 0,
        target_replicas: int = 0,
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from an approval, dismissal, or expiry event."""
        return DecisionLogEntry(
            phase=DecisionPhase.APPROVE,
            timestamp=self._ts(timestamp),
            service=self.service,
            namespace=self.namespace,
            decision_id=recommendation_id,
            current_replicas=current_replicas,
            target_replicas=target_replicas,
            replica_delta=target_replicas - current_replicas,
            approved_by=by,
            approval_state=state,
        )

    def from_execution(
        self,
        recommendation_id: str,
        approved_by: str,
        current_replicas: int,
        target_replicas: int,
        execution_mode: str = "",
        execution_success: Optional[bool] = None,
        execution_error: str = "",
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from an execution event (after approval)."""
        return DecisionLogEntry(
            phase=DecisionPhase.EXECUTE,
            timestamp=self._ts(timestamp),
            service=self.service,
            namespace=self.namespace,
            decision_id=recommendation_id,
            current_replicas=current_replicas,
            target_replicas=target_replicas,
            replica_delta=target_replicas - current_replicas,
            approved_by=approved_by,
            execution_mode=execution_mode,
            execution_success=execution_success,
            execution_error=execution_error,
        )

    def from_outcome(
        self,
        recommendation_id: str,
        verdict: str,
        verdict_reason: str = "",
        deployment: str = "",
        metrics: Optional[Dict[str, float]] = None,
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from an outcome verdict."""
        return DecisionLogEntry(
            phase=DecisionPhase.OUTCOME,
            timestamp=self._ts(timestamp),
            service=deployment or self.service,
            namespace=self.namespace,
            decision_id=recommendation_id,
            verdict=verdict,
            verdict_reason=verdict_reason,
            metrics=metrics or {},
        )

    def from_rollback(
        self,
        recommendation_id: str,
        verdict: str,
        deployment: str = "",
        pre_replicas: int = 0,
        post_replicas: int = 0,
        verdict_reason: str = "",
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from a rollback monitor verdict."""
        return DecisionLogEntry(
            phase=DecisionPhase.ROLLBACK,
            timestamp=self._ts(timestamp),
            service=deployment or self.service,
            namespace=self.namespace,
            decision_id=recommendation_id,
            current_replicas=pre_replicas,
            target_replicas=post_replicas,
            replica_delta=post_replicas - pre_replicas if pre_replicas else 0,
            verdict=verdict,
            verdict_reason=verdict_reason,
        )

    def from_divergence(
        self,
        divergence_type: str,
        verdict: str,
        controller_delta: int = 0,
        hpa_delta: int = 0,
        verdict_reason: str = "",
        metrics: Optional[Dict[str, float]] = None,
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from a controller-vs-HPA divergence evaluation."""
        return DecisionLogEntry(
            phase=DecisionPhase.DIVERGENCE,
            timestamp=self._ts(timestamp),
            service=self.service,
            namespace=self.namespace,
            divergence_type=divergence_type,
            verdict=verdict,
            verdict_reason=verdict_reason,
            controller_delta=controller_delta,
            hpa_delta=hpa_delta,
            metrics=metrics or {},
        )

    def from_feedback(
        self,
        signal: str,
        applied: bool,
        adjustments: int,
        total_verdicts: int = 0,
        skip_reason: str = "",
        timestamp: Optional[float] = None,
    ) -> DecisionLogEntry:
        """Build entry from a feedback loop cycle."""
        return DecisionLogEntry(
            phase=DecisionPhase.FEEDBACK,
            timestamp=self._ts(timestamp),
            service=self.service,
            namespace=self.namespace,
            feedback_signal=signal,
            feedback_applied=applied,
            feedback_adjustments=adjustments,
            suppress_reason=skip_reason,
            explanation=f"{total_verdicts} verdicts evaluated",
        )

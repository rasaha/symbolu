"""Confidence Scorer — determines recommendation confidence level.

A recommendation is only sent when both:
  - |action_score| exceeds the action threshold
  - coherence exceeds the coherence threshold

Confidence levels:
  LOW:    action barely crosses threshold, or coherence marginal
  MEDIUM: solid action score and coherence
  HIGH:   strong action score and high coherence (signals fully agree)
"""

import logging
from dataclasses import dataclass
from enum import Enum

from symbolu_core.cloud_controller.controller import ActionResult

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence classification for a recommendation."""
    NONE = "none"          # Below threshold — no recommendation
    LOW = "low"            # Marginal — recommend with caveats
    MEDIUM = "medium"      # Solid — standard recommendation
    HIGH = "high"          # Strong — high-confidence recommendation


@dataclass
class ConfidenceConfig:
    """Thresholds for confidence scoring."""
    # Minimum |action_score| to generate any recommendation
    action_threshold: float = 0.3
    # Minimum coherence to generate any recommendation
    coherence_threshold: float = 0.5
    # Boundaries between LOW/MEDIUM/HIGH
    medium_action_threshold: float = 0.5
    medium_coherence_threshold: float = 0.65
    high_action_threshold: float = 0.7
    high_coherence_threshold: float = 0.8


@dataclass
class ConfidenceResult:
    """Result of confidence evaluation."""
    level: ConfidenceLevel
    action_score: float
    coherence: float
    should_recommend: bool
    reason: str


class ConfidenceScorer:
    """Evaluates whether a controller decision warrants a recommendation."""

    def __init__(self, config: ConfidenceConfig | None = None):
        self.config = config or ConfidenceConfig()

    def evaluate(self, action: ActionResult) -> ConfidenceResult:
        """Score the confidence of a controller recommendation.

        Args:
            action: The controller's ActionResult.

        Returns:
            ConfidenceResult with level and whether to recommend.
        """
        score = abs(action.action_score)
        coherence = action.coherence.coherence if action.coherence else 0.0

        # No action = no recommendation
        if action.replica_delta == 0:
            return ConfidenceResult(
                level=ConfidenceLevel.NONE,
                action_score=score,
                coherence=coherence,
                should_recommend=False,
                reason="No scaling action recommended",
            )

        # Check minimum thresholds (strictly greater-than per spec)
        if score <= self.config.action_threshold:
            return ConfidenceResult(
                level=ConfidenceLevel.NONE,
                action_score=score,
                coherence=coherence,
                should_recommend=False,
                reason=f"Action score {score:.3f} at or below threshold "
                       f"{self.config.action_threshold}",
            )

        if coherence <= self.config.coherence_threshold:
            return ConfidenceResult(
                level=ConfidenceLevel.NONE,
                action_score=score,
                coherence=coherence,
                should_recommend=False,
                reason=f"Coherence {coherence:.2f} at or below threshold "
                       f"{self.config.coherence_threshold}",
            )

        # Determine level
        level = self._classify(score, coherence)

        return ConfidenceResult(
            level=level,
            action_score=score,
            coherence=coherence,
            should_recommend=True,
            reason=f"{level.value.upper()} confidence: score={score:.3f} "
                   f"coherence={coherence:.2f}",
        )

    def _classify(self, score: float, coherence: float) -> ConfidenceLevel:
        """Classify into LOW/MEDIUM/HIGH based on thresholds."""
        cfg = self.config

        if (score >= cfg.high_action_threshold
                and coherence >= cfg.high_coherence_threshold):
            return ConfidenceLevel.HIGH

        if (score >= cfg.medium_action_threshold
                and coherence >= cfg.medium_coherence_threshold):
            return ConfidenceLevel.MEDIUM

        return ConfidenceLevel.LOW

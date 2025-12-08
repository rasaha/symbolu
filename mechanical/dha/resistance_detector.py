"""
Resistance Detector Module (v3.0)
=================================

Detects and quantifies user resistance to insights and change.

Converts resistance_score and emotional_entropy from metadata into
categorical levels (HIGH/MEDIUM/LOW) for use by the tone selector.

Resistance indicates:
    - Defensive patterns against new information
    - Ego protection mechanisms
    - Avoidance of uncomfortable truths
"""

from typing import Dict, Any, List, Optional
from .adaptation_rules import (
    Level,
    resistance_score_to_level,
    extract_metadata_score,
    entropy_to_resistance_boost,
    clamp,
    RESISTANCE_HIGH_THRESHOLD,
    RESISTANCE_MEDIUM_THRESHOLD,
    ENTROPY_HIGH_THRESHOLD
)


class ResistanceDetector:
    """
    Detector for user resistance to insights.

    Analyzes multiple signals to determine resistance level:
        - Direct resistance score
        - Emotional entropy (chaos indicator)
        - Ego state markers
        - Historical patterns
    """

    def __init__(
        self,
        high_threshold: float = RESISTANCE_HIGH_THRESHOLD,
        medium_threshold: float = RESISTANCE_MEDIUM_THRESHOLD,
        entropy_weight: float = 0.3
    ):
        """
        Initialize ResistanceDetector.

        Args:
            high_threshold: Score threshold for HIGH resistance (default 0.7)
            medium_threshold: Score threshold for MEDIUM resistance (default 0.4)
            entropy_weight: Weight for emotional entropy in final score (default 0.3)
        """
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold
        self.entropy_weight = entropy_weight

    def detect(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Detect resistance from metadata.

        Args:
            metadata: Dictionary containing resistance_score, emotional_entropy, etc.

        Returns:
            Detection result with level, scores, and diagnostics
        """
        # Extract primary scores
        resistance_score = extract_metadata_score(
            metadata, "resistance_score", default=0.3
        )
        emotional_entropy = extract_metadata_score(
            metadata, "emotional_entropy", default=0.3
        )

        # Extract additional signals
        ego_state = metadata.get("ego_state", "neutral")

        # Calculate composite resistance score
        composite_score = self._calculate_composite_score(
            resistance_score,
            emotional_entropy,
            ego_state
        )

        # Detect specific resistance patterns
        patterns = self._detect_resistance_patterns(metadata)

        # Determine level
        level = self._score_to_level(composite_score)

        return {
            "resistance_level": level.value,
            "raw_resistance_score": resistance_score,
            "emotional_entropy": emotional_entropy,
            "composite_score": composite_score,
            "detected_patterns": patterns,
            "ego_state": ego_state,
            "diagnostics": {
                "high_threshold": self.high_threshold,
                "medium_threshold": self.medium_threshold,
                "entropy_weight": self.entropy_weight,
                "entropy_contribution": emotional_entropy * self.entropy_weight
            }
        }

    def get_level(self, metadata: Dict[str, Any]) -> Level:
        """
        Get resistance level from metadata (simple accessor).

        Args:
            metadata: Dictionary containing resistance data

        Returns:
            Level enum (HIGH, MEDIUM, or LOW)
        """
        detection = self.detect(metadata)
        return Level(detection["resistance_level"])

    def get_score(self, metadata: Dict[str, Any]) -> float:
        """
        Get composite resistance score from metadata.

        Args:
            metadata: Dictionary containing resistance data

        Returns:
            Composite resistance score (0.0 to 1.0)
        """
        detection = self.detect(metadata)
        return detection["composite_score"]

    def is_high_resistance(self, metadata: Dict[str, Any]) -> bool:
        """
        Quick check for high resistance state.

        Args:
            metadata: Dictionary containing resistance data

        Returns:
            True if resistance is HIGH
        """
        return self.get_level(metadata) == Level.HIGH

    def _score_to_level(self, score: float) -> Level:
        """Convert score to level using configured thresholds."""
        if score >= self.high_threshold:
            return Level.HIGH
        elif score >= self.medium_threshold:
            return Level.MEDIUM
        else:
            return Level.LOW

    def _calculate_composite_score(
        self,
        resistance_score: float,
        emotional_entropy: float,
        ego_state: Optional[str]
    ) -> float:
        """
        Calculate composite resistance score from multiple factors.

        Formula:
            composite = base_resistance * (1 - entropy_weight)
                      + emotional_entropy * entropy_weight
                      + ego_adjustment

        Args:
            resistance_score: Direct resistance score
            emotional_entropy: Emotional chaos indicator
            ego_state: User's ego state

        Returns:
            Composite score (0.0 to 1.0)
        """
        # Weighted combination of resistance and entropy
        base_weight = 1.0 - self.entropy_weight
        composite = (
            resistance_score * base_weight
            + emotional_entropy * self.entropy_weight
        )

        # Adjust for ego state
        ego_adjustment = self._get_ego_adjustment(ego_state)
        composite = composite + ego_adjustment

        # Add entropy boost for high emotional chaos
        entropy_boost = entropy_to_resistance_boost(emotional_entropy)
        composite = composite + entropy_boost

        return clamp(composite)

    def _get_ego_adjustment(self, ego_state: Optional[str]) -> float:
        """
        Get resistance adjustment based on ego state.

        Args:
            ego_state: User's ego state

        Returns:
            Adjustment value (-0.2 to +0.3)
        """
        if ego_state is None:
            return 0.0

        ego_adjustments = {
            "open": -0.15,        # Lower resistance
            "receptive": -0.1,
            "curious": -0.05,
            "neutral": 0.0,
            "guarded": 0.1,
            "defensive": 0.2,    # Higher resistance
            "resistant": 0.25,
            "closed": 0.3,
            "hostile": 0.35
        }

        return ego_adjustments.get(ego_state.lower(), 0.0)

    def _detect_resistance_patterns(
        self,
        metadata: Dict[str, Any]
    ) -> List[str]:
        """
        Detect specific resistance patterns from metadata.

        Args:
            metadata: Full metadata dictionary

        Returns:
            List of detected pattern names
        """
        patterns = []

        resistance_score = extract_metadata_score(
            metadata, "resistance_score", default=0.3
        )
        emotional_entropy = extract_metadata_score(
            metadata, "emotional_entropy", default=0.3
        )
        ego_state = metadata.get("ego_state", "neutral")

        # Pattern: High entropy + high resistance = chaotic defense
        if emotional_entropy > ENTROPY_HIGH_THRESHOLD and resistance_score > 0.6:
            patterns.append("CHAOTIC_DEFENSE")

        # Pattern: Low entropy + high resistance = rigid defense
        if emotional_entropy < 0.3 and resistance_score > 0.7:
            patterns.append("RIGID_DEFENSE")

        # Pattern: Defensive ego state
        if ego_state and ego_state.lower() in ["defensive", "closed", "hostile"]:
            patterns.append("EGO_PROTECTION")

        # Pattern: Multiple folded truths but still high resistance
        folded_truths = metadata.get("folded_truths", [])
        if isinstance(folded_truths, list) and len(folded_truths) > 3:
            if resistance_score > 0.5:
                patterns.append("SELECTIVE_ACCEPTANCE")

        return patterns


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def detect_resistance(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to detect resistance.

    Args:
        metadata: Dictionary with resistance data

    Returns:
        Detection result dictionary
    """
    detector = ResistanceDetector()
    return detector.detect(metadata)


def get_resistance_level(metadata: Dict[str, Any]) -> Level:
    """
    Convenience function to get resistance level.

    Args:
        metadata: Dictionary with resistance data

    Returns:
        Level enum
    """
    detector = ResistanceDetector()
    return detector.get_level(metadata)


if __name__ == "__main__":
    print("DHA Resistance Detector v3.0")
    print("=" * 40)
    print("Detects user resistance patterns")
    print(f"HIGH threshold: {RESISTANCE_HIGH_THRESHOLD}")
    print(f"MEDIUM threshold: {RESISTANCE_MEDIUM_THRESHOLD}")

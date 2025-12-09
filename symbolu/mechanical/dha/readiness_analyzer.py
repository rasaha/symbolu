"""
Readiness Analyzer Module (v3.0)
================================

Analyzes user readiness to receive insights and truths.

Converts readiness_score from metadata into categorical levels (HIGH/MEDIUM/LOW)
for use by the tone selector.

Readiness indicates how prepared the user is to:
    - Accept new perspectives
    - Process challenging information
    - Integrate insights into their worldview
"""

from typing import Dict, Any, Optional
from .adaptation_rules import (
    Level,
    readiness_score_to_level,
    extract_metadata_score,
    clamp,
    READINESS_HIGH_THRESHOLD,
    READINESS_MEDIUM_THRESHOLD
)


class ReadinessAnalyzer:
    """
    Analyzer for user readiness to receive insights.

    Converts numerical readiness scores to categorical levels
    for decision-making in the delivery pipeline.
    """

    def __init__(
        self,
        high_threshold: float = READINESS_HIGH_THRESHOLD,
        medium_threshold: float = READINESS_MEDIUM_THRESHOLD
    ):
        """
        Initialize ReadinessAnalyzer.

        Args:
            high_threshold: Score threshold for HIGH readiness (default 0.7)
            medium_threshold: Score threshold for MEDIUM readiness (default 0.4)
        """
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    def analyze(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze readiness from metadata.

        Args:
            metadata: Dictionary containing readiness_score and related data

        Returns:
            Analysis result with level, score, and diagnostics
        """
        # Extract readiness score
        readiness_score = extract_metadata_score(
            metadata, "readiness_score", default=0.5
        )

        # Check for additional readiness indicators
        ego_state = metadata.get("ego_state", "neutral")
        folded_truths = metadata.get("folded_truths", [])

        # Adjust score based on ego state
        adjusted_score = self._adjust_for_ego_state(readiness_score, ego_state)

        # Adjust score based on folded truths
        adjusted_score = self._adjust_for_folded_truths(
            adjusted_score, folded_truths
        )

        # Determine level
        level = self._score_to_level(adjusted_score)

        return {
            "readiness_level": level.value,
            "raw_score": readiness_score,
            "adjusted_score": adjusted_score,
            "ego_state_factor": ego_state,
            "folded_truths_count": len(folded_truths) if isinstance(folded_truths, list) else 0,
            "diagnostics": {
                "high_threshold": self.high_threshold,
                "medium_threshold": self.medium_threshold,
                "adjustments_applied": True
            }
        }

    def get_level(self, metadata: Dict[str, Any]) -> Level:
        """
        Get readiness level from metadata (simple accessor).

        Args:
            metadata: Dictionary containing readiness_score

        Returns:
            Level enum (HIGH, MEDIUM, or LOW)
        """
        analysis = self.analyze(metadata)
        return Level(analysis["readiness_level"])

    def get_score(self, metadata: Dict[str, Any]) -> float:
        """
        Get adjusted readiness score from metadata.

        Args:
            metadata: Dictionary containing readiness_score

        Returns:
            Adjusted readiness score (0.0 to 1.0)
        """
        analysis = self.analyze(metadata)
        return analysis["adjusted_score"]

    def _score_to_level(self, score: float) -> Level:
        """Convert score to level using configured thresholds."""
        if score >= self.high_threshold:
            return Level.HIGH
        elif score >= self.medium_threshold:
            return Level.MEDIUM
        else:
            return Level.LOW

    def _adjust_for_ego_state(
        self,
        score: float,
        ego_state: Optional[str]
    ) -> float:
        """
        Adjust readiness based on ego state.

        Ego states affect how open the user is to new information.

        Args:
            score: Current readiness score
            ego_state: User's ego state (open, defensive, neutral, etc.)

        Returns:
            Adjusted score
        """
        if ego_state is None:
            return score

        ego_adjustments = {
            "open": 0.1,           # More ready to receive
            "receptive": 0.1,
            "curious": 0.05,
            "neutral": 0.0,
            "defensive": -0.15,   # Less ready to receive
            "resistant": -0.2,
            "closed": -0.25,
            "hostile": -0.3
        }

        adjustment = ego_adjustments.get(ego_state.lower(), 0.0)
        return clamp(score + adjustment)

    def _adjust_for_folded_truths(
        self,
        score: float,
        folded_truths: Any
    ) -> float:
        """
        Adjust readiness based on folded truths.

        Folded truths are insights the user has already integrated.
        More folded truths suggest higher readiness for new insights.

        Args:
            score: Current readiness score
            folded_truths: List of previously integrated truths

        Returns:
            Adjusted score
        """
        if not isinstance(folded_truths, list):
            return score

        num_truths = len(folded_truths)

        # Each folded truth adds a small boost (up to 0.2 total)
        boost = min(num_truths * 0.04, 0.2)

        return clamp(score + boost)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def analyze_readiness(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to analyze readiness.

    Args:
        metadata: Dictionary with readiness_score and related data

    Returns:
        Analysis result dictionary
    """
    analyzer = ReadinessAnalyzer()
    return analyzer.analyze(metadata)


def get_readiness_level(metadata: Dict[str, Any]) -> Level:
    """
    Convenience function to get readiness level.

    Args:
        metadata: Dictionary with readiness_score

    Returns:
        Level enum
    """
    analyzer = ReadinessAnalyzer()
    return analyzer.get_level(metadata)


if __name__ == "__main__":
    print("DHA Readiness Analyzer v3.0")
    print("=" * 40)
    print("Converts readiness scores to categorical levels")
    print(f"HIGH threshold: {READINESS_HIGH_THRESHOLD}")
    print(f"MEDIUM threshold: {READINESS_MEDIUM_THRESHOLD}")

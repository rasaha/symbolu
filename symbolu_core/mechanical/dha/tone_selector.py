"""
Tone Selector Module (v3.0)
===========================

Selects the appropriate delivery profile based on readiness and resistance levels.

Decision Logic:
    - High resistance → INVERSE_JOLT (break through with directness)
    - Medium resistance + Low readiness → SYMBOLIC_METAPHOR (gentle, indirect)
    - High readiness + Low resistance → SWEET_RESONANCE (supportive delivery)

This module is the core decision-maker for HOW messages should be delivered.
"""

from typing import Dict, Any, Optional, Tuple
from .adaptation_rules import (
    DeliveryProfile,
    Level,
    get_delivery_profile_metadata
)
from .readiness_analyzer import ReadinessAnalyzer
from .resistance_detector import ResistanceDetector


class ToneSelector:
    """
    Selects delivery profile based on user state analysis.

    Pipeline Position:
        ReadinessAnalyzer + ResistanceDetector → ToneSelector → DeliveryModulator

    The ToneSelector is deterministic: given the same inputs,
    it will always produce the same output.
    """

    def __init__(
        self,
        readiness_analyzer: Optional[ReadinessAnalyzer] = None,
        resistance_detector: Optional[ResistanceDetector] = None
    ):
        """
        Initialize ToneSelector.

        Args:
            readiness_analyzer: Custom ReadinessAnalyzer (uses default if None)
            resistance_detector: Custom ResistanceDetector (uses default if None)
        """
        self.readiness_analyzer = readiness_analyzer or ReadinessAnalyzer()
        self.resistance_detector = resistance_detector or ResistanceDetector()

    def select(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Select appropriate delivery profile based on metadata.

        Args:
            metadata: Dictionary containing:
                - readiness_score (0-1)
                - resistance_score (0-1)
                - emotional_entropy (0-1)
                - ego_state (optional)
                - folded_truths (optional)

        Returns:
            Selection result with:
                - delivery_profile: DeliveryProfile enum value
                - profile_name: String name of profile
                - confidence: Selection confidence (0-1)
                - reasoning: Explanation of selection
                - readiness_analysis: Full readiness analysis
                - resistance_analysis: Full resistance analysis
        """
        # Analyze readiness and resistance
        readiness_analysis = self.readiness_analyzer.analyze(metadata)
        resistance_analysis = self.resistance_detector.detect(metadata)

        # Extract levels
        readiness_level = Level(readiness_analysis["readiness_level"])
        resistance_level = Level(resistance_analysis["resistance_level"])

        # Select profile based on decision matrix
        profile, confidence, reasoning = self._apply_decision_logic(
            readiness_level,
            resistance_level,
            metadata
        )

        return {
            "delivery_profile": profile,
            "profile_name": profile.value,
            "confidence": confidence,
            "reasoning": reasoning,
            "readiness_analysis": readiness_analysis,
            "resistance_analysis": resistance_analysis,
            "profile_metadata": get_delivery_profile_metadata(profile)
        }

    def get_profile(self, metadata: Dict[str, Any]) -> DeliveryProfile:
        """
        Get delivery profile from metadata (simple accessor).

        Args:
            metadata: Dictionary containing readiness/resistance data

        Returns:
            DeliveryProfile enum value
        """
        result = self.select(metadata)
        return result["delivery_profile"]

    def _apply_decision_logic(
        self,
        readiness_level: Level,
        resistance_level: Level,
        metadata: Dict[str, Any]
    ) -> Tuple[DeliveryProfile, float, str]:
        """
        Apply the core decision logic for profile selection.

        Decision Matrix:
        ┌───────────────┬─────────────┬─────────────┬─────────────┐
        │ Resistance →  │    HIGH     │   MEDIUM    │    LOW      │
        │ Readiness ↓   │             │             │             │
        ├───────────────┼─────────────┼─────────────┼─────────────┤
        │     HIGH      │ INVERSE     │ RESONANCE   │ RESONANCE   │
        │     MEDIUM    │ INVERSE     │ METAPHOR    │ RESONANCE   │
        │     LOW       │ INVERSE     │ METAPHOR    │ METAPHOR    │
        └───────────────┴─────────────┴─────────────┴─────────────┘

        Args:
            readiness_level: User's readiness level
            resistance_level: User's resistance level
            metadata: Full metadata for edge case handling

        Returns:
            Tuple of (profile, confidence, reasoning)
        """
        # Priority 1: High resistance always gets INVERSE_JOLT
        if resistance_level == Level.HIGH:
            return (
                DeliveryProfile.INVERSE_JOLT,
                0.9,
                "High resistance detected - using direct approach to break through defensive patterns"
            )

        # Priority 2: High readiness + Low resistance = SWEET_RESONANCE
        if readiness_level == Level.HIGH and resistance_level == Level.LOW:
            return (
                DeliveryProfile.SWEET_RESONANCE,
                0.95,
                "High readiness with low resistance - optimal conditions for gentle, supportive delivery"
            )

        # Priority 3: Medium resistance + Low readiness = SYMBOLIC_METAPHOR
        if resistance_level == Level.MEDIUM and readiness_level == Level.LOW:
            return (
                DeliveryProfile.SYMBOLIC_METAPHOR,
                0.85,
                "Medium resistance with low readiness - using metaphorical framing for gradual insight"
            )

        # Priority 4: Medium readiness + Medium resistance = SYMBOLIC_METAPHOR
        if resistance_level == Level.MEDIUM and readiness_level == Level.MEDIUM:
            return (
                DeliveryProfile.SYMBOLIC_METAPHOR,
                0.8,
                "Balanced state - metaphorical delivery allows safe exploration"
            )

        # Priority 5: Medium readiness + Low resistance = SWEET_RESONANCE
        if resistance_level == Level.LOW and readiness_level == Level.MEDIUM:
            return (
                DeliveryProfile.SWEET_RESONANCE,
                0.85,
                "Low resistance with medium readiness - supportive delivery appropriate"
            )

        # Priority 6: High readiness + Medium resistance
        if readiness_level == Level.HIGH and resistance_level == Level.MEDIUM:
            # Check emotional entropy for edge case
            emotional_entropy = metadata.get("emotional_entropy", 0.5)
            if emotional_entropy > 0.6:
                return (
                    DeliveryProfile.SYMBOLIC_METAPHOR,
                    0.7,
                    "High readiness but elevated entropy suggests caution with metaphorical approach"
                )
            return (
                DeliveryProfile.SWEET_RESONANCE,
                0.8,
                "High readiness can handle medium resistance with supportive approach"
            )

        # Priority 7: Low readiness + Low resistance = SYMBOLIC_METAPHOR
        if readiness_level == Level.LOW and resistance_level == Level.LOW:
            return (
                DeliveryProfile.SYMBOLIC_METAPHOR,
                0.75,
                "Low readiness benefits from indirect, metaphorical approach even without resistance"
            )

        # Default fallback: SYMBOLIC_METAPHOR (safest option)
        return (
            DeliveryProfile.SYMBOLIC_METAPHOR,
            0.6,
            "Defaulting to symbolic metaphor as safest delivery approach"
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def select_tone(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to select tone.

    Args:
        metadata: Dictionary with readiness/resistance data

    Returns:
        Selection result dictionary
    """
    selector = ToneSelector()
    return selector.select(metadata)


def get_delivery_profile(metadata: Dict[str, Any]) -> DeliveryProfile:
    """
    Convenience function to get delivery profile.

    Args:
        metadata: Dictionary with readiness/resistance data

    Returns:
        DeliveryProfile enum
    """
    selector = ToneSelector()
    return selector.get_profile(metadata)


if __name__ == "__main__":
    print("DHA Tone Selector v3.0")
    print("=" * 40)
    print("Selects delivery profile based on user state")
    print("\nAvailable profiles:")
    for profile in DeliveryProfile:
        meta = get_delivery_profile_metadata(profile)
        print(f"  - {profile.value}: {meta.get('description', 'N/A')}")

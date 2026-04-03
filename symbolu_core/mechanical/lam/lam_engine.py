"""
LAM v1.0 Engine Module

Deterministic Long-Arc Mapper engine that produces temporal-longitudinal
cognitive maps for long-arc trajectory reasoning by Fusion/DHA engines.

Key Features:
- Pure deterministic processing (no LLM, no randomness)
- Integrates TemporalBhavaTracker for consciousness state evolution
- Uses CrossDomainIntelligence for universal pattern detection and transfer
- Produces trajectory summaries, momentum indicators, and arc state classification

Usage:
    engine = LAMEngine()
    lam_map = engine.build_map(lam_input)
"""

from typing import Dict, List, Optional, Tuple, Any

from .models import LAMInput, LongArcMap


class LAMEngine:
    """
    LAM - Long-Arc Mapper.

    Uses multi-turn temporal information to produce long-arc cognition.
    Integrates TemporalBhavaTracker and CrossDomainIntelligence to detect
    patterns, trajectories, and arc states over time.

    LAM answers key temporal questions:
    - Where is the user coming from?
    - Where is the user going emotionally/mentally?
    - Is the trajectory rising, falling, stable?
    - Is the system in tension or recovery?
    - Which universal patterns are active?
    - How do we map these patterns to the current domain?

    LAM outputs a deterministic LongArcMap structure - no text generation.

    Attributes:
        tension_threshold: Threshold for tension corridor detection.
        pattern_confidence_threshold: Minimum confidence for pattern inclusion.

    Example:
        engine = LAMEngine()
        lam_map = engine.build_map(lam_input)
    """

    # Default thresholds
    DEFAULT_TENSION_THRESHOLD: float = 0.6
    DEFAULT_PATTERN_CONFIDENCE_THRESHOLD: float = 0.65

    def __init__(
        self,
        *,
        tension_threshold: float = DEFAULT_TENSION_THRESHOLD,
        pattern_confidence_threshold: float = DEFAULT_PATTERN_CONFIDENCE_THRESHOLD,
    ) -> None:
        """
        Initialize the LAM engine with configurable thresholds.

        Args:
            tension_threshold: Threshold for tension state detection.
            pattern_confidence_threshold: Minimum confidence for pattern inclusion.
        """
        self.tension_threshold = tension_threshold
        self.pattern_confidence_threshold = pattern_confidence_threshold

    def build_map(self, lam_input: LAMInput) -> LongArcMap:
        """
        Main entrypoint - builds a temporal-longitudinal cognitive map from input.

        Processing Steps:
        1. Update temporal tracker with the current input
        2. Retrieve temporal summary from tracker
        3. Extract trajectory, momentum, tension, and recovery components
        4. Detect universal patterns using CDI
        5. Generate domain transfers for detected patterns
        6. Determine arc_state based on all signals
        7. Package everything into LongArcMap

        Args:
            lam_input: LAMInput containing current analysis and temporal references.

        Returns:
            LongArcMap with temporal-longitudinal cognitive mapping data.
        """
        # Step 1: Update temporal tracker with the current input
        lam_input.temporal_tracker.add_analysis(
            text=lam_input.text,
            smi=lam_input.smi,
            bhava_id=lam_input.bhava_id,
            bhava_direction=lam_input.bhava_direction,
            kosha_id=lam_input.kosha_id,
            ontology_id=lam_input.ontology_id,
        )

        # Step 2: Retrieve temporal summary from tracker
        summary = lam_input.temporal_tracker.get_pattern_summary()

        # Step 3: Extract components from temporal summary
        trajectory = self._extract_trajectory(summary)
        momentum = self._extract_momentum(summary)
        tension = self._extract_tension(summary)
        recovery = self._extract_recovery(summary)

        # Step 4: Detect universal patterns using CDI
        # Get trend from trajectory for CDI pattern matching
        temporal_trend = trajectory.get("trend", "stable")

        patterns = lam_input.cdi.detect_pattern(
            smi=lam_input.smi,
            bhava_id=lam_input.bhava_id,
            bhava_direction=lam_input.bhava_direction,
            kosha_id=lam_input.kosha_id,
            ontology_id=lam_input.ontology_id,
            temporal_trend=temporal_trend,
        )

        # Filter patterns by confidence threshold
        active_patterns = [
            pattern_name
            for pattern_name, confidence in patterns
            if confidence >= self.pattern_confidence_threshold
        ]

        # Step 5: Generate domain transfers for detected patterns
        domain_transfers = self._generate_domain_transfers(
            patterns=active_patterns,
            domain=lam_input.domain,
            cdi=lam_input.cdi,
        )

        # Step 6: Determine arc_state based on all signals
        arc_state = self._classify_arc_state(
            trajectory=trajectory,
            tension=tension,
            recovery=recovery,
            long_arc_tension=lam_input.long_arc_tension,
        )

        # Step 7: Compute long_arc_signal for cross-mapper fusion
        long_arc_signal = self._compute_long_arc_signal(
            trajectory=trajectory,
            tension=tension,
            recovery=recovery,
            long_arc_tension=lam_input.long_arc_tension,
            pattern_count=len(active_patterns),
        )

        # Package into LongArcMap
        return LongArcMap(
            trajectory_summary=trajectory,
            bhava_momentum=momentum,
            tension_corridor=tension,
            recovery_pattern=recovery,
            active_patterns=active_patterns,
            domain_transfers=domain_transfers,
            arc_state=arc_state,
            long_arc_signal=long_arc_signal,
        )

    def _extract_trajectory(self, summary: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract trajectory summary from temporal pattern summary.

        Args:
            summary: Pattern summary from TemporalBhavaTracker.

        Returns:
            Dictionary with slope, trend, and confidence.
        """
        trajectory_data = summary.get("trajectory", {})

        return {
            "slope": float(trajectory_data.get("slope", 0.0)),
            "trend": trajectory_data.get("trend", "stable"),
            "confidence": float(trajectory_data.get("confidence", 0.0)),
        }

    def _extract_momentum(self, summary: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract bhava momentum from temporal pattern summary.

        Computes:
        - upward_ratio: Proportion of upward movements (derived from direction)
        - acceleration: Rate of momentum change (derived from slope)
        - strength: Overall momentum strength

        Args:
            summary: Pattern summary from TemporalBhavaTracker.

        Returns:
            Dictionary with upward_ratio, acceleration, and strength.
        """
        momentum_data = summary.get("momentum", {})
        trajectory_data = summary.get("trajectory", {})

        direction = momentum_data.get("direction", "neutral")
        strength = float(momentum_data.get("strength", 0.0))
        slope = float(trajectory_data.get("slope", 0.0))

        # Compute upward_ratio based on direction
        if direction == "upward":
            upward_ratio = 0.7 + strength * 0.3
        elif direction == "downward":
            upward_ratio = 0.3 - strength * 0.2
        else:
            upward_ratio = 0.5

        # Clamp to [0, 1]
        upward_ratio = max(0.0, min(1.0, upward_ratio))

        # Acceleration is derived from slope magnitude
        acceleration = abs(slope) * 2.0
        acceleration = min(1.0, acceleration)

        return {
            "upward_ratio": round(upward_ratio, 4),
            "acceleration": round(acceleration, 4),
            "strength": round(strength, 4),
        }

    def _extract_tension(self, summary: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract tension corridor metrics from temporal pattern summary.

        Args:
            summary: Pattern summary from TemporalBhavaTracker.

        Returns:
            Dictionary with length, intensity, and active flag.
        """
        tension_data = summary.get("tension", {})

        corridor_length = int(tension_data.get("corridor_length", 0))
        max_corridor = int(tension_data.get("max_corridor_length", 0))
        is_current = tension_data.get("current", False)

        # Compute intensity based on corridor length relative to max
        if max_corridor > 0:
            intensity = corridor_length / max_corridor
        else:
            intensity = 0.0

        return {
            "length": float(corridor_length),
            "intensity": round(intensity, 4),
            "active": 1.0 if is_current else 0.0,
        }

    def _extract_recovery(self, summary: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract recovery pattern metrics from temporal pattern summary.

        Args:
            summary: Pattern summary from TemporalBhavaTracker.

        Returns:
            Dictionary with recovering flag and progress.
        """
        recovery_data = summary.get("recovery", {})

        is_active = recovery_data.get("active", False)
        progress = float(recovery_data.get("progress", 0.0))

        return {
            "recovering": 1.0 if is_active else 0.0,
            "progress": round(progress, 4),
        }

    def _generate_domain_transfers(
        self,
        patterns: List[str],
        domain: str,
        cdi: Any,
    ) -> Dict[str, str]:
        """
        Generate domain-specific interpretations for detected patterns.

        Args:
            patterns: List of detected pattern names.
            domain: Target domain for interpretation.
            cdi: CrossDomainIntelligence instance.

        Returns:
            Dictionary mapping pattern name to domain-specific interpretation.
        """
        transfers = {}

        for pattern_name in patterns:
            try:
                transfer = cdi.transfer_pattern_to_domain(pattern_name, domain)
                transfers[pattern_name] = transfer.get("interpretation", "")
            except ValueError:
                # Skip patterns or domains not recognized by CDI
                continue

        return transfers

    def _classify_arc_state(
        self,
        trajectory: Dict[str, Any],
        tension: Dict[str, Any],
        recovery: Dict[str, Any],
        long_arc_tension: float,
    ) -> str:
        """
        Classify overall arc state based on all temporal signals.

        Arc States:
        - "tension": Active tension corridor detected
        - "recovery": Actively recovering from high tension
        - "turning_point": Rising trend detected (potential breakthrough)
        - "steady": No significant temporal dynamics

        Classification Priority:
        1. Tension (highest priority) - if tension is active
        2. Recovery - if in active recovery
        3. Turning point - if rising trend with confidence
        4. Steady (default)

        Args:
            trajectory: Trajectory summary dict.
            tension: Tension corridor dict.
            recovery: Recovery pattern dict.
            long_arc_tension: TTOR long-arc tension signal.

        Returns:
            Arc state string: "tension", "recovery", "turning_point", or "steady".
        """
        # Check tension first (highest priority)
        tension_active = tension.get("active", 0.0) > 0.5
        tension_intense = tension.get("intensity", 0.0) > 0.5
        high_lat = long_arc_tension > self.tension_threshold

        if tension_active or (tension_intense and high_lat):
            return "tension"

        # Check recovery
        recovering = recovery.get("recovering", 0.0) > 0.5
        recovery_progress = recovery.get("progress", 0.0)

        if recovering and recovery_progress > 0.2:
            return "recovery"

        # Check turning point
        trend = trajectory.get("trend", "stable")
        confidence = trajectory.get("confidence", 0.0)

        if trend == "rising" and confidence > 0.3:
            return "turning_point"

        # Default to steady
        return "steady"

    def _compute_long_arc_signal(
        self,
        trajectory: Dict[str, Any],
        tension: Dict[str, Any],
        recovery: Dict[str, Any],
        long_arc_tension: float,
        pattern_count: int,
    ) -> float:
        """
        Compute the long-arc signal for cross-mapper fusion.

        This signal indicates the strength of temporal dynamics
        and is used by Fusion/DHA for weighting LAM contributions.

        Components:
        - Base: long_arc_tension from TTOR (40%)
        - Tension intensity (20%)
        - Trajectory confidence (20%)
        - Pattern richness (10%)
        - Recovery activity (10%)

        Args:
            trajectory: Trajectory summary dict.
            tension: Tension corridor dict.
            recovery: Recovery pattern dict.
            long_arc_tension: TTOR long-arc tension signal.
            pattern_count: Number of detected patterns.

        Returns:
            Long-arc signal in [0.0, 1.0].
        """
        # Weight components
        base_weight = 0.40
        tension_weight = 0.20
        trajectory_weight = 0.20
        pattern_weight = 0.10
        recovery_weight = 0.10

        # Base signal from TTOR
        base_signal = long_arc_tension * base_weight

        # Tension contribution
        tension_intensity = tension.get("intensity", 0.0)
        tension_active = tension.get("active", 0.0)
        tension_signal = (tension_intensity + tension_active) / 2.0 * tension_weight

        # Trajectory contribution
        trajectory_confidence = trajectory.get("confidence", 0.0)
        trajectory_signal = trajectory_confidence * trajectory_weight

        # Pattern richness contribution (normalized to [0, 1])
        pattern_richness = min(pattern_count / 5.0, 1.0)
        pattern_signal = pattern_richness * pattern_weight

        # Recovery contribution
        recovery_active = recovery.get("recovering", 0.0)
        recovery_progress = recovery.get("progress", 0.0)
        recovery_signal = (recovery_active + recovery_progress) / 2.0 * recovery_weight

        # Total signal
        total = (
            base_signal
            + tension_signal
            + trajectory_signal
            + pattern_signal
            + recovery_signal
        )

        return round(min(1.0, max(0.0, total)), 4)

    def get_statistics(self) -> Dict[str, float]:
        """
        Get engine configuration statistics.

        Returns:
            Dictionary with threshold configuration.
        """
        return {
            "tension_threshold": self.tension_threshold,
            "pattern_confidence_threshold": self.pattern_confidence_threshold,
        }


# Module-level singleton for convenience
_lam_engine: Optional[LAMEngine] = None


def get_lam_engine() -> LAMEngine:
    """
    Get singleton LAM engine instance.

    Returns:
        Shared LAMEngine instance.
    """
    global _lam_engine
    if _lam_engine is None:
        _lam_engine = LAMEngine()
    return _lam_engine


# Public exports
__all__ = [
    "LAMEngine",
    "get_lam_engine",
]

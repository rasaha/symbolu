"""
LAM v1.0 Models Module

Defines data models for the Long-Arc Mapper:
- LAMInput: Input context for LAM processing
- LongArcMap: Output temporal-longitudinal cognitive map

All models are dataclasses for deterministic processing.
LAM handles long-arc temporal trajectory reasoning by integrating
TemporalBhavaTracker and CrossDomainIntelligence signals.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Any

# Type checking imports to avoid circular dependencies
if TYPE_CHECKING:
    from symbolu.temporal.temporal_bhava_tracker import TemporalBhavaTracker
    from symbolu.temporal.cross_domain_intelligence import CrossDomainIntelligence


@dataclass
class LAMInput:
    """
    Input context for LAM (Long-Arc Mapper) processing.

    Contains all signals needed for building a temporal-longitudinal cognitive map:
    - Current analysis results (text, smi, bhava, kosha, ontology)
    - Domain classification
    - TTOR long-arc tension signal
    - References to temporal tracker and cross-domain intelligence

    LAM is triggered when:
    - routing_plan.use_lam = True
    - Or router_context.long_arc_tension > threshold

    Attributes:
        text: The raw query text being analyzed.
        smi: Semantic Mismatch Index value (0.0 to 1.0).
        bhava_id: Bhava state identifier.
        bhava_direction: Direction of bhava ("upward", "downward", "stable").
        kosha_id: Kosha layer identifier.
        ontology_id: Ontological layer identifier (1-10), mapping to:
                    Lower 5 (1-5): O1_action, O2_tagging, O3_forming, O4_thinking, O5_directing
                    Upper 5 (6-10): O6_reasoning, O7_purposing, O8_meta_observing, O9_unifying, O10_absolving
        domain: Domain classification (finance, medicine, psychology, etc.)
        long_arc_tension: TTOR long-arc tension signal (0.0 to 1.0).
        temporal_tracker: Reference to TemporalBhavaTracker instance.
        cdi: Reference to CrossDomainIntelligence instance.
    """

    text: str
    smi: float
    bhava_id: int
    bhava_direction: str  # "upward" | "downward" | "stable"
    kosha_id: int
    ontology_id: int
    domain: str
    long_arc_tension: float  # TTOR signal
    temporal_tracker: "TemporalBhavaTracker"
    cdi: "CrossDomainIntelligence"


@dataclass
class LongArcMap:
    """
    Output temporal-longitudinal cognitive map from LAM.

    Contains structured, symbolic data for Fusion/DHA engines:
    - Trajectory analysis (slope, trend, confidence)
    - Bhava momentum indicators
    - Tension corridor metrics
    - Recovery pattern detection
    - Active universal patterns
    - Domain-specific pattern transfers
    - Overall arc state classification
    - Long-arc signal for cross-mapper fusion

    No text generation - only deterministic structured data.

    Attributes:
        trajectory_summary: Trajectory analysis with slope, trend, and confidence.
                           - slope: Rate of SMI change over time
                           - trend: "rising", "falling", or "stable"
                           - confidence: Confidence in the trend detection
        bhava_momentum: Momentum indicators for bhava state.
                       - upward_ratio: Proportion of upward movements
                       - acceleration: Rate of momentum change
                       - strength: Overall momentum strength
        tension_corridor: Tension corridor metrics.
                         - length: Current corridor length
                         - intensity: Corridor intensity (based on max corridor)
                         - active: Whether currently in tension
        recovery_pattern: Recovery pattern analysis.
                         - recovering: Whether in active recovery
                         - progress: Progress through recovery (0.0 to 1.0)
        active_patterns: List of detected universal pattern names.
        domain_transfers: Domain-specific pattern interpretations.
                         Maps pattern_name -> domain-specific interpretation.
        arc_state: Overall arc state classification.
                  One of: "steady", "turning_point", "recovery", "tension"
        long_arc_signal: TTOR signal for cross-mapper fusion (0.0 to 1.0).
    """

    trajectory_summary: Dict[str, float] = field(default_factory=dict)
    bhava_momentum: Dict[str, float] = field(default_factory=dict)
    tension_corridor: Dict[str, float] = field(default_factory=dict)
    recovery_pattern: Dict[str, float] = field(default_factory=dict)
    active_patterns: List[str] = field(default_factory=list)
    domain_transfers: Dict[str, str] = field(default_factory=dict)
    arc_state: str = "steady"
    long_arc_signal: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "trajectory_summary": self.trajectory_summary,
            "bhava_momentum": self.bhava_momentum,
            "tension_corridor": self.tension_corridor,
            "recovery_pattern": self.recovery_pattern,
            "active_patterns": self.active_patterns,
            "domain_transfers": self.domain_transfers,
            "arc_state": self.arc_state,
            "long_arc_signal": self.long_arc_signal,
        }

    def __repr__(self) -> str:
        """Concise representation for logging."""
        trend = self.trajectory_summary.get("trend", "unknown")
        pattern_count = len(self.active_patterns)
        return (
            f"LongArcMap(arc_state={self.arc_state}, "
            f"trend={trend}, "
            f"patterns={pattern_count}, "
            f"long_arc_signal={self.long_arc_signal:.3f})"
        )


# Public exports
__all__ = [
    "LAMInput",
    "LongArcMap",
]

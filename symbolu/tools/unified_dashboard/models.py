"""
Unified Dashboard Models (Phase 20 v1.0)

This module defines dataclasses for dashboard-ready analytics views.
All models are JSON-serializable and deterministic.

Design Principles:
    1. Zero-LLM (no model calls)
    2. JSON-safe (all fields serializable)
    3. Deterministic (same input → same output)
    4. Optional fields for missing data
    5. Complete metric coverage
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class MetricSparkline:
    """
    Compact sparkline representation for metric trends.

    Attributes:
        name: Metric name (e.g., "coherence", "drift", "entropy")
        values: Normalized values [0.0-1.0] for sparkline visualization
        labels: Optional turn labels or timestamps (for tooltips)
    """
    name: str
    values: List[float] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class MetricBandStatus:
    """
    Band classification for a single metric.

    Attributes:
        name: Metric name
        value: Current metric value (0.0-1.0 or None)
        band: Band classification ("low" | "moderate" | "high" | None)
        commentary: Short deterministic description
    """
    name: str
    value: Optional[float] = None
    band: Optional[str] = None
    commentary: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


@dataclass
class UnifiedSessionAnalytics:
    """
    Complete dashboard analytics for a single session.

    This is the primary analytics model combining all Symbol-U v3.0 metrics
    into a unified, dashboard-ready view.

    All fields are optional to handle missing data gracefully.
    All computations are deterministic and zero-LLM.
    """

    # ========================================================================
    # Session Metadata
    # ========================================================================
    session_id: str
    domain: Optional[str] = None
    turn_count: int = 0

    # ========================================================================
    # Core Coherence & Stability
    # ========================================================================
    coherence_v1: Optional[float] = None
    coherence_v2: Optional[float] = None
    coherence_v3: Optional[float] = None
    coherence_fused: Optional[float] = None
    coherence_v3_quality: Optional[float] = None

    # ========================================================================
    # Semantic & Drift
    # ========================================================================
    semantic_integrity_score: Optional[float] = None
    cognitive_drift_v3: Optional[float] = None
    drift_fusion_index: Optional[float] = None
    drift_risk_band: Optional[str] = None
    drift_pattern_tags: List[str] = field(default_factory=list)

    # ========================================================================
    # Temporal & Entropy
    # ========================================================================
    temporal_arc_score: Optional[float] = None
    instantaneous_entropy: Optional[float] = None
    short_window_entropy: Optional[float] = None
    long_window_entropy: Optional[float] = None
    normalized_entropy_diff: Optional[float] = None
    entropy_volatility: Optional[float] = None

    # ========================================================================
    # Motivation & Identity & Intent
    # ========================================================================
    intent_arc_type: Optional[str] = None
    identity_signature: Optional[str] = None
    motivation_type: Optional[str] = None

    # ========================================================================
    # Formula / Resonance
    # ========================================================================
    enhanced_smi: Optional[float] = None
    avg_enhanced_smi: Optional[float] = None
    resonance_index: Optional[float] = None
    tension_index: Optional[float] = None
    arc_alignment_index: Optional[float] = None
    guna_resonance_index: Optional[float] = None
    kosha_resonance_index: Optional[float] = None

    # ========================================================================
    # Aggregated Bands (Derived)
    # ========================================================================
    stability_band: Optional[str] = None
    drift_band: Optional[str] = None
    motivation_band: Optional[str] = None
    semantic_band: Optional[str] = None

    # ========================================================================
    # Timeline Views (Sparklines)
    # ========================================================================
    coherence_sparkline: MetricSparkline = field(default_factory=lambda: MetricSparkline(name="coherence"))
    drift_sparkline: MetricSparkline = field(default_factory=lambda: MetricSparkline(name="drift"))
    entropy_sparkline: MetricSparkline = field(default_factory=lambda: MetricSparkline(name="entropy"))

    # ========================================================================
    # Pattern Tags & Notes
    # ========================================================================
    session_pattern_tags: List[str] = field(default_factory=list)
    note: Optional[str] = None

    # ========================================================================
    # Phase 23: Cause-Effect Inversion Analytics
    # ========================================================================
    inversion_band: Optional[str] = None  # "forward_dominant" | "ambiguous" | "inversion_plausible" | "inversion_dominant"
    inversion_sparkline: Optional[MetricSparkline] = None
    inversion_notes: List[str] = field(default_factory=list)

    # ========================================================================
    # Phase 24: Resonance Weighting Function
    # ========================================================================
    resonance_entropy_band: Optional[str] = None  # "focused" | "balanced" | "diffuse"
    dominant_resonance_metrics: List[str] = field(default_factory=list)  # Top metrics by normalized weight
    resonance_notes: List[str] = field(default_factory=list)  # Diagnostic notes

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to JSON-serializable dictionary.

        Returns:
            Complete analytics as dictionary with all fields
        """
        data = asdict(self)

        # Remove None values for cleaner output
        return _remove_none_values(data)

    def to_json_string(self) -> str:
        """
        Convert to JSON string.

        Returns:
            JSON string representation
        """
        import json
        return json.dumps(self.to_dict(), indent=2)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _remove_none_values(d: Any) -> Any:
    """
    Recursively remove None values from dictionary.

    Args:
        d: Dictionary or value to process

    Returns:
        Cleaned dictionary or value
    """
    if isinstance(d, dict):
        return {k: _remove_none_values(v) for k, v in d.items() if v is not None}
    elif isinstance(d, list):
        return [_remove_none_values(item) for item in d]
    else:
        return d


# Public API
__all__ = [
    "MetricSparkline",
    "MetricBandStatus",
    "UnifiedSessionAnalytics",
]

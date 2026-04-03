"""
P20 Schema - Unified Cognitive Snapshot

Phase 20 is a read-only aggregation layer that collects outputs from Phases 1-19
into a unified, immutable snapshot for observability, dashboards, audits, and
regression verification.

CRITICAL CONSTRAINTS:
    - Read-Only: Does NOT modify any upstream state or context
    - Deterministic: Same context always produces same snapshot
    - No Computation: No formulas, thresholds, or conditionals
    - No Gating: Does NOT influence routing, intent, regime, discourse, or rendering
    - No Side Effects: Pure observation only
    - Immutable: All fields are frozen after creation

Design Principles:
    - Observability Boundary: Exposes internal cognitive state externally
    - Verbatim Copy: All fields copied directly from context (no synthesis)
    - Missing = None: Missing values are None (no defaults, no fallbacks)
    - Safe External Exposure: Suitable for logging, dashboards, and audits

    Must NOT:
        - Infer or derive new values
        - Normalize or transform values
        - Gate or block any behavior
        - Modify any upstream state
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional, Tuple


# =============================================================================
# Version
# =============================================================================

P20_VERSION = "1.0.0"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass(frozen=True)
class UnifiedCognitiveSnapshot:
    """
    Immutable snapshot of the system's internal cognitive state at a point in time.

    This is the primary output of Phase 20. It collects outputs from Phases 1-19
    without performing any computation, gating, inference, or modulation.

    All fields are copied verbatim from context. Missing values are None.
    No default synthesis, fallbacks, or normalization is performed.

    Attributes:
        timestamp: UTC timestamp when snapshot was created
        run_id: Unique identifier for this pipeline run

        # Core coherence
        coherence_v3: Coherence v3 megafusion score [0.0, 1.0] from Phase 10
        coherence_quality: Coherence v3 quality metric [0.0, 1.0] from Phase 12

        # Entropy
        temporal_entropy_diff: Temporal entropy differential [0.0, 1.0] from Phase 18
        temporal_entropy_volatility: Temporal entropy volatility [0.0, 1.0] from Phase 18

        # Drift
        drift_fusion_index: Drift fusion index [0.0, 1.0] from Phase 19
        drift_risk_band: Drift risk band ("low"/"moderate"/"high") from Phase 19
        drift_pattern_tags: Drift pattern tags from Phase 19

        # Integrity / harmony
        semantic_integrity: Semantic integrity score [0.0, 1.0] from Phase 17
        symbolic_harmony: Symbolic harmonization index [0.0, 1.0] from Phase 27

        # Domain / activation
        active_domains: Tuple of active domain names
        phase_completion_flags: Dict mapping phase names to completion status
    """

    # Identity
    timestamp: datetime
    run_id: str

    # Core coherence
    coherence_v3: Optional[float] = None
    coherence_quality: Optional[float] = None

    # Entropy
    temporal_entropy_diff: Optional[float] = None
    temporal_entropy_volatility: Optional[float] = None

    # Drift
    drift_fusion_index: Optional[float] = None
    drift_risk_band: Optional[str] = None
    drift_pattern_tags: Tuple[str, ...] = field(default_factory=tuple)

    # Integrity / harmony
    semantic_integrity: Optional[float] = None
    symbolic_harmony: Optional[float] = None

    # Domain / activation
    active_domains: Tuple[str, ...] = field(default_factory=tuple)
    phase_completion_flags: Dict[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate snapshot invariants (minimal - just type checks)."""
        # Ensure timestamp is datetime
        if not isinstance(self.timestamp, datetime):
            raise TypeError(
                f"UnifiedCognitiveSnapshot.timestamp must be datetime, "
                f"got {type(self.timestamp).__name__}"
            )

        # Ensure run_id is string
        if not isinstance(self.run_id, str):
            raise TypeError(
                f"UnifiedCognitiveSnapshot.run_id must be str, "
                f"got {type(self.run_id).__name__}"
            )

        # Ensure drift_pattern_tags is tuple (frozen dataclass requires immutable)
        if not isinstance(self.drift_pattern_tags, tuple):
            # Convert to tuple for immutability
            object.__setattr__(self, 'drift_pattern_tags', tuple(self.drift_pattern_tags))

        # Ensure active_domains is tuple
        if not isinstance(self.active_domains, tuple):
            object.__setattr__(self, 'active_domains', tuple(self.active_domains))

        # Ensure phase_completion_flags is dict (frozen=True allows dict)
        if not isinstance(self.phase_completion_flags, dict):
            raise TypeError(
                f"UnifiedCognitiveSnapshot.phase_completion_flags must be dict, "
                f"got {type(self.phase_completion_flags).__name__}"
            )

    # -------------------------------------------------------------------------
    # Convenience methods (read-only, no behavior)
    # -------------------------------------------------------------------------

    def has_coherence(self) -> bool:
        """Check if coherence v3 is present."""
        return self.coherence_v3 is not None

    def has_entropy(self) -> bool:
        """Check if temporal entropy values are present."""
        return self.temporal_entropy_diff is not None

    def has_drift(self) -> bool:
        """Check if drift fusion values are present."""
        return self.drift_fusion_index is not None

    def has_integrity(self) -> bool:
        """Check if semantic integrity is present."""
        return self.semantic_integrity is not None

    def has_harmony(self) -> bool:
        """Check if symbolic harmony is present."""
        return self.symbolic_harmony is not None

    def phase_count(self) -> int:
        """Get the number of completed phases."""
        return sum(1 for v in self.phase_completion_flags.values() if v)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize snapshot to dictionary for API/JSON output."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "coherence_v3": self.coherence_v3,
            "coherence_quality": self.coherence_quality,
            "temporal_entropy_diff": self.temporal_entropy_diff,
            "temporal_entropy_volatility": self.temporal_entropy_volatility,
            "drift_fusion_index": self.drift_fusion_index,
            "drift_risk_band": self.drift_risk_band,
            "drift_pattern_tags": list(self.drift_pattern_tags),
            "semantic_integrity": self.semantic_integrity,
            "symbolic_harmony": self.symbolic_harmony,
            "active_domains": list(self.active_domains),
            "phase_completion_flags": dict(self.phase_completion_flags),
        }


# =============================================================================
# Helper Functions
# =============================================================================


def create_snapshot(
    timestamp: datetime,
    run_id: str,
    coherence_v3: Optional[float] = None,
    coherence_quality: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    temporal_entropy_volatility: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    drift_risk_band: Optional[str] = None,
    drift_pattern_tags: Optional[Tuple[str, ...]] = None,
    semantic_integrity: Optional[float] = None,
    symbolic_harmony: Optional[float] = None,
    active_domains: Optional[Tuple[str, ...]] = None,
    phase_completion_flags: Optional[Dict[str, bool]] = None,
) -> UnifiedCognitiveSnapshot:
    """
    Factory function to create a UnifiedCognitiveSnapshot.

    Args:
        timestamp: UTC timestamp when snapshot was created
        run_id: Unique identifier for this pipeline run
        coherence_v3: Coherence v3 score from Phase 10
        coherence_quality: Coherence quality from Phase 12
        temporal_entropy_diff: Entropy diff from Phase 18
        temporal_entropy_volatility: Entropy volatility from Phase 18
        drift_fusion_index: Drift index from Phase 19
        drift_risk_band: Drift risk band from Phase 19
        drift_pattern_tags: Drift pattern tags from Phase 19
        semantic_integrity: Semantic integrity from Phase 17
        symbolic_harmony: Symbolic harmony from Phase 27
        active_domains: Active domain names
        phase_completion_flags: Phase completion status

    Returns:
        UnifiedCognitiveSnapshot instance
    """
    return UnifiedCognitiveSnapshot(
        timestamp=timestamp,
        run_id=run_id,
        coherence_v3=coherence_v3,
        coherence_quality=coherence_quality,
        temporal_entropy_diff=temporal_entropy_diff,
        temporal_entropy_volatility=temporal_entropy_volatility,
        drift_fusion_index=drift_fusion_index,
        drift_risk_band=drift_risk_band,
        drift_pattern_tags=tuple(drift_pattern_tags) if drift_pattern_tags else (),
        semantic_integrity=semantic_integrity,
        symbolic_harmony=symbolic_harmony,
        active_domains=tuple(active_domains) if active_domains else (),
        phase_completion_flags=dict(phase_completion_flags) if phase_completion_flags else {},
    )


# Public exports
__all__ = [
    # Version
    "P20_VERSION",
    # Dataclasses
    "UnifiedCognitiveSnapshot",
    # Helpers
    "create_snapshot",
]

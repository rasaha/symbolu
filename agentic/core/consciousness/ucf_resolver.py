"""
P26 - Unified Consciousness Formula Resolver

Orchestration layer for UCF computation that extracts inputs from
PipelineContext and delegates to the pure formula computation.

This resolver:
    1. Extracts coherence signals from PipelineContext
    2. Delegates computation to ucf_formula
    3. Returns immutable UnifiedConsciousnessState

The resolver NEVER:
    - Modifies upstream state
    - Makes decisions based on UCF
    - Imports forbidden modules (P6-P9, P21, P22-P24, Renderer, DHA, Persona)
    - Calls LLMs or uses randomness

Invariants:
    - INV-P26-1: UCF is read-only truth, not a decision
    - INV-P26-2: Observer data cannot affect UCF
    - INV-P26-3: UCF monotonic with respect to instability
    - INV-P26-4: UCF never opens gates directly
    - INV-P26-5: Absence of optional inputs never destabilizes output
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from agentic.core.consciousness.ucf_schema import (
    P26_VERSION,
    UnifiedConsciousnessState,
    create_neutral_state,
)

from agentic.core.consciousness.ucf_formula import (
    compute_ucf,
)


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class UCFResolver:
    """
    Orchestration resolver for Phase 26: Unified Consciousness Formula.

    This class provides the interface between PipelineContext and the
    pure UCF formula computation. It extracts relevant inputs from
    context and delegates to compute_ucf().

    Usage:
        resolver = UCFResolver()
        state = resolver.compute(ctx)

    The resolver is stateless - it does not store any computation results.
    Each call to compute() is independent.
    """

    def __init__(self) -> None:
        """Initialize UCFResolver."""
        self._version = P26_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def compute(self, ctx: Any) -> UnifiedConsciousnessState:
        """
        Compute UCF from PipelineContext.

        This method:
        1. Extracts coherence signals from ctx
        2. Extracts temporal metrics (P18, P19)
        3. Extracts schema stability (P33)
        4. Extracts identity harmonics (if present)
        5. Calls compute_ucf() with extracted values
        6. Returns the result (does NOT modify ctx)

        Args:
            ctx: PipelineContext or compatible object with:
                - coherence_state: CoherenceState with coherence_v3_quality
                - p18: P18TemporalEntropyReport (or coherence_state.temporal_entropy_volatility)
                - p19: P19DriftFusionReport (or coherence_state.drift_fusion_index)
                - p33: SchemaAdaptiveRoutingSnapshot (or coherence_state.persona_schema_stability)
                - identity_harmonics_snapshot (optional)

        Returns:
            UnifiedConsciousnessState with computed UCF

        Note:
            This method NEVER modifies ctx. It only reads from it.
        """
        # Extract all inputs with graceful degradation
        inputs = self._extract_inputs(ctx)

        # Compute UCF using pure formula
        return compute_ucf(**inputs)

    def _extract_inputs(self, ctx: Any) -> Dict[str, Optional[float]]:
        """
        Extract UCF inputs from PipelineContext.

        This method safely extracts all required inputs, returning None
        for any missing values (graceful degradation).

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            Dictionary with UCF input values (some may be None)
        """
        inputs: Dict[str, Optional[float]] = {
            "coherence_v3_quality": None,
            "drift_fusion_index": None,
            "entropy_volatility": None,
            "schema_stability": None,
            "identity_harmonics_stability": None,
        }

        # ====================================================================
        # Extract coherence_v3_quality from CoherenceState (P10/P12)
        # ====================================================================

        coherence_state = getattr(ctx, "coherence_state", None)

        if coherence_state is not None:
            # Primary source: coherence_v3_quality from CoherenceState
            inputs["coherence_v3_quality"] = getattr(
                coherence_state, "coherence_v3_quality", None
            )

            # Also check for temporal metrics in coherence_state
            if inputs["drift_fusion_index"] is None:
                inputs["drift_fusion_index"] = getattr(
                    coherence_state, "drift_fusion_index", None
                )

            if inputs["entropy_volatility"] is None:
                inputs["entropy_volatility"] = getattr(
                    coherence_state, "temporal_entropy_volatility", None
                )

            if inputs["schema_stability"] is None:
                inputs["schema_stability"] = getattr(
                    coherence_state, "persona_schema_stability", None
                )

            # Identity harmonics from coherence_state
            if inputs["identity_harmonics_stability"] is None:
                inputs["identity_harmonics_stability"] = getattr(
                    coherence_state, "current_identity_harmonics_index", None
                )

        # ====================================================================
        # Extract from P18 (Temporal Entropy) - if available
        # ====================================================================

        p18 = getattr(ctx, "p18", None)
        if p18 is not None and inputs["entropy_volatility"] is None:
            # Try to get volatility from P18 report
            volatility_band = getattr(p18, "volatility_band", None)
            if volatility_band is not None:
                # Convert volatility band to numeric
                inputs["entropy_volatility"] = self._volatility_band_to_score(
                    volatility_band
                )

        # ====================================================================
        # Extract from P19 (Drift Fusion) - if available
        # ====================================================================

        p19 = getattr(ctx, "p19", None)
        if p19 is not None and inputs["drift_fusion_index"] is None:
            inputs["drift_fusion_index"] = getattr(p19, "drift_fusion_index", None)

        # ====================================================================
        # Extract from P33 (Schema Adaptive) - if available
        # ====================================================================

        p33 = getattr(ctx, "p33", None)
        if p33 is not None and inputs["schema_stability"] is None:
            # Try to get average stability from P33 snapshot
            stability_scores = getattr(p33, "schema_stability_scores", None)
            if stability_scores and isinstance(stability_scores, dict):
                if stability_scores:
                    inputs["schema_stability"] = sum(stability_scores.values()) / len(
                        stability_scores
                    )
            # Also try direct confidence field
            if inputs["schema_stability"] is None:
                inputs["schema_stability"] = getattr(p33, "confidence", None)

        # ====================================================================
        # Extract from identity_harmonics_snapshot - if available
        # ====================================================================

        ih_snapshot = getattr(ctx, "identity_harmonics_snapshot", None)
        if ih_snapshot is not None and inputs["identity_harmonics_stability"] is None:
            inputs["identity_harmonics_stability"] = getattr(
                ih_snapshot, "index", None
            )

        # Also check coherence_state for identity harmonics
        if coherence_state is not None and inputs["identity_harmonics_stability"] is None:
            ih_from_state = getattr(
                coherence_state, "identity_harmonics_snapshot", None
            )
            if ih_from_state is not None:
                inputs["identity_harmonics_stability"] = getattr(
                    ih_from_state, "index", None
                )

        return inputs

    def _volatility_band_to_score(self, volatility_band: Any) -> Optional[float]:
        """
        Convert volatility band enum to numeric score.

        Args:
            volatility_band: VolatilityBand enum or string

        Returns:
            Float score [0.0, 1.0] or None if unknown
        """
        # Handle enum or string
        if hasattr(volatility_band, "value"):
            band_value = volatility_band.value
        else:
            band_value = str(volatility_band).upper()

        # Map bands to numeric values
        band_mapping = {
            "LOW": 0.2,
            "MED": 0.5,
            "MEDIUM": 0.5,
            "HIGH": 0.8,
            "UNKNOWN": 0.5,  # Neutral default
        }

        return band_mapping.get(band_value, 0.5)

    def compute_directly(
        self,
        coherence_v3_quality: Optional[float] = None,
        drift_fusion_index: Optional[float] = None,
        entropy_volatility: Optional[float] = None,
        schema_stability: Optional[float] = None,
        identity_harmonics_stability: Optional[float] = None,
    ) -> UnifiedConsciousnessState:
        """
        Compute UCF directly with explicit inputs (for testing).

        This bypasses context extraction and allows direct testing.

        Args:
            All UCF input parameters

        Returns:
            UnifiedConsciousnessState
        """
        return compute_ucf(
            coherence_v3_quality=coherence_v3_quality,
            drift_fusion_index=drift_fusion_index,
            entropy_volatility=entropy_volatility,
            schema_stability=schema_stability,
            identity_harmonics_stability=identity_harmonics_stability,
        )


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_ucf_resolver: Optional[UCFResolver] = None


def get_ucf_resolver() -> UCFResolver:
    """
    Get the singleton UCFResolver instance.

    Returns:
        The shared UCFResolver instance
    """
    global _ucf_resolver
    if _ucf_resolver is None:
        _ucf_resolver = UCFResolver()
    return _ucf_resolver


def reset_ucf_resolver() -> None:
    """
    Reset the singleton UCFResolver instance.

    This is primarily for testing purposes.
    """
    global _ucf_resolver
    _ucf_resolver = None


# Public exports
__all__ = [
    # Classes
    "UCFResolver",
    # Singleton
    "get_ucf_resolver",
    "reset_ucf_resolver",
]

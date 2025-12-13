"""
P19 - Drift Fusion Resolver

Main resolver class that fuses symbolic, semantic, and temporal drift signals
into a unified drift profile. This is the entry point for P19 analysis.

Design Principles:
    - Observation-Only: Never modifies upstream context
    - Deterministic: Same inputs always produce same outputs
    - Fixed Formula: Weighted blend of drift sources
    - Non-Invasive: Zero impact on routing, scoring, or behavior

CRITICAL CONSTRAINTS:
    ❌ Must NOT:
        - Infer intent
        - Infer emotion
        - Select regime
        - Gate actions
        - Trigger any side effects

Drift Fusion Formula:
    drift_fusion_index = w1 * cognitive_drift_v3 +
                        w2 * (1 - semantic_integrity) +
                        w3 * temporal_entropy_volatility +
                        w4 * |temporal_entropy_diff - 0.5| +
                        w5 * (1 - coherence_fused)

All weights are constants (not configurable).
Missing inputs use neutral defaults (graceful degradation).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from symbolu.mechanical.pipeline.p19_drift_fusion.p19_schema import (
    P19_VERSION,
    P19DriftFusionReport,
    DriftRiskBand,
    DriftPatternTag,
    W_COGNITIVE_DRIFT,
    W_INTEGRITY,
    W_VOLATILITY,
    W_ENTROPY_SHIFT,
    W_COHERENCE,
    RISK_BAND_LOW_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    TAG_SEMANTIC_DRIFT_THRESHOLD,
    TAG_COGNITIVE_DRIFT_THRESHOLD,
    TAG_TEMPORAL_INSTABILITY_THRESHOLD,
    TAG_ENTROPY_SHIFT_THRESHOLD,
    TAG_LOW_COHERENCE_THRESHOLD,
    create_report,
)


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P19DriftFusion:
    """
    P19 Drift Fusion - Deterministic diagnostic synthesis phase.

    Fuses symbolic, semantic, and temporal drift signals into a unified
    drift profile. The resolver never modifies upstream state.

    Usage:
        resolver = P19DriftFusion()
        report = resolver.compute(ctx)

    The report contains:
        - drift_fusion_index: Overall drift severity [0, 1]
        - drift_risk_band: Risk classification ("low" / "moderate" / "high")
        - drift_pattern_tags: List of detected patterns
        - Input signals for observability
        - Debug trace information
    """

    def __init__(self) -> None:
        """Initialize the P19 Drift Fusion resolver."""
        self._version = P19_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def compute(self, ctx: Any) -> Optional[P19DriftFusionReport]:
        """
        Compute drift fusion from pipeline context.

        This is the main entry point for P19 analysis. It:
        1. Extracts upstream signals from context (P17, P18, P16)
        2. Computes drift_fusion_index using weighted formula
        3. Determines drift_risk_band from index
        4. Generates drift_pattern_tags from rule-based thresholds
        5. Produces the P19DriftFusionReport

        Args:
            ctx: PipelineContext, CoherenceState, or compatible object

        Returns:
            P19DriftFusionReport with computed metrics, or None if all inputs missing
        """
        # Track debug information
        debug: Dict[str, Any] = {
            "version": self._version,
            "weights": {
                "cognitive_drift": W_COGNITIVE_DRIFT,
                "integrity": W_INTEGRITY,
                "volatility": W_VOLATILITY,
                "entropy_shift": W_ENTROPY_SHIFT,
                "coherence": W_COHERENCE,
            },
            "missing_inputs": [],
        }

        # 1. Extract upstream signals
        semantic_integrity = self._extract_semantic_integrity(ctx)
        cognitive_drift = self._extract_cognitive_drift(ctx)
        temporal_entropy_diff = self._extract_temporal_entropy_diff(ctx)
        temporal_entropy_volatility = self._extract_temporal_entropy_volatility(ctx)
        coherence_fused = self._extract_coherence_fused(ctx)

        # 2. Track missing inputs and check if all are None
        all_none = True

        if semantic_integrity is None:
            debug["missing_inputs"].append("semantic_integrity_score")
        else:
            all_none = False

        if cognitive_drift is None:
            debug["missing_inputs"].append("cognitive_drift_v3")
        else:
            all_none = False

        if temporal_entropy_diff is None:
            debug["missing_inputs"].append("temporal_entropy_diff")
        else:
            all_none = False

        if temporal_entropy_volatility is None:
            debug["missing_inputs"].append("temporal_entropy_volatility")
        else:
            all_none = False

        if coherence_fused is None:
            debug["missing_inputs"].append("coherence_fused")
        else:
            all_none = False

        # Return None if all inputs are missing
        if all_none:
            debug["result"] = "all_inputs_none"
            return None

        debug["missing_count"] = len(debug["missing_inputs"])

        # 3. Apply neutral defaults for missing inputs
        integrity_val = semantic_integrity if semantic_integrity is not None else 0.0
        drift_val = cognitive_drift if cognitive_drift is not None else 0.0
        entropy_diff_val = temporal_entropy_diff if temporal_entropy_diff is not None else 0.5
        entropy_vol_val = temporal_entropy_volatility if temporal_entropy_volatility is not None else 0.0
        coherence_val = coherence_fused if coherence_fused is not None else 0.5

        # Clamp all inputs to [0, 1]
        integrity_val = max(0.0, min(1.0, integrity_val))
        drift_val = max(0.0, min(1.0, drift_val))
        entropy_diff_val = max(0.0, min(1.0, entropy_diff_val))
        entropy_vol_val = max(0.0, min(1.0, entropy_vol_val))
        coherence_val = max(0.0, min(1.0, coherence_val))

        debug["inputs_used"] = {
            "semantic_integrity": integrity_val,
            "cognitive_drift": drift_val,
            "temporal_entropy_diff": entropy_diff_val,
            "temporal_entropy_volatility": entropy_vol_val,
            "coherence_fused": coherence_val,
        }

        # 4. Compute drift_fusion_index using weighted formula
        # Invert semantic_integrity (low integrity → high drift)
        integrity_term = 1.0 - integrity_val

        # Cognitive drift is direct contribution
        drift_term = drift_val

        # Temporal volatility is direct contribution
        volatility_term = entropy_vol_val

        # Entropy shift: deviation from neutral (0.5)
        entropy_shift_term = abs(entropy_diff_val - 0.5)

        # Invert coherence_fused (low coherence → high drift)
        coherence_term = 1.0 - coherence_val

        # Weighted sum
        drift_fusion_index = (
            W_COGNITIVE_DRIFT * drift_term +
            W_INTEGRITY * integrity_term +
            W_VOLATILITY * volatility_term +
            W_ENTROPY_SHIFT * entropy_shift_term +
            W_COHERENCE * coherence_term
        )

        # Clamp to [0, 1]
        drift_fusion_index = max(0.0, min(1.0, drift_fusion_index))

        debug["drift_fusion_index"] = drift_fusion_index
        debug["term_contributions"] = {
            "cognitive_drift_contribution": W_COGNITIVE_DRIFT * drift_term,
            "integrity_contribution": W_INTEGRITY * integrity_term,
            "volatility_contribution": W_VOLATILITY * volatility_term,
            "entropy_shift_contribution": W_ENTROPY_SHIFT * entropy_shift_term,
            "coherence_contribution": W_COHERENCE * coherence_term,
        }

        # 5. Determine drift_risk_band
        drift_risk_band = self._classify_risk_band(drift_fusion_index)
        debug["drift_risk_band"] = drift_risk_band

        # 6. Generate drift_pattern_tags
        drift_pattern_tags = self._generate_pattern_tags(
            semantic_integrity=semantic_integrity,
            cognitive_drift=cognitive_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            coherence_fused=coherence_fused,
        )
        debug["drift_pattern_tags"] = drift_pattern_tags

        # 7. Create and return report
        return create_report(
            drift_fusion_index=drift_fusion_index,
            drift_risk_band=drift_risk_band,
            drift_pattern_tags=drift_pattern_tags,
            semantic_integrity_score=semantic_integrity,
            cognitive_drift_v3=cognitive_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            temporal_entropy_volatility=temporal_entropy_volatility,
            coherence_fused=coherence_fused,
            debug=debug,
        )

    def compute_from_values(
        self,
        semantic_integrity_score: Optional[float] = None,
        cognitive_drift_v3: Optional[float] = None,
        temporal_entropy_diff: Optional[float] = None,
        temporal_entropy_volatility: Optional[float] = None,
        coherence_fused: Optional[float] = None,
    ) -> Optional[P19DriftFusionReport]:
        """
        Compute drift fusion from explicit input values.

        This is a convenience method for direct testing without a context object.

        Args:
            semantic_integrity_score: P17 semantic integrity [0, 1]
            cognitive_drift_v3: P17 cognitive drift [0, 1]
            temporal_entropy_diff: P18 normalized entropy diff [0, 1]
            temporal_entropy_volatility: P18 entropy volatility [0, 1]
            coherence_fused: P16 fused coherence [0, 1]

        Returns:
            P19DriftFusionReport with computed metrics, or None if all inputs None
        """
        # Create a mock context with the values
        class MockContext:
            def __init__(self):
                self.coherence_state = type('MockCoherenceState', (), {
                    'semantic_integrity_score': semantic_integrity_score,
                    'cognitive_drift_v3': cognitive_drift_v3,
                    'temporal_entropy_diff': temporal_entropy_diff,
                    'temporal_entropy_volatility': temporal_entropy_volatility,
                    'coherence_fused': coherence_fused,
                })()

        return self.compute(MockContext())

    # -------------------------------------------------------------------------
    # Private extraction methods
    # -------------------------------------------------------------------------

    def _extract_semantic_integrity(self, ctx: Any) -> Optional[float]:
        """
        Extract semantic integrity score from context (P17).

        Checks:
        1. ctx.p17.integrity_score
        2. ctx.coherence_state.semantic_integrity_score
        3. ctx (if it's a CoherenceState directly)

        Args:
            ctx: Pipeline context

        Returns:
            Semantic integrity in [0, 1], or None if not available
        """
        # Try P17 report first
        p17 = getattr(ctx, "p17", None)
        if p17 is not None:
            score = getattr(p17, "integrity_score", None)
            if score is not None and isinstance(score, (int, float)):
                return float(score)

        # Try coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            # ctx might be the coherence_state itself
            coherence_state = ctx

        score = getattr(coherence_state, "semantic_integrity_score", None)
        if score is not None and isinstance(score, (int, float)):
            return float(score)

        return None

    def _extract_cognitive_drift(self, ctx: Any) -> Optional[float]:
        """
        Extract cognitive drift v3 from context (P17).

        Checks:
        1. ctx.coherence_state.cognitive_drift_v3
        2. ctx.cognitive_drift_v3 (if ctx is CoherenceState)

        Args:
            ctx: Pipeline context

        Returns:
            Cognitive drift in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            coherence_state = ctx

        score = getattr(coherence_state, "cognitive_drift_v3", None)
        if score is not None and isinstance(score, (int, float)):
            return float(score)

        return None

    def _extract_temporal_entropy_diff(self, ctx: Any) -> Optional[float]:
        """
        Extract temporal entropy diff from context (P18).

        Checks:
        1. ctx.p18.entropy_now (normalized)
        2. ctx.coherence_state.temporal_entropy_diff
        3. ctx.temporal_entropy_diff (if ctx is CoherenceState)

        Args:
            ctx: Pipeline context

        Returns:
            Temporal entropy diff in [0, 1], or None if not available
        """
        # Try P18 report
        p18 = getattr(ctx, "p18", None)
        if p18 is not None:
            entropy = getattr(p18, "entropy_now", None)
            if entropy is not None and isinstance(entropy, (int, float)):
                return float(entropy)

        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            coherence_state = ctx

        diff = getattr(coherence_state, "temporal_entropy_diff", None)
        if diff is not None and isinstance(diff, (int, float)):
            return float(diff)

        return None

    def _extract_temporal_entropy_volatility(self, ctx: Any) -> Optional[float]:
        """
        Extract temporal entropy volatility from context (P18).

        Checks:
        1. ctx.coherence_state.temporal_entropy_volatility
        2. ctx.temporal_entropy_volatility (if ctx is CoherenceState)

        Args:
            ctx: Pipeline context

        Returns:
            Volatility in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            coherence_state = ctx

        vol = getattr(coherence_state, "temporal_entropy_volatility", None)
        if vol is not None and isinstance(vol, (int, float)):
            return float(vol)

        return None

    def _extract_coherence_fused(self, ctx: Any) -> Optional[float]:
        """
        Extract fused coherence from context (P16).

        Checks:
        1. ctx.coherence_state.coherence_fused
        2. ctx.coherence_fused (if ctx is CoherenceState)

        Args:
            ctx: Pipeline context

        Returns:
            Fused coherence in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            coherence_state = ctx

        fused = getattr(coherence_state, "coherence_fused", None)
        if fused is not None and isinstance(fused, (int, float)):
            return float(fused)

        return None

    def _classify_risk_band(self, index: float) -> str:
        """
        Classify drift risk band from index.

        Args:
            index: Drift fusion index [0, 1]

        Returns:
            Risk band string: "low", "moderate", or "high"
        """
        if index < RISK_BAND_LOW_THRESHOLD:
            return DriftRiskBand.LOW.value
        elif index < RISK_BAND_HIGH_THRESHOLD:
            return DriftRiskBand.MODERATE.value
        else:
            return DriftRiskBand.HIGH.value

    def _generate_pattern_tags(
        self,
        semantic_integrity: Optional[float],
        cognitive_drift: Optional[float],
        temporal_entropy_diff: Optional[float],
        temporal_entropy_volatility: Optional[float],
        coherence_fused: Optional[float],
    ) -> List[str]:
        """
        Generate drift pattern tags based on rule-based thresholds.

        Tags are deterministically assigned based on individual input values
        crossing their respective thresholds.

        Args:
            semantic_integrity: P17 semantic integrity [0, 1]
            cognitive_drift: P17 cognitive drift [0, 1]
            temporal_entropy_diff: P18 entropy diff [0, 1]
            temporal_entropy_volatility: P18 volatility [0, 1]
            coherence_fused: P16 fused coherence [0, 1]

        Returns:
            List of tag strings
        """
        tags = []

        # Semantic drift: low semantic integrity
        if semantic_integrity is not None and semantic_integrity < TAG_SEMANTIC_DRIFT_THRESHOLD:
            tags.append(DriftPatternTag.SEMANTIC_DRIFT.value)

        # Cognitive drift: high drift v3
        if cognitive_drift is not None and cognitive_drift > TAG_COGNITIVE_DRIFT_THRESHOLD:
            tags.append(DriftPatternTag.COGNITIVE_DRIFT.value)

        # Temporal instability: high entropy volatility
        if temporal_entropy_volatility is not None and temporal_entropy_volatility > TAG_TEMPORAL_INSTABILITY_THRESHOLD:
            tags.append(DriftPatternTag.TEMPORAL_INSTABILITY.value)

        # Entropy shift: significant deviation from neutral
        if temporal_entropy_diff is not None and abs(temporal_entropy_diff - 0.5) > TAG_ENTROPY_SHIFT_THRESHOLD:
            tags.append(DriftPatternTag.ENTROPY_SHIFT.value)

        # Low coherence context
        if coherence_fused is not None and coherence_fused < TAG_LOW_COHERENCE_THRESHOLD:
            tags.append(DriftPatternTag.LOW_COHERENCE_CONTEXT.value)

        return tags


# Public exports
__all__ = [
    "P19DriftFusion",
]

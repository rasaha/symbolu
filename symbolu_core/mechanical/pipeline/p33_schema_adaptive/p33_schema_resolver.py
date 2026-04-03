"""
P33 - Schema Adaptive Routing Resolver

Deterministic resolver that computes schema-level stability and alignment
metrics from pipeline context. This is the core computation engine for P33.

CRITICAL CONSTRAINTS (NON-NEGOTIABLE):
- MUST NOT affect Regime (P6), Discourse (P7), Semantics (P8), Lexical (P9), Delivery (P21)
- MUST NOT gate, block, or route anything
- MUST NOT influence Phase 10/12 results
- MUST NOT import P6, P7, P8, P9, Policy, Planner, Renderer, or Observer modules (P22-P24)
- Same inputs → same outputs (bitwise deterministic)
- No randomness, no LLM calls

Design Principles:
- Observation-Only: Never modifies upstream context
- Deterministic: Same inputs always produce same outputs
- Fixed Formula: Weighted blend of stability sources with documented weights
- Conservative: Uses neutral defaults (0.5) for missing inputs

Formula Weights (documented clearly):
    Schema Stability Score:
        stability = W_COHERENCE_V3 * coherence_v3 +
                    W_COHERENCE_QUALITY * coherence_v3_quality +
                    W_DRIFT_INVERSE * (1 - drift_fusion_index) +
                    W_ENTROPY_INVERSE * (1 - temporal_entropy_volatility)

    Schema Alignment Score:
        alignment = W_ALIGN_COHERENCE * coherence_v3 +
                    W_ALIGN_QUALITY * coherence_v3_quality +
                    W_ALIGN_IDENTITY * identity_harmonics_index

    Schema Drift Score:
        drift = W_DRIFT_FUSION * drift_fusion_index +
                W_DRIFT_ENTROPY * temporal_entropy_volatility
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from symbolu_core.mechanical.pipeline.p33_schema_adaptive.p33_schema_snapshot import (
    SchemaAdaptiveRoutingSnapshot,
    SchemaStabilityBand,
    SchemaConfidenceBand,
    ALLOWED_SCHEMA_TAGS,
    P33_VERSION,
    create_snapshot,
    create_empty_snapshot,
)


# ============================================================================
# FORMULA WEIGHTS - Fixed constants for deterministic computation
# All weights are documented and must not be changed without version bump
# ============================================================================

# Stability score weights (sum = 1.0)
W_COHERENCE_V3 = 0.35              # Weight for coherence_v3
W_COHERENCE_QUALITY = 0.25         # Weight for coherence_v3_quality
W_DRIFT_INVERSE = 0.25             # Weight for (1 - drift_fusion_index)
W_ENTROPY_INVERSE = 0.15           # Weight for (1 - temporal_entropy_volatility)

# Alignment score weights (sum = 1.0)
W_ALIGN_COHERENCE = 0.40           # Weight for coherence_v3
W_ALIGN_QUALITY = 0.35             # Weight for coherence_v3_quality
W_ALIGN_IDENTITY = 0.25            # Weight for identity_harmonics_index

# Drift score weights (sum = 1.0)
W_DRIFT_FUSION = 0.70              # Weight for drift_fusion_index
W_DRIFT_ENTROPY = 0.30             # Weight for temporal_entropy_volatility

# Confidence computation weights
W_CONF_DATA_PRESENCE = 0.50        # Weight for input data presence
W_CONF_STABILITY = 0.30            # Weight for stability score
W_CONF_HISTORY = 0.20              # Weight for historical data presence

# Thresholds for band classification
STABILITY_HIGH_THRESHOLD = 0.70
STABILITY_LOW_THRESHOLD = 0.40
CONFIDENCE_HIGH_THRESHOLD = 0.70
CONFIDENCE_LOW_THRESHOLD = 0.40

# Dominant schema selection threshold
DOMINANCE_MARGIN = 0.10            # Min margin above second-best to be "dominant"

# Neutral default for missing inputs
NEUTRAL_DEFAULT = 0.5


# ============================================================================
# DEFAULT SCHEMA DEFINITIONS - Static persona/schema metadata
# These are the default schemas analyzed when no custom metadata is provided
# ============================================================================

DEFAULT_SCHEMA_IDS: Tuple[str, ...] = (
    "analyst",
    "sage",
    "coach",
    "guide",
    "neutral",
)


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P33SchemaAdaptiveResolver:
    """
    P33 Schema Adaptive Routing Resolver - Observation-only phase.

    Computes schema-level stability and alignment metrics from upstream
    signals and produces a SchemaAdaptiveRoutingSnapshot. The resolver
    never modifies upstream state and never influences routing.

    Usage:
        resolver = P33SchemaAdaptiveResolver()
        snapshot = resolver.compute(ctx)

    The snapshot contains:
        - schema_alignment_scores: Per-schema alignment [0, 1]
        - schema_stability_scores: Per-schema stability [0, 1]
        - schema_drift_scores: Per-schema drift [0, 1]
        - dominant_schema: Most stable/aligned schema (or None)
        - confidence: Overall confidence in assessment [0, 1]
        - stability_band: HIGH / MODERATE / LOW / UNKNOWN
        - confidence_band: HIGH / MODERATE / LOW / INSUFFICIENT
        - diagnostic_tags: Frozen set of diagnostic tags
        - debug: Trace information

    INV-P33-1: This resolver cannot influence any decision
    INV-P33-2: All scores are observational only
    INV-P33-3: Dominant schema selection has zero side effects
    INV-P33-4: Observer data (P22-P24) cannot enter this resolver
    """

    def __init__(self) -> None:
        """Initialize the P33 Schema Adaptive Routing resolver."""
        self._version = P33_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def compute(self, ctx: Any) -> SchemaAdaptiveRoutingSnapshot:
        """
        Compute schema adaptive routing snapshot from pipeline context.

        This is the main entry point for P33 analysis. It:
        1. Extracts upstream signals from context (read-only)
        2. Gets schema definitions from context or uses defaults
        3. Computes per-schema stability, alignment, and drift scores
        4. Identifies dominant schema (if any)
        5. Computes overall confidence
        6. Classifies bands and generates diagnostic tags
        7. Produces the SchemaAdaptiveRoutingSnapshot

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            SchemaAdaptiveRoutingSnapshot with computed metrics
        """
        # Track debug information
        debug: Dict[str, Any] = {
            "version": self._version,
            "weights": {
                "stability": {
                    "coherence_v3": W_COHERENCE_V3,
                    "coherence_quality": W_COHERENCE_QUALITY,
                    "drift_inverse": W_DRIFT_INVERSE,
                    "entropy_inverse": W_ENTROPY_INVERSE,
                },
                "alignment": {
                    "coherence": W_ALIGN_COHERENCE,
                    "quality": W_ALIGN_QUALITY,
                    "identity": W_ALIGN_IDENTITY,
                },
                "drift": {
                    "fusion": W_DRIFT_FUSION,
                    "entropy": W_DRIFT_ENTROPY,
                },
            },
            "missing_inputs": [],
        }

        # 1. Extract upstream signals (read-only)
        coherence_v3 = self._extract_coherence_v3(ctx)
        coherence_v3_quality = self._extract_coherence_v3_quality(ctx)
        drift_fusion_index = self._extract_drift_fusion_index(ctx)
        temporal_entropy_volatility = self._extract_temporal_entropy_volatility(ctx)
        identity_harmonics_index = self._extract_identity_harmonics_index(ctx)

        # Track missing inputs
        if coherence_v3 is None:
            debug["missing_inputs"].append("coherence_v3")
            coherence_v3 = NEUTRAL_DEFAULT
        if coherence_v3_quality is None:
            debug["missing_inputs"].append("coherence_v3_quality")
            coherence_v3_quality = NEUTRAL_DEFAULT
        if drift_fusion_index is None:
            debug["missing_inputs"].append("drift_fusion_index")
            drift_fusion_index = NEUTRAL_DEFAULT
        if temporal_entropy_volatility is None:
            debug["missing_inputs"].append("temporal_entropy_volatility")
            temporal_entropy_volatility = NEUTRAL_DEFAULT
        if identity_harmonics_index is None:
            debug["missing_inputs"].append("identity_harmonics_index")
            identity_harmonics_index = NEUTRAL_DEFAULT

        debug["missing_count"] = len(debug["missing_inputs"])

        # Store extracted values in debug
        debug["inputs"] = {
            "coherence_v3": coherence_v3,
            "coherence_v3_quality": coherence_v3_quality,
            "drift_fusion_index": drift_fusion_index,
            "temporal_entropy_volatility": temporal_entropy_volatility,
            "identity_harmonics_index": identity_harmonics_index,
        }

        # 2. Get schema definitions
        schema_ids = self._extract_schema_ids(ctx)
        debug["schema_ids"] = list(schema_ids)
        debug["schema_count"] = len(schema_ids)

        # If no schemas defined, return empty snapshot
        if not schema_ids:
            return create_empty_snapshot()

        # 3. Compute per-schema scores
        schema_stability_scores: Dict[str, float] = {}
        schema_alignment_scores: Dict[str, float] = {}
        schema_drift_scores: Dict[str, float] = {}

        for schema_id in schema_ids:
            # Get schema-specific adjustments (if any)
            schema_adjustment = self._get_schema_adjustment(ctx, schema_id)

            # Compute stability score
            stability = self._compute_stability_score(
                coherence_v3=coherence_v3,
                coherence_v3_quality=coherence_v3_quality,
                drift_fusion_index=drift_fusion_index,
                temporal_entropy_volatility=temporal_entropy_volatility,
                adjustment=schema_adjustment,
            )
            schema_stability_scores[schema_id] = stability

            # Compute alignment score
            alignment = self._compute_alignment_score(
                coherence_v3=coherence_v3,
                coherence_v3_quality=coherence_v3_quality,
                identity_harmonics_index=identity_harmonics_index,
                adjustment=schema_adjustment,
            )
            schema_alignment_scores[schema_id] = alignment

            # Compute drift score
            drift = self._compute_drift_score(
                drift_fusion_index=drift_fusion_index,
                temporal_entropy_volatility=temporal_entropy_volatility,
                adjustment=schema_adjustment,
            )
            schema_drift_scores[schema_id] = drift

        debug["computed_scores"] = {
            "stability": schema_stability_scores,
            "alignment": schema_alignment_scores,
            "drift": schema_drift_scores,
        }

        # 4. Identify dominant schema
        dominant_schema, dominance_margin = self._identify_dominant_schema(
            schema_stability_scores,
            schema_alignment_scores,
        )
        debug["dominant_schema"] = dominant_schema
        debug["dominance_margin"] = dominance_margin

        # 5. Compute overall confidence
        confidence = self._compute_confidence(
            schema_stability_scores=schema_stability_scores,
            missing_count=debug["missing_count"],
            has_history=self._has_history(ctx),
        )
        debug["confidence"] = confidence

        # 6. Classify bands
        stability_band = self._classify_stability_band(schema_stability_scores)
        confidence_band = self._classify_confidence_band(confidence)

        # 7. Generate diagnostic tags
        diagnostic_tags = self._generate_diagnostic_tags(
            schema_stability_scores=schema_stability_scores,
            schema_alignment_scores=schema_alignment_scores,
            schema_drift_scores=schema_drift_scores,
            dominant_schema=dominant_schema,
            confidence=confidence,
            missing_count=debug["missing_count"],
        )
        debug["diagnostic_tags"] = sorted(diagnostic_tags)

        # 8. Create and return snapshot
        return create_snapshot(
            schema_alignment_scores=schema_alignment_scores,
            schema_stability_scores=schema_stability_scores,
            schema_drift_scores=schema_drift_scores,
            dominant_schema=dominant_schema,
            confidence=confidence,
            stability_band=stability_band,
            confidence_band=confidence_band,
            diagnostic_tags=diagnostic_tags,
            debug=debug,
        )

    # ========================================================================
    # EXTRACTION METHODS - Read-only access to context
    # ========================================================================

    def _extract_coherence_v3(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence_v3 from context.

        Checks:
        1. ctx.coherence_state.coherence_score_v3

        Args:
            ctx: Pipeline context

        Returns:
            Coherence v3 score in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        v3 = getattr(coherence_state, "coherence_score_v3", None)
        if v3 is not None and isinstance(v3, (int, float)):
            return max(0.0, min(1.0, float(v3)))

        return None

    def _extract_coherence_v3_quality(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence_v3_quality from context.

        Checks:
        1. ctx.coherence_state.coherence_v3_quality

        Args:
            ctx: Pipeline context

        Returns:
            Coherence v3 quality in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        quality = getattr(coherence_state, "coherence_v3_quality", None)
        if quality is not None and isinstance(quality, (int, float)):
            return max(0.0, min(1.0, float(quality)))

        return None

    def _extract_drift_fusion_index(self, ctx: Any) -> Optional[float]:
        """
        Extract drift_fusion_index from P19 or coherence_state.

        Checks:
        1. ctx.coherence_state.drift_fusion_index

        Args:
            ctx: Pipeline context

        Returns:
            Drift fusion index in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        drift = getattr(coherence_state, "drift_fusion_index", None)
        if drift is not None and isinstance(drift, (int, float)):
            return max(0.0, min(1.0, float(drift)))

        return None

    def _extract_temporal_entropy_volatility(self, ctx: Any) -> Optional[float]:
        """
        Extract temporal_entropy_volatility from P18 or coherence_state.

        Checks:
        1. ctx.coherence_state.temporal_entropy_volatility

        Args:
            ctx: Pipeline context

        Returns:
            Temporal entropy volatility in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        volatility = getattr(coherence_state, "temporal_entropy_volatility", None)
        if volatility is not None and isinstance(volatility, (int, float)):
            return max(0.0, min(1.0, float(volatility)))

        return None

    def _extract_identity_harmonics_index(self, ctx: Any) -> Optional[float]:
        """
        Extract identity_harmonics_index from coherence_state.

        Checks:
        1. ctx.coherence_state.current_identity_harmonics_index

        Args:
            ctx: Pipeline context

        Returns:
            Identity harmonics index in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        index = getattr(coherence_state, "current_identity_harmonics_index", None)
        if index is not None and isinstance(index, (int, float)):
            return max(0.0, min(1.0, float(index)))

        return None

    def _extract_schema_ids(self, ctx: Any) -> Tuple[str, ...]:
        """
        Extract schema IDs from context or use defaults.

        Checks:
        1. ctx.persona_schema_metadata (if present and has schema_ids)
        2. Falls back to DEFAULT_SCHEMA_IDS

        Args:
            ctx: Pipeline context

        Returns:
            Tuple of schema ID strings
        """
        # Check for custom schema metadata
        metadata = getattr(ctx, "persona_schema_metadata", None)
        if metadata is not None:
            schema_ids = getattr(metadata, "schema_ids", None)
            if schema_ids and isinstance(schema_ids, (list, tuple)):
                return tuple(str(s) for s in schema_ids)

        # Fall back to defaults
        return DEFAULT_SCHEMA_IDS

    def _get_schema_adjustment(self, ctx: Any, schema_id: str) -> float:
        """
        Get schema-specific adjustment factor (if any).

        This allows for per-schema tuning based on metadata.
        Currently returns 0.0 (no adjustment) for all schemas.

        Args:
            ctx: Pipeline context
            schema_id: Schema identifier

        Returns:
            Adjustment factor in [-0.1, +0.1], defaults to 0.0
        """
        # Check for schema-specific adjustments in metadata
        metadata = getattr(ctx, "persona_schema_metadata", None)
        if metadata is not None:
            adjustments = getattr(metadata, "schema_adjustments", None)
            if adjustments and isinstance(adjustments, dict):
                adj = adjustments.get(schema_id, 0.0)
                if isinstance(adj, (int, float)):
                    return max(-0.1, min(0.1, float(adj)))

        return 0.0

    def _has_history(self, ctx: Any) -> bool:
        """
        Check if historical data is present in coherence_state.

        Args:
            ctx: Pipeline context

        Returns:
            True if meaningful history exists
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return False

        # Check various history fields
        for history_attr in [
            "drift_fusion_index_history",
            "temporal_entropy_diff_history",
            "coherence_fused_history",
        ]:
            history = getattr(coherence_state, history_attr, None)
            if history and isinstance(history, list) and len(history) >= 2:
                return True

        return False

    # ========================================================================
    # COMPUTATION METHODS - Deterministic formulas
    # ========================================================================

    def _compute_stability_score(
        self,
        coherence_v3: float,
        coherence_v3_quality: float,
        drift_fusion_index: float,
        temporal_entropy_volatility: float,
        adjustment: float = 0.0,
    ) -> float:
        """
        Compute stability score using weighted formula.

        Formula:
            stability = W_COHERENCE_V3 * coherence_v3 +
                        W_COHERENCE_QUALITY * coherence_v3_quality +
                        W_DRIFT_INVERSE * (1 - drift_fusion_index) +
                        W_ENTROPY_INVERSE * (1 - temporal_entropy_volatility) +
                        adjustment

        Args:
            coherence_v3: Coherence v3 score [0, 1]
            coherence_v3_quality: Coherence quality [0, 1]
            drift_fusion_index: Drift fusion index [0, 1]
            temporal_entropy_volatility: Entropy volatility [0, 1]
            adjustment: Schema-specific adjustment [-0.1, +0.1]

        Returns:
            Stability score clamped to [0.0, 1.0]
        """
        stability = (
            W_COHERENCE_V3 * coherence_v3 +
            W_COHERENCE_QUALITY * coherence_v3_quality +
            W_DRIFT_INVERSE * (1.0 - drift_fusion_index) +
            W_ENTROPY_INVERSE * (1.0 - temporal_entropy_volatility) +
            adjustment
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, stability))

    def _compute_alignment_score(
        self,
        coherence_v3: float,
        coherence_v3_quality: float,
        identity_harmonics_index: float,
        adjustment: float = 0.0,
    ) -> float:
        """
        Compute alignment score using weighted formula.

        Formula:
            alignment = W_ALIGN_COHERENCE * coherence_v3 +
                        W_ALIGN_QUALITY * coherence_v3_quality +
                        W_ALIGN_IDENTITY * identity_harmonics_index +
                        adjustment

        Args:
            coherence_v3: Coherence v3 score [0, 1]
            coherence_v3_quality: Coherence quality [0, 1]
            identity_harmonics_index: Identity harmonics index [0, 1]
            adjustment: Schema-specific adjustment [-0.1, +0.1]

        Returns:
            Alignment score clamped to [0.0, 1.0]
        """
        alignment = (
            W_ALIGN_COHERENCE * coherence_v3 +
            W_ALIGN_QUALITY * coherence_v3_quality +
            W_ALIGN_IDENTITY * identity_harmonics_index +
            adjustment
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, alignment))

    def _compute_drift_score(
        self,
        drift_fusion_index: float,
        temporal_entropy_volatility: float,
        adjustment: float = 0.0,
    ) -> float:
        """
        Compute drift score using weighted formula.

        Formula:
            drift = W_DRIFT_FUSION * drift_fusion_index +
                    W_DRIFT_ENTROPY * temporal_entropy_volatility +
                    adjustment

        Args:
            drift_fusion_index: Drift fusion index [0, 1]
            temporal_entropy_volatility: Entropy volatility [0, 1]
            adjustment: Schema-specific adjustment [-0.1, +0.1]

        Returns:
            Drift score clamped to [0.0, 1.0]
        """
        drift = (
            W_DRIFT_FUSION * drift_fusion_index +
            W_DRIFT_ENTROPY * temporal_entropy_volatility +
            adjustment
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, drift))

    def _identify_dominant_schema(
        self,
        stability_scores: Dict[str, float],
        alignment_scores: Dict[str, float],
    ) -> Tuple[Optional[str], float]:
        """
        Identify the dominant schema based on combined stability and alignment.

        A schema is considered dominant if:
        1. It has the highest combined score (stability + alignment) / 2
        2. Its margin above the second-best is >= DOMINANCE_MARGIN

        Args:
            stability_scores: Per-schema stability scores
            alignment_scores: Per-schema alignment scores

        Returns:
            Tuple of (dominant_schema_id or None, margin above second-best)
        """
        if not stability_scores:
            return None, 0.0

        # Compute combined scores
        combined_scores: Dict[str, float] = {}
        for schema_id in stability_scores:
            stability = stability_scores.get(schema_id, 0.0)
            alignment = alignment_scores.get(schema_id, 0.0)
            combined_scores[schema_id] = (stability + alignment) / 2.0

        # Sort by combined score (descending)
        sorted_schemas = sorted(
            combined_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        if len(sorted_schemas) < 1:
            return None, 0.0

        best_schema, best_score = sorted_schemas[0]

        if len(sorted_schemas) < 2:
            # Only one schema, it's dominant by default
            return best_schema, 1.0

        _, second_score = sorted_schemas[1]
        margin = best_score - second_score

        # Check if margin is sufficient
        if margin >= DOMINANCE_MARGIN:
            return best_schema, margin
        else:
            return None, margin

    def _compute_confidence(
        self,
        schema_stability_scores: Dict[str, float],
        missing_count: int,
        has_history: bool,
    ) -> float:
        """
        Compute overall confidence in the assessment.

        Formula:
            confidence = W_CONF_DATA_PRESENCE * data_presence_score +
                         W_CONF_STABILITY * avg_stability +
                         W_CONF_HISTORY * history_score

        Args:
            schema_stability_scores: Per-schema stability scores
            missing_count: Number of missing inputs
            has_history: Whether historical data is present

        Returns:
            Confidence score clamped to [0.0, 1.0]
        """
        # Data presence score (penalize for missing inputs)
        max_missing = 5  # Maximum expected inputs
        data_presence = max(0.0, 1.0 - (missing_count / max_missing))

        # Average stability score
        if schema_stability_scores:
            avg_stability = sum(schema_stability_scores.values()) / len(schema_stability_scores)
        else:
            avg_stability = 0.0

        # History presence score
        history_score = 1.0 if has_history else 0.3

        # Compute weighted confidence
        confidence = (
            W_CONF_DATA_PRESENCE * data_presence +
            W_CONF_STABILITY * avg_stability +
            W_CONF_HISTORY * history_score
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, confidence))

    # ========================================================================
    # CLASSIFICATION METHODS
    # ========================================================================

    def _classify_stability_band(
        self,
        stability_scores: Dict[str, float],
    ) -> SchemaStabilityBand:
        """
        Classify overall stability band based on average stability.

        Args:
            stability_scores: Per-schema stability scores

        Returns:
            SchemaStabilityBand classification
        """
        if not stability_scores:
            return SchemaStabilityBand.UNKNOWN

        avg_stability = sum(stability_scores.values()) / len(stability_scores)

        if avg_stability >= STABILITY_HIGH_THRESHOLD:
            return SchemaStabilityBand.HIGH
        elif avg_stability >= STABILITY_LOW_THRESHOLD:
            return SchemaStabilityBand.MODERATE
        else:
            return SchemaStabilityBand.LOW

    def _classify_confidence_band(
        self,
        confidence: float,
    ) -> SchemaConfidenceBand:
        """
        Classify confidence band based on confidence score.

        Args:
            confidence: Confidence score [0, 1]

        Returns:
            SchemaConfidenceBand classification
        """
        if confidence >= CONFIDENCE_HIGH_THRESHOLD:
            return SchemaConfidenceBand.HIGH
        elif confidence >= CONFIDENCE_LOW_THRESHOLD:
            return SchemaConfidenceBand.MODERATE
        elif confidence > 0.1:
            return SchemaConfidenceBand.LOW
        else:
            return SchemaConfidenceBand.INSUFFICIENT

    def _generate_diagnostic_tags(
        self,
        schema_stability_scores: Dict[str, float],
        schema_alignment_scores: Dict[str, float],
        schema_drift_scores: Dict[str, float],
        dominant_schema: Optional[str],
        confidence: float,
        missing_count: int,
    ) -> FrozenSet[str]:
        """
        Generate diagnostic tags based on computed metrics.

        Tags are drawn from ALLOWED_SCHEMA_TAGS only.

        Args:
            schema_stability_scores: Per-schema stability scores
            schema_alignment_scores: Per-schema alignment scores
            schema_drift_scores: Per-schema drift scores
            dominant_schema: Identified dominant schema (or None)
            confidence: Confidence score
            missing_count: Number of missing inputs

        Returns:
            Frozen set of diagnostic tags
        """
        tags: List[str] = []

        # Schema count check
        if not schema_stability_scores:
            tags.append("NO_SCHEMAS_DEFINED")
            return frozenset(tags)

        # Stability tags
        avg_stability = sum(schema_stability_scores.values()) / len(schema_stability_scores)
        if avg_stability >= STABILITY_HIGH_THRESHOLD:
            tags.append("HIGHLY_STABLE")
        elif avg_stability >= STABILITY_LOW_THRESHOLD:
            tags.append("MODERATELY_STABLE")
        else:
            tags.append("LOW_STABILITY")

        # Alignment tags
        avg_alignment = sum(schema_alignment_scores.values()) / len(schema_alignment_scores)
        if avg_alignment >= 0.7:
            tags.append("ALIGNED")
        elif avg_alignment >= 0.4:
            tags.append("NEUTRAL_ALIGNMENT")
        else:
            tags.append("MISALIGNED")

        # Drift tags
        avg_drift = sum(schema_drift_scores.values()) / len(schema_drift_scores)
        if avg_drift < 0.3:
            tags.append("LOW_DRIFT")
        elif avg_drift < 0.65:
            tags.append("MODERATE_DRIFT")
        else:
            tags.append("HIGH_DRIFT")

        # Confidence tags
        if confidence >= CONFIDENCE_HIGH_THRESHOLD:
            tags.append("HIGH_CONFIDENCE")
        elif confidence >= CONFIDENCE_LOW_THRESHOLD:
            tags.append("MODERATE_CONFIDENCE")
        else:
            tags.append("LOW_CONFIDENCE")

        # Dominant schema tags
        if dominant_schema is not None:
            tags.append("DOMINANT_CLEAR")
        elif len(schema_stability_scores) > 1:
            tags.append("MULTIPLE_CANDIDATES")
        else:
            tags.append("DOMINANT_UNCLEAR")

        # History check
        if missing_count >= 3:
            tags.append("INSUFFICIENT_HISTORY")

        # Filter to allowed tags only (safety check)
        valid_tags = [t for t in tags if t in ALLOWED_SCHEMA_TAGS]

        return frozenset(valid_tags)


# Public exports
__all__ = [
    "P33SchemaAdaptiveResolver",
    # Weights (for testing/validation)
    "W_COHERENCE_V3",
    "W_COHERENCE_QUALITY",
    "W_DRIFT_INVERSE",
    "W_ENTROPY_INVERSE",
    "W_ALIGN_COHERENCE",
    "W_ALIGN_QUALITY",
    "W_ALIGN_IDENTITY",
    "W_DRIFT_FUSION",
    "W_DRIFT_ENTROPY",
    "W_CONF_DATA_PRESENCE",
    "W_CONF_STABILITY",
    "W_CONF_HISTORY",
    # Thresholds
    "STABILITY_HIGH_THRESHOLD",
    "STABILITY_LOW_THRESHOLD",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_LOW_THRESHOLD",
    "DOMINANCE_MARGIN",
    "NEUTRAL_DEFAULT",
    # Defaults
    "DEFAULT_SCHEMA_IDS",
]

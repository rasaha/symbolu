"""
Phase 32 - Insight Gating Engine

Main engine for computing insight window gating decisions.
Combines the locked formula with input extraction and envelope creation.

CRITICAL INVARIANTS:
- INV-P32-1: Insight gating never opens due to observers
- INV-P32-2: Gate monotonicity enforced
- INV-P32-3: No upstream influence
- INV-P32-4: Deterministic behavior
- INV-P32-5: Envelope is advisory only

WHAT THIS ENGINE DOES:
- Reads metrics from PipelineContext (read-only)
- Computes insight depth using the LOCKED formula
- Applies monotonic penalties
- Produces an InsightWindowEnvelope

WHAT THIS ENGINE DOES NOT DO:
- Trigger regime changes (P6)
- Select discourse acts (P7)
- Modify semantics or lexical frames (P8-P9)
- Influence persona, DHA, renderer
- Trigger actions or agent handoff
- Open insight windows due to acoustic input alone

Design Principle:
    This engine decides WHEN insight is allowed, NOT what insight is given.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from .insight_envelope import (
    InsightWindowEnvelope,
    ConfidenceBand,
    create_envelope,
    create_closed_envelope,
    INSIGHT_GATE_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
)

from .insight_gating_formula import (
    compute_insight_depth,
    FormulaResult,
    NEUTRAL_DEFAULT,
)


# ============================================================================
# ENGINE CLASS
# ============================================================================


class InsightGatingEngine:
    """
    Engine for computing insight window gating decisions.

    This engine extracts metrics from a PipelineContext (or equivalent),
    computes insight depth using the LOCKED formula, and produces an
    immutable InsightWindowEnvelope.

    Usage:
        engine = InsightGatingEngine()
        envelope = engine.compute(ctx)

        if envelope.is_open:
            # Insight window is open
            pass

    CRITICAL: The envelope is advisory only. It MUST NOT be used to
    influence any authoritative decisions in the pipeline.
    """

    def __init__(self) -> None:
        """Initialize the InsightGatingEngine."""
        pass  # Stateless engine

    def compute(self, ctx: Any) -> InsightWindowEnvelope:
        """
        Compute insight gating decision from pipeline context.

        Args:
            ctx: PipelineContext or compatible object with:
                - coherence_state (for coherence_v3_quality, drift_fusion_index)
                - p18 (for temporal_entropy_diff)
                - p26 (for ucf_score)
                - p33 (for schema_stability)
                - p23_alignment_report (optional, for acoustic_alignment)

        Returns:
            InsightWindowEnvelope with gating decision

        Note:
            Returns a closed envelope if required metrics are unavailable.
        """
        # Extract metrics from context
        metrics = self._extract_metrics(ctx)

        # Check for minimum viable inputs
        if not self._has_minimum_inputs(metrics):
            return create_closed_envelope(
                reason="MISSING_INPUTS",
                debug={"metrics": metrics, "reason": "insufficient_data"},
            )

        # Compute insight depth using LOCKED formula
        result = compute_insight_depth(
            coherence_v3_quality=metrics.get("coherence_v3_quality"),
            ucf_score=metrics.get("ucf_score"),
            schema_stability=metrics.get("schema_stability"),
            drift_fusion_index=metrics.get("drift_fusion_index"),
            temporal_entropy_diff=metrics.get("temporal_entropy_diff"),
            acoustic_alignment_score=metrics.get("acoustic_alignment_score"),
        )

        # Build envelope from formula result
        return self._build_envelope(result, metrics)

    def compute_directly(
        self,
        coherence_v3_quality: Optional[float] = None,
        ucf_score: Optional[float] = None,
        schema_stability: Optional[float] = None,
        drift_fusion_index: Optional[float] = None,
        temporal_entropy_diff: Optional[float] = None,
        acoustic_alignment_score: Optional[float] = None,
    ) -> InsightWindowEnvelope:
        """
        Compute insight gating decision with explicit inputs (for testing).

        This bypasses context extraction and allows direct testing
        of the gating formula with explicit values.

        Args:
            coherence_v3_quality: P10/P12 coherence v3 quality [0.0, 1.0]
            ucf_score: P26 unified consciousness formula score [0.0, 1.0]
            schema_stability: P33 schema stability score [0.0, 1.0]
            drift_fusion_index: P19 drift fusion index [0.0, 1.0]
            temporal_entropy_diff: P18 temporal entropy differential [0.0, 1.0]
            acoustic_alignment_score: Optional acoustic alignment [0.0, 1.0]

        Returns:
            InsightWindowEnvelope with gating decision
        """
        # Compute insight depth using LOCKED formula
        result = compute_insight_depth(
            coherence_v3_quality=coherence_v3_quality,
            ucf_score=ucf_score,
            schema_stability=schema_stability,
            drift_fusion_index=drift_fusion_index,
            temporal_entropy_diff=temporal_entropy_diff,
            acoustic_alignment_score=acoustic_alignment_score,
        )

        metrics = {
            "coherence_v3_quality": coherence_v3_quality,
            "ucf_score": ucf_score,
            "schema_stability": schema_stability,
            "drift_fusion_index": drift_fusion_index,
            "temporal_entropy_diff": temporal_entropy_diff,
            "acoustic_alignment_score": acoustic_alignment_score,
        }

        return self._build_envelope(result, metrics)

    def _extract_metrics(self, ctx: Any) -> Dict[str, Optional[float]]:
        """
        Extract relevant metrics from pipeline context.

        Reads from:
        - ctx.coherence_state (coherence_v3_quality, drift_fusion_index)
        - ctx.p18 (temporal_entropy_diff)
        - ctx.p26 (ucf_score)
        - ctx.p33 (schema_stability via confidence)
        - ctx.p23_alignment_report (acoustic_alignment_score, optional)

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            Dictionary of metric names to values (None if unavailable)
        """
        metrics: Dict[str, Optional[float]] = {
            "coherence_v3_quality": None,
            "drift_fusion_index": None,
            "temporal_entropy_diff": None,
            "ucf_score": None,
            "schema_stability": None,
            "acoustic_alignment_score": None,
        }

        # Extract from coherence_state
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            metrics["coherence_v3_quality"] = getattr(
                coherence_state, "coherence_v3_quality", None
            )
            metrics["drift_fusion_index"] = getattr(
                coherence_state, "drift_fusion_index", None
            )

        # Extract from P18 temporal entropy report
        p18 = getattr(ctx, "p18", None)
        if p18 is not None:
            # Try delta_entropy first, fall back to temporal_entropy_diff
            metrics["temporal_entropy_diff"] = getattr(
                p18, "delta_entropy",
                getattr(p18, "temporal_entropy_diff", None)
            )

        # Extract from P26 UCF state
        p26 = getattr(ctx, "p26", None)
        if p26 is not None:
            metrics["ucf_score"] = getattr(p26, "ucf_score", None)

        # Extract from P33 schema adaptive routing
        p33 = getattr(ctx, "p33", None)
        if p33 is not None:
            # Use confidence as proxy for schema_stability
            metrics["schema_stability"] = getattr(p33, "confidence", None)

        # Extract acoustic alignment (observer-only, optional)
        # CRITICAL: This is read-only from P23. P32 never imports P22/P23/P24 directly.
        p23 = getattr(ctx, "p23_alignment_report", None)
        if p23 is not None:
            metrics["acoustic_alignment_score"] = getattr(
                p23, "alignment_score", None
            )

        return metrics

    def _has_minimum_inputs(self, metrics: Dict[str, Optional[float]]) -> bool:
        """
        Check if minimum required inputs are present.

        Requires at least coherence_v3_quality OR ucf_score to be present.

        Args:
            metrics: Dictionary of extracted metrics

        Returns:
            True if minimum inputs are present
        """
        # Need at least one core metric
        has_coherence = metrics.get("coherence_v3_quality") is not None
        has_ucf = metrics.get("ucf_score") is not None

        return has_coherence or has_ucf

    def _build_envelope(
        self,
        result: FormulaResult,
        metrics: Dict[str, Optional[float]],
    ) -> InsightWindowEnvelope:
        """
        Build InsightWindowEnvelope from formula result.

        Args:
            result: FormulaResult from compute_insight_depth
            metrics: Original extracted metrics

        Returns:
            InsightWindowEnvelope with gating decision
        """
        # Determine confidence band based on input availability and depth
        confidence_band = self._compute_confidence_band(result, metrics)

        # Build reason codes
        reason_codes = list(result.reason_codes)

        # Add gate state reason
        if result.final_depth >= INSIGHT_GATE_THRESHOLD:
            reason_codes.append("GATE_OPEN")
        else:
            reason_codes.append("GATE_CLOSED")
            reason_codes.append("DEPTH_BELOW_THRESHOLD")

        # Add reason codes for specific low metrics
        if metrics.get("ucf_score") is not None and metrics["ucf_score"] < 0.4:
            if "LOW_UCF_SCORE" not in reason_codes:
                reason_codes.append("LOW_UCF_SCORE")

        if metrics.get("schema_stability") is not None and metrics["schema_stability"] < 0.4:
            if "LOW_SCHEMA_STABILITY" not in reason_codes:
                reason_codes.append("LOW_SCHEMA_STABILITY")

        if metrics.get("drift_fusion_index") is not None and metrics["drift_fusion_index"] > 0.6:
            if "ELEVATED_DRIFT" not in reason_codes:
                reason_codes.append("ELEVATED_DRIFT")

        return create_envelope(
            insight_depth=result.final_depth,
            raw_depth=result.raw_depth,
            gating_reason_codes=reason_codes,
            confidence_band=confidence_band,
            penalties_applied=result.penalties_applied,
            debug={
                "inputs_used": result.inputs_used,
                "extracted_metrics": {k: v for k, v in metrics.items() if v is not None},
            },
        )

    def _compute_confidence_band(
        self,
        result: FormulaResult,
        metrics: Dict[str, Optional[float]],
    ) -> ConfidenceBand:
        """
        Compute confidence band based on input availability and results.

        Args:
            result: FormulaResult from formula computation
            metrics: Extracted metrics

        Returns:
            ConfidenceBand classification
        """
        # Count available inputs
        available_count = sum(1 for v in metrics.values() if v is not None)
        total_inputs = 6  # coherence, drift, entropy, ucf, schema, acoustic

        # Input availability factor
        input_factor = available_count / total_inputs

        # Penalty factor (fewer penalties = higher confidence)
        penalty_factor = 1.0 - (len(result.penalties_applied) * 0.15)
        penalty_factor = max(0.0, penalty_factor)

        # Depth factor (higher depth = higher confidence in accuracy)
        depth_factor = result.raw_depth

        # Combined confidence
        confidence = (input_factor * 0.4) + (penalty_factor * 0.3) + (depth_factor * 0.3)

        if confidence >= CONFIDENCE_HIGH_THRESHOLD:
            return ConfidenceBand.HIGH
        elif confidence >= CONFIDENCE_LOW_THRESHOLD:
            return ConfidenceBand.MEDIUM
        else:
            return ConfidenceBand.LOW


# ============================================================================
# SINGLETON ACCESS
# ============================================================================

_engine_instance: Optional[InsightGatingEngine] = None


def get_insight_gating_engine() -> InsightGatingEngine:
    """
    Get the singleton InsightGatingEngine instance.

    Returns:
        InsightGatingEngine instance
    """
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = InsightGatingEngine()
    return _engine_instance


# Public exports
__all__ = [
    "InsightGatingEngine",
    "get_insight_gating_engine",
]

"""
P35 - Predictive Persona Drift Pipeline Integration

Integration functions for running P35 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu.mechanical.pipeline.p35_predictive_persona_drift import maybe_run_p35

    # In pipeline after P19, P33, P34:
    maybe_run_p35(ctx)

    # Access report:
    if ctx.p35 is not None:
        print(f"Predicted drift: {ctx.p35.predicted_drift_score}")
        print(f"Risk band: {ctx.p35.drift_risk_band}")

CRITICAL CONSTRAINTS:
    ❌ Must NOT:
        - Change regime (P6)
        - Change discourse (P7)
        - Change semantics or lexical selection (P8–P9)
        - Influence DHA, Persona Engine, Renderer
        - Influence insight gating (P32)
        - Infer intent or emotion
        - Gate actions or trigger side effects

INVARIANTS:
    - INV-P35-1: Forecast never influences current decisions
    - INV-P35-2: Prediction never escalates authority
    - INV-P35-3: Observer-only behavior enforced
    - INV-P35-4: Deterministic math only
    - INV-P35-5: No acoustic dependency
"""

from __future__ import annotations

from typing import Any, List, Optional

from symbolu.core.predictive.persona_drift import (
    P35_VERSION,
    PredictivePersonaDriftReport,
    create_report,
    create_empty_report,
    risk_band_from_score,
    compute_base_drift_score,
    compute_confidence,
    compute_contributing_factors,
    compute_signal_variance,
    analyze_trend_from_histories,
)


# ============================================================================
# DEFAULT CONFIGURATION
# ============================================================================

DEFAULT_HISTORY_WINDOW = 3  # Default number of historical snapshots to use


# ============================================================================
# P35 RESOLVER CLASS
# ============================================================================


class P35PredictivePersonaDrift:
    """
    Resolver for Phase 35: Predictive Persona Drift Model.

    This class:
    - Extracts input signals from PipelineContext
    - Computes predicted drift score using the locked formula
    - Analyzes trend direction from historical snapshots
    - Computes confidence from historical variance
    - Produces an immutable PredictivePersonaDriftReport

    INVARIANTS:
        - INV-P35-3: Observer-only behavior enforced
        - INV-P35-4: Deterministic math only
        - INV-P35-5: No acoustic dependency
    """

    def __init__(self, history_window: int = DEFAULT_HISTORY_WINDOW) -> None:
        """
        Initialize P35 resolver.

        Args:
            history_window: Number of historical snapshots to use (default 3)
        """
        self._version = P35_VERSION
        self._history_window = history_window

    @property
    def version(self) -> str:
        """Return the resolver version."""
        return self._version

    @property
    def history_window(self) -> int:
        """Return the history window size."""
        return self._history_window

    def compute(self, ctx: Any) -> Optional[PredictivePersonaDriftReport]:
        """
        Compute predictive persona drift from pipeline context.

        This is the main entry point for the resolver. It:
        1. Extracts input signals from context
        2. Computes the base drift score
        3. Analyzes trend direction
        4. Computes confidence
        5. Returns an immutable report

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            PredictivePersonaDriftReport if computation possible, None otherwise
        """
        # Extract current input signals
        drift_fusion_index = self._extract_drift_fusion_index(ctx)
        schema_drift = self._extract_schema_drift(ctx)
        temporal_entropy_diff = self._extract_temporal_entropy_diff(ctx)
        coherence_v3_quality = self._extract_coherence_v3_quality(ctx)
        ucf_score = self._extract_ucf_score(ctx)
        identity_harmonics_score = self._extract_identity_harmonics_score(ctx)

        # Check if we have any inputs
        all_none = all(
            v is None for v in [
                drift_fusion_index,
                schema_drift,
                temporal_entropy_diff,
                coherence_v3_quality,
                ucf_score,
            ]
        )

        if all_none:
            # No inputs available, return None
            return None

        # Apply neutral defaults for missing inputs
        dfi = drift_fusion_index if drift_fusion_index is not None else 0.0
        sd = schema_drift if schema_drift is not None else 0.0
        ted = temporal_entropy_diff if temporal_entropy_diff is not None else 0.0
        cq = coherence_v3_quality if coherence_v3_quality is not None else 1.0
        ucf = ucf_score if ucf_score is not None else 1.0

        # Compute base drift score
        predicted_drift_score = compute_base_drift_score(
            drift_fusion_index=dfi,
            schema_drift=sd,
            temporal_entropy_diff=ted,
            coherence_v3_quality=cq,
            ucf_score=ucf,
        )

        # Determine risk band
        drift_risk_band = risk_band_from_score(predicted_drift_score)

        # Extract historical data for trend analysis
        histories = self._extract_histories(ctx)

        # Analyze trend direction
        trend_direction = analyze_trend_from_histories(
            drift_fusion_index_history=histories.get("drift_fusion_index"),
            schema_drift_history=histories.get("schema_drift"),
            temporal_entropy_diff_history=histories.get("temporal_entropy_diff"),
            coherence_v3_quality_history=histories.get("coherence_v3_quality"),
            ucf_score_history=histories.get("ucf_score"),
            identity_harmonics_history=histories.get("identity_harmonics"),
            window_size=self._history_window,
        )

        # Compute confidence from historical variance
        drift_score_history = histories.get("predicted_drift_score", [])
        confidence = compute_confidence(
            [s for s in drift_score_history if s is not None]
        )

        # Compute signal variance for cross-signal volatility detection
        signal_variance = compute_signal_variance(
            drift_fusion_index=dfi,
            schema_drift=sd,
            temporal_entropy_diff=ted,
            coherence_v3_quality=cq,
            ucf_score=ucf,
        )

        # Compute contributing factors
        contributing_factors = compute_contributing_factors(
            drift_fusion_index=drift_fusion_index,
            schema_drift=schema_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            coherence_v3_quality=coherence_v3_quality,
            ucf_score=ucf_score,
            identity_harmonics_score=identity_harmonics_score,
            signal_variance=signal_variance,
        )

        # Count history snapshots
        history_count = max(
            len(histories.get("drift_fusion_index", [])),
            len(histories.get("schema_drift", [])),
            len(histories.get("temporal_entropy_diff", [])),
        )

        # Build debug info
        debug = {
            "inputs_used": {
                "drift_fusion_index": dfi,
                "schema_drift": sd,
                "temporal_entropy_diff": ted,
                "coherence_v3_quality": cq,
                "ucf_score": ucf,
            },
            "signal_variance": signal_variance,
            "history_window": self._history_window,
        }

        # Create and return report
        return create_report(
            predicted_drift_score=predicted_drift_score,
            drift_risk_band=drift_risk_band,
            trend_direction=trend_direction,
            contributing_factors=contributing_factors,
            confidence=confidence,
            drift_fusion_index=drift_fusion_index,
            schema_drift=schema_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            coherence_v3_quality=coherence_v3_quality,
            ucf_score=ucf_score,
            identity_harmonics_score=identity_harmonics_score,
            history_snapshot_count=history_count,
            debug=debug,
        )

    def compute_from_values(
        self,
        drift_fusion_index: Optional[float] = None,
        schema_drift: Optional[float] = None,
        temporal_entropy_diff: Optional[float] = None,
        coherence_v3_quality: Optional[float] = None,
        ucf_score: Optional[float] = None,
        identity_harmonics_score: Optional[float] = None,
        drift_fusion_index_history: Optional[List[Optional[float]]] = None,
        schema_drift_history: Optional[List[Optional[float]]] = None,
        temporal_entropy_diff_history: Optional[List[Optional[float]]] = None,
        coherence_v3_quality_history: Optional[List[Optional[float]]] = None,
        ucf_score_history: Optional[List[Optional[float]]] = None,
        identity_harmonics_history: Optional[List[Optional[float]]] = None,
        predicted_drift_score_history: Optional[List[Optional[float]]] = None,
    ) -> Optional[PredictivePersonaDriftReport]:
        """
        Compute predictive persona drift from explicit values (for testing).

        This bypasses context extraction and allows direct testing
        with mock values.

        Args:
            drift_fusion_index: P19 drift fusion index [0, 1]
            schema_drift: P33 schema drift [0, 1]
            temporal_entropy_diff: P18 temporal entropy diff [0, 1]
            coherence_v3_quality: P12 coherence v3 quality [0, 1]
            ucf_score: P26 UCF score [0, 1]
            identity_harmonics_score: P34 identity harmonics [0, 1]
            drift_fusion_index_history: History of drift fusion index
            schema_drift_history: History of schema drift
            temporal_entropy_diff_history: History of temporal entropy diff
            coherence_v3_quality_history: History of coherence v3 quality
            ucf_score_history: History of UCF score
            identity_harmonics_history: History of identity harmonics
            predicted_drift_score_history: History of predicted drift scores

        Returns:
            PredictivePersonaDriftReport if inputs valid, None otherwise
        """
        # Check if we have any inputs
        all_none = all(
            v is None for v in [
                drift_fusion_index,
                schema_drift,
                temporal_entropy_diff,
                coherence_v3_quality,
                ucf_score,
            ]
        )

        if all_none:
            return None

        # Apply neutral defaults for missing inputs
        dfi = drift_fusion_index if drift_fusion_index is not None else 0.0
        sd = schema_drift if schema_drift is not None else 0.0
        ted = temporal_entropy_diff if temporal_entropy_diff is not None else 0.0
        cq = coherence_v3_quality if coherence_v3_quality is not None else 1.0
        ucf = ucf_score if ucf_score is not None else 1.0

        # Compute base drift score
        predicted_drift_score = compute_base_drift_score(
            drift_fusion_index=dfi,
            schema_drift=sd,
            temporal_entropy_diff=ted,
            coherence_v3_quality=cq,
            ucf_score=ucf,
        )

        # Determine risk band
        drift_risk_band = risk_band_from_score(predicted_drift_score)

        # Analyze trend direction
        trend_direction = analyze_trend_from_histories(
            drift_fusion_index_history=drift_fusion_index_history,
            schema_drift_history=schema_drift_history,
            temporal_entropy_diff_history=temporal_entropy_diff_history,
            coherence_v3_quality_history=coherence_v3_quality_history,
            ucf_score_history=ucf_score_history,
            identity_harmonics_history=identity_harmonics_history,
            window_size=self._history_window,
        )

        # Compute confidence from historical variance
        confidence = compute_confidence(
            [s for s in (predicted_drift_score_history or []) if s is not None]
        )

        # Compute signal variance
        signal_variance = compute_signal_variance(
            drift_fusion_index=dfi,
            schema_drift=sd,
            temporal_entropy_diff=ted,
            coherence_v3_quality=cq,
            ucf_score=ucf,
        )

        # Compute contributing factors
        contributing_factors = compute_contributing_factors(
            drift_fusion_index=drift_fusion_index,
            schema_drift=schema_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            coherence_v3_quality=coherence_v3_quality,
            ucf_score=ucf_score,
            identity_harmonics_score=identity_harmonics_score,
            signal_variance=signal_variance,
        )

        # Count history snapshots
        history_count = max(
            len(drift_fusion_index_history or []),
            len(schema_drift_history or []),
            len(temporal_entropy_diff_history or []),
        )

        # Build debug info
        debug = {
            "inputs_used": {
                "drift_fusion_index": dfi,
                "schema_drift": sd,
                "temporal_entropy_diff": ted,
                "coherence_v3_quality": cq,
                "ucf_score": ucf,
            },
            "signal_variance": signal_variance,
            "history_window": self._history_window,
            "mode": "compute_from_values",
        }

        # Create and return report
        return create_report(
            predicted_drift_score=predicted_drift_score,
            drift_risk_band=drift_risk_band,
            trend_direction=trend_direction,
            contributing_factors=contributing_factors,
            confidence=confidence,
            drift_fusion_index=drift_fusion_index,
            schema_drift=schema_drift,
            temporal_entropy_diff=temporal_entropy_diff,
            coherence_v3_quality=coherence_v3_quality,
            ucf_score=ucf_score,
            identity_harmonics_score=identity_harmonics_score,
            history_snapshot_count=history_count,
            debug=debug,
        )

    # ========================================================================
    # SIGNAL EXTRACTION METHODS
    # ========================================================================

    def _extract_drift_fusion_index(self, ctx: Any) -> Optional[float]:
        """Extract drift fusion index from context."""
        # Try ctx.p19 first
        if hasattr(ctx, "p19") and ctx.p19 is not None:
            return getattr(ctx.p19, "drift_fusion_index", None)
        # Fall back to coherence_state
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "drift_fusion_index", None)
        return None

    def _extract_schema_drift(self, ctx: Any) -> Optional[float]:
        """Extract schema drift from context."""
        # Try ctx.p33 first
        if hasattr(ctx, "p33") and ctx.p33 is not None:
            # P33 has per-schema drift scores; get average or dominant
            drift_scores = getattr(ctx.p33, "schema_drift_scores", {})
            if drift_scores:
                # Return average drift across all schemas
                return sum(drift_scores.values()) / len(drift_scores)
        # Fall back to coherence_state
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "persona_schema_drift", None)
        return None

    def _extract_temporal_entropy_diff(self, ctx: Any) -> Optional[float]:
        """Extract temporal entropy diff from context."""
        # Try ctx.p18 first
        if hasattr(ctx, "p18") and ctx.p18 is not None:
            delta = getattr(ctx.p18, "delta_entropy", None)
            if delta is not None:
                # Normalize to [0, 1] (delta is in [-1, 1])
                return (delta + 1.0) / 2.0
        # Fall back to coherence_state
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "temporal_entropy_diff", None)
        return None

    def _extract_coherence_v3_quality(self, ctx: Any) -> Optional[float]:
        """Extract coherence v3 quality from context."""
        # Try coherence_state first (most reliable source)
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "coherence_v3_quality", None)
        return None

    def _extract_ucf_score(self, ctx: Any) -> Optional[float]:
        """Extract UCF score from context."""
        # Try ctx.p26 first
        if hasattr(ctx, "p26") and ctx.p26 is not None:
            return getattr(ctx.p26, "ucf_score", None)
        # Fall back to coherence_state
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "current_coi", None)
        return None

    def _extract_identity_harmonics_score(self, ctx: Any) -> Optional[float]:
        """Extract identity harmonics score from context (P34)."""
        # Try coherence_state
        if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
            return getattr(ctx.coherence_state, "current_identity_harmonics_index", None)
        return None

    def _extract_histories(self, ctx: Any) -> dict:
        """
        Extract historical signal values from context.

        Returns a dictionary of history lists.
        """
        histories = {
            "drift_fusion_index": [],
            "schema_drift": [],
            "temporal_entropy_diff": [],
            "coherence_v3_quality": [],
            "ucf_score": [],
            "identity_harmonics": [],
            "predicted_drift_score": [],
        }

        if not hasattr(ctx, "coherence_state") or ctx.coherence_state is None:
            return histories

        cs = ctx.coherence_state

        # Extract histories from coherence_state
        histories["drift_fusion_index"] = list(
            getattr(cs, "drift_fusion_index_history", []) or []
        )
        histories["schema_drift"] = list(
            getattr(cs, "persona_schema_drift_history", []) or []
        )
        histories["temporal_entropy_diff"] = list(
            getattr(cs, "temporal_entropy_diff_history", []) or []
        )

        # Note: These may need to be computed from other histories if not directly available
        # For now, we'll leave them empty if not available
        histories["identity_harmonics"] = list(
            getattr(cs, "identity_stability_history", []) or []
        )

        # Get predicted drift score history from P35's own history
        histories["predicted_drift_score"] = list(
            getattr(cs, "drift_magnitude_history", []) or []
        )

        return histories


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p35_resolver: Optional[P35PredictivePersonaDrift] = None


def get_p35_resolver() -> P35PredictivePersonaDrift:
    """
    Get the singleton P35PredictivePersonaDrift instance.

    Returns:
        The shared P35PredictivePersonaDrift instance
    """
    global _p35_resolver
    if _p35_resolver is None:
        _p35_resolver = P35PredictivePersonaDrift()
    return _p35_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p35(ctx: Any) -> Optional[PredictivePersonaDriftReport]:
    """
    Run P35 predictive persona drift if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P35 should run
    2. Runs the predictive drift computation
    3. Attaches the report to ctx.p35
    4. Updates coherence_state if available

    P35 is designed to run after P19, P33, and P34, as it uses their signals.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The PredictivePersonaDriftReport if run, None if skipped
    """
    # Check if P35 is disabled on this context
    if is_p35_disabled(ctx):
        return None

    # P35 can run with minimal inputs (will use neutral defaults)
    # Only skip if ctx has no relevant attributes at all
    has_any_input = (
        hasattr(ctx, "coherence_state") or
        hasattr(ctx, "p18") or
        hasattr(ctx, "p19") or
        hasattr(ctx, "p33")
    )

    if not has_any_input:
        # Context has none of the expected attributes, skip P35
        return None

    # Run the resolver
    resolver = get_p35_resolver()
    report = resolver.compute(ctx)

    # If all inputs were None, report is None
    if report is None:
        return None

    # Attach to context
    if hasattr(ctx, "p35"):
        ctx.p35 = report
    else:
        # Context doesn't have p35 attribute, try to set it anyway
        try:
            setattr(ctx, "p35", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass

    # Update coherence_state if available
    _update_coherence_state(ctx, report)

    return report


def run_p35_directly(
    drift_fusion_index: Optional[float] = None,
    schema_drift: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    coherence_v3_quality: Optional[float] = None,
    ucf_score: Optional[float] = None,
    identity_harmonics_score: Optional[float] = None,
    drift_fusion_index_history: Optional[List[Optional[float]]] = None,
    schema_drift_history: Optional[List[Optional[float]]] = None,
    temporal_entropy_diff_history: Optional[List[Optional[float]]] = None,
    coherence_v3_quality_history: Optional[List[Optional[float]]] = None,
    ucf_score_history: Optional[List[Optional[float]]] = None,
    identity_harmonics_history: Optional[List[Optional[float]]] = None,
    predicted_drift_score_history: Optional[List[Optional[float]]] = None,
) -> Optional[PredictivePersonaDriftReport]:
    """
    Run P35 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the predictive drift with mock values.

    Args:
        drift_fusion_index: P19 drift fusion index [0, 1]
        schema_drift: P33 schema drift [0, 1]
        temporal_entropy_diff: P18 temporal entropy diff [0, 1]
        coherence_v3_quality: P12 coherence v3 quality [0, 1]
        ucf_score: P26 UCF score [0, 1]
        identity_harmonics_score: P34 identity harmonics [0, 1]
        drift_fusion_index_history: History of drift fusion index
        schema_drift_history: History of schema drift
        temporal_entropy_diff_history: History of temporal entropy diff
        coherence_v3_quality_history: History of coherence v3 quality
        ucf_score_history: History of UCF score
        identity_harmonics_history: History of identity harmonics
        predicted_drift_score_history: History of predicted drift scores

    Returns:
        PredictivePersonaDriftReport with computed metrics, or None if all inputs None
    """
    resolver = get_p35_resolver()
    return resolver.compute_from_values(
        drift_fusion_index=drift_fusion_index,
        schema_drift=schema_drift,
        temporal_entropy_diff=temporal_entropy_diff,
        coherence_v3_quality=coherence_v3_quality,
        ucf_score=ucf_score,
        identity_harmonics_score=identity_harmonics_score,
        drift_fusion_index_history=drift_fusion_index_history,
        schema_drift_history=schema_drift_history,
        temporal_entropy_diff_history=temporal_entropy_diff_history,
        coherence_v3_quality_history=coherence_v3_quality_history,
        ucf_score_history=ucf_score_history,
        identity_harmonics_history=identity_harmonics_history,
        predicted_drift_score_history=predicted_drift_score_history,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p35_disabled(ctx: Any) -> bool:
    """
    Check if P35 is disabled on this context.

    P35 can be disabled by setting ctx._p35_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P35 is disabled, False otherwise
    """
    return getattr(ctx, "_p35_disabled", False)


def has_p35_report(ctx: Any) -> bool:
    """
    Check if context has a P35 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p35 is set and not None
    """
    return getattr(ctx, "p35", None) is not None


def get_p35_report(ctx: Any) -> Optional[PredictivePersonaDriftReport]:
    """
    Get the P35 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The PredictivePersonaDriftReport if present, None otherwise
    """
    return getattr(ctx, "p35", None)


def get_predicted_drift_score(ctx: Any) -> float:
    """
    Get the predicted drift score from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Predicted drift score in [0.0, 1.0], or 0.0 if no report
    """
    report = get_p35_report(ctx)
    if report is None:
        return 0.0
    return report.predicted_drift_score


def get_drift_risk_band(ctx: Any) -> str:
    """
    Get the drift risk band from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Risk band string ("low", "moderate", "high"), or "low" if no report
    """
    report = get_p35_report(ctx)
    if report is None:
        return "low"
    return report.drift_risk_band


def get_trend_direction(ctx: Any) -> str:
    """
    Get the trend direction from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Trend direction ("stable", "worsening", "improving"), or "stable" if no report
    """
    report = get_p35_report(ctx)
    if report is None:
        return "stable"
    return report.trend_direction


def get_contributing_factors(ctx: Any) -> List[str]:
    """
    Get the contributing factors from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        List of contributing factor strings, or empty list if no report
    """
    report = get_p35_report(ctx)
    if report is None:
        return []
    return list(report.contributing_factors)


def get_confidence(ctx: Any) -> float:
    """
    Get the confidence from context.

    Convenience function for downstream access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence in [0.0, 1.0], or 0.5 if no report
    """
    report = get_p35_report(ctx)
    if report is None:
        return 0.5
    return report.confidence


def is_low_risk(ctx: Any) -> bool:
    """
    Check if predicted drift risk is low.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "low", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return True  # Default to safe assumption
    return report.is_low_risk()


def is_moderate_risk(ctx: Any) -> bool:
    """
    Check if predicted drift risk is moderate.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "moderate", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return False
    return report.is_moderate_risk()


def is_high_risk(ctx: Any) -> bool:
    """
    Check if predicted drift risk is high.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if risk band is "high", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return False
    return report.is_high_risk()


def is_stable(ctx: Any) -> bool:
    """
    Check if trend direction is stable.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "stable", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return True  # Default to stable
    return report.is_stable()


def is_worsening(ctx: Any) -> bool:
    """
    Check if trend direction is worsening.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "worsening", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return False
    return report.is_worsening()


def is_improving(ctx: Any) -> bool:
    """
    Check if trend direction is improving.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if trend is "improving", False otherwise
    """
    report = get_p35_report(ctx)
    if report is None:
        return False
    return report.is_improving()


def get_p35_version() -> str:
    """
    Get the current P35 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P35_VERSION


def _update_coherence_state(ctx: Any, report: PredictivePersonaDriftReport) -> None:
    """
    Update coherence_state with P35 metrics.

    This stores the current predictive drift values in the coherence state
    for observability and history tracking.

    NOTE: This only updates observation fields. P35 is observation-only
    and does NOT modify any scoring or behavior fields.

    Args:
        ctx: PipelineContext with coherence_state
        report: The P35 report to store
    """
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is None:
        return

    # Update current values (observation only)
    if hasattr(coherence_state, "predictive_drift_snapshot"):
        coherence_state.predictive_drift_snapshot = report

    if hasattr(coherence_state, "current_drift_magnitude_prediction"):
        coherence_state.current_drift_magnitude_prediction = report.predicted_drift_score

    if hasattr(coherence_state, "current_drift_stability_score"):
        coherence_state.current_drift_stability_score = report.confidence

    if hasattr(coherence_state, "current_drift_likelihood_band"):
        coherence_state.current_drift_likelihood_band = report.drift_risk_band.upper()

    if hasattr(coherence_state, "current_drift_direction_scores"):
        # Store trend as a simple dict
        coherence_state.current_drift_direction_scores = {
            "trend_direction": report.trend_direction,
        }

    # Update histories
    if hasattr(coherence_state, "predictive_drift_history"):
        coherence_state.predictive_drift_history.append(report)

    if hasattr(coherence_state, "drift_magnitude_history"):
        coherence_state.drift_magnitude_history.append(report.predicted_drift_score)

    if hasattr(coherence_state, "drift_stability_history"):
        coherence_state.drift_stability_history.append(report.confidence)

    if hasattr(coherence_state, "drift_likelihood_band_history"):
        coherence_state.drift_likelihood_band_history.append(report.drift_risk_band.upper())


# Public exports
__all__ = [
    # Singleton
    "get_p35_resolver",
    # Integration
    "maybe_run_p35",
    "run_p35_directly",
    # Helpers
    "is_p35_disabled",
    "has_p35_report",
    "get_p35_report",
    "get_predicted_drift_score",
    "get_drift_risk_band",
    "get_trend_direction",
    "get_contributing_factors",
    "get_confidence",
    "is_low_risk",
    "is_moderate_risk",
    "is_high_risk",
    "is_stable",
    "is_worsening",
    "is_improving",
    "get_p35_version",
]

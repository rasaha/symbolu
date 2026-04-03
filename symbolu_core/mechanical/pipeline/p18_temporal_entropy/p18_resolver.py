"""
P18 - Temporal Entropy Differential Resolver

Main resolver class that computes entropy metrics and produces
the P18TemporalEntropyReport. This is the entry point for P18 analysis.

Design Principles:
- Observation-Only: Never modifies upstream context
- Deterministic: Same inputs always produce same outputs
- Fixed Formula: Weighted blend of instability sources

Entropy Formula:
    entropy_now = w1 * (1 - coherence_score) +
                  w2 * (1 - coherence_quality) +
                  w3 * (1 - integrity_score) +
                  w4 * tension_index +
                  w5 * volatility_penalty

All weights are constants (not configurable).
Missing inputs use neutral defaults with evidence_missing_penalty.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_schema import (
    EntropyTrend,
    P18TemporalEntropyReport,
    VolatilityBand,
    P18_VERSION,
    create_report,
)


# ============================================================================
# ENTROPY FORMULA WEIGHTS - Fixed constants for deterministic computation
# ============================================================================

# Weights for entropy formula (must sum to <= 1.0 for normalized output)
W_COHERENCE = 0.30        # Weight for (1 - coherence_score)
W_QUALITY = 0.20          # Weight for (1 - coherence_quality)
W_INTEGRITY = 0.25        # Weight for (1 - integrity_score)
W_TENSION = 0.15          # Weight for tension_index
W_VOLATILITY = 0.10       # Weight for historical volatility penalty

# Penalty for missing inputs
EVIDENCE_MISSING_PENALTY = 0.05

# Trend threshold (epsilon)
TREND_EPSILON = 0.05

# Volatility thresholds
VOLATILITY_LOW_THRESHOLD = 0.10
VOLATILITY_HIGH_THRESHOLD = 0.30

# Window size for volatility computation
DEFAULT_WINDOW_SIZE = 5


# ============================================================================
# RESOLVER CLASS
# ============================================================================


class P18TemporalEntropyDifferential:
    """
    P18 Temporal Entropy Differential - Observation-only governance phase.

    Computes entropy metrics from upstream signals and produces a
    P18TemporalEntropyReport. The resolver never modifies upstream state.

    Usage:
        resolver = P18TemporalEntropyDifferential()
        report = resolver.compute(ctx)

    The report contains:
        - entropy_now: Current entropy level [0, 1]
        - entropy_prev: Previous entropy [0, 1] if available
        - delta_entropy: Change [-1, 1] if available
        - trend: INCREASING / DECREASING / STABLE / INSUFFICIENT_HISTORY
        - volatility_band: LOW / MED / HIGH / UNKNOWN
        - debug: Trace information
    """

    def __init__(self) -> None:
        """Initialize the P18 Temporal Entropy Differential resolver."""
        self._version = P18_VERSION

    @property
    def version(self) -> str:
        """Get the resolver version."""
        return self._version

    def compute(self, ctx: Any) -> P18TemporalEntropyReport:
        """
        Compute temporal entropy differential from pipeline context.

        This is the main entry point for P18 analysis. It:
        1. Extracts upstream signals from context
        2. Computes entropy_now using weighted formula
        3. Retrieves entropy_prev from history if available
        4. Computes delta and trend
        5. Computes volatility band from historical deltas
        6. Produces the P18TemporalEntropyReport

        Args:
            ctx: PipelineContext or compatible object

        Returns:
            P18TemporalEntropyReport with computed metrics
        """
        # Track debug information
        debug: Dict[str, Any] = {
            "version": self._version,
            "weights": {
                "coherence": W_COHERENCE,
                "quality": W_QUALITY,
                "integrity": W_INTEGRITY,
                "tension": W_TENSION,
                "volatility": W_VOLATILITY,
            },
            "missing_inputs": [],
        }

        # 1. Extract upstream signals
        coherence_score = self._extract_coherence_score(ctx)
        coherence_quality = self._extract_coherence_quality(ctx)
        integrity_score = self._extract_integrity_score(ctx)
        tension_index = self._extract_tension_index(ctx)

        # 2. Track missing inputs
        missing_count = 0
        if coherence_score is None:
            debug["missing_inputs"].append("coherence_score")
            coherence_score = 0.5  # Neutral default
            missing_count += 1
        if coherence_quality is None:
            debug["missing_inputs"].append("coherence_quality")
            coherence_quality = 0.5  # Neutral default
            missing_count += 1
        if integrity_score is None:
            debug["missing_inputs"].append("integrity_score")
            integrity_score = 0.5  # Neutral default
            missing_count += 1
        if tension_index is None:
            debug["missing_inputs"].append("tension_index")
            tension_index = 0.5  # Neutral default
            missing_count += 1

        debug["missing_count"] = missing_count

        # 3. Get historical volatility from recent deltas
        delta_history = self._extract_delta_history(ctx)
        historical_volatility = self._compute_historical_volatility(delta_history)
        debug["historical_volatility"] = historical_volatility
        debug["delta_history_size"] = len(delta_history)

        # 4. Compute entropy_now using weighted formula
        entropy_now = self._compute_entropy(
            coherence_score=coherence_score,
            coherence_quality=coherence_quality,
            integrity_score=integrity_score,
            tension_index=tension_index,
            historical_volatility=historical_volatility,
            missing_count=missing_count,
        )

        # Clamp to [0, 1]
        entropy_now = max(0.0, min(1.0, entropy_now))
        debug["entropy_now_raw"] = entropy_now

        # 5. Get entropy_prev from history
        entropy_prev = self._extract_entropy_prev(ctx)
        debug["entropy_prev"] = entropy_prev

        # 6. Compute delta and trend
        delta_entropy: Optional[float] = None
        trend: EntropyTrend

        if entropy_prev is None:
            trend = EntropyTrend.INSUFFICIENT_HISTORY
            delta_entropy = None
        else:
            delta_entropy = entropy_now - entropy_prev
            trend = self._classify_trend(delta_entropy)

        debug["delta_entropy"] = delta_entropy
        debug["trend"] = trend.value

        # 7. Compute volatility band
        # Combine historical deltas with current delta if available
        all_deltas = list(delta_history)
        if delta_entropy is not None:
            all_deltas.append(delta_entropy)

        volatility_band, window_size_used = self._classify_volatility(all_deltas)
        debug["volatility_band"] = volatility_band.value
        debug["window_size_used"] = window_size_used

        # 8. Create and return report
        return create_report(
            entropy_now=entropy_now,
            entropy_prev=entropy_prev,
            delta_entropy=delta_entropy,
            trend=trend,
            volatility_band=volatility_band,
            window_size_used=window_size_used,
            debug=debug,
        )

    def _extract_coherence_score(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence score from context.

        Checks multiple sources in order of preference:
        1. ctx.coherence_state.coherence_score_v3
        2. ctx.coherence_state.coherence_score_v2
        3. ctx.coherence_state.coherence_score

        Args:
            ctx: Pipeline context

        Returns:
            Coherence score in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        # Try v3 first (most advanced)
        v3 = getattr(coherence_state, "coherence_score_v3", None)
        if v3 is not None and isinstance(v3, (int, float)):
            return float(v3)

        # Try v2
        v2 = getattr(coherence_state, "coherence_score_v2", None)
        if v2 is not None and isinstance(v2, (int, float)):
            return float(v2)

        # Fall back to v1
        v1 = getattr(coherence_state, "coherence_score", None)
        if v1 is not None and isinstance(v1, (int, float)):
            return float(v1)

        return None

    def _extract_coherence_quality(self, ctx: Any) -> Optional[float]:
        """
        Extract coherence quality metric from context.

        Checks:
        1. ctx.coherence_state.coherence_v3_quality (P12)
        2. ctx.coherence_state.coherence_fused (P16)

        Args:
            ctx: Pipeline context

        Returns:
            Coherence quality in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        # Try v3 quality first
        quality = getattr(coherence_state, "coherence_v3_quality", None)
        if quality is not None and isinstance(quality, (int, float)):
            return float(quality)

        # Try coherence_fused from P16
        fused = getattr(coherence_state, "coherence_fused", None)
        if fused is not None and isinstance(fused, (int, float)):
            return float(fused)

        return None

    def _extract_integrity_score(self, ctx: Any) -> Optional[float]:
        """
        Extract integrity score from P17 report.

        Checks:
        1. ctx.p17.integrity_score
        2. ctx.coherence_state.semantic_integrity_score

        Args:
            ctx: Pipeline context

        Returns:
            Integrity score in [0, 1], or None if not available
        """
        # Try P17 report first
        p17 = getattr(ctx, "p17", None)
        if p17 is not None:
            score = getattr(p17, "integrity_score", None)
            if score is not None and isinstance(score, (int, float)):
                return float(score)

        # Try coherence_state tracking
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            score = getattr(coherence_state, "semantic_integrity_score", None)
            if score is not None and isinstance(score, (int, float)):
                return float(score)

        return None

    def _extract_tension_index(self, ctx: Any) -> Optional[float]:
        """
        Extract tension index from context.

        Checks:
        1. ctx.coherence_state.tension_index
        2. ctx.tension_corridor

        Args:
            ctx: Pipeline context

        Returns:
            Tension index in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is not None:
            tension = getattr(coherence_state, "tension_index", None)
            if tension is not None and isinstance(tension, (int, float)):
                return float(tension)

        # Try tension_corridor from pipeline context
        tension = getattr(ctx, "tension_corridor", None)
        if tension is not None and isinstance(tension, (int, float)):
            return float(tension)

        return None

    def _extract_delta_history(self, ctx: Any) -> List[float]:
        """
        Extract historical entropy deltas from context.

        Checks:
        1. ctx.coherence_state.temporal_entropy_diff_history

        Args:
            ctx: Pipeline context

        Returns:
            List of historical deltas (most recent last)
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return []

        history = getattr(coherence_state, "temporal_entropy_diff_history", None)
        if history is None:
            return []

        # Filter to valid floats only
        valid_deltas = []
        for delta in history:
            if delta is not None and isinstance(delta, (int, float)):
                valid_deltas.append(float(delta))

        # Return last N entries (sliding window)
        return valid_deltas[-DEFAULT_WINDOW_SIZE:]

    def _extract_entropy_prev(self, ctx: Any) -> Optional[float]:
        """
        Extract previous entropy value from context.

        Checks:
        1. ctx.coherence_state.temporal_entropy_diff (previous normalized entropy)
        2. Reconstructs from history if delta history exists

        Args:
            ctx: Pipeline context

        Returns:
            Previous entropy in [0, 1], or None if not available
        """
        coherence_state = getattr(ctx, "coherence_state", None)
        if coherence_state is None:
            return None

        # Try direct previous entropy snapshot
        snapshot = getattr(coherence_state, "temporal_entropy_snapshot", None)
        if snapshot is not None:
            prev = getattr(snapshot, "entropy_now", None)
            if prev is not None and isinstance(prev, (int, float)):
                return float(prev)

        # Try temporal_entropy_diff as previous value
        prev = getattr(coherence_state, "temporal_entropy_diff", None)
        if prev is not None and isinstance(prev, (int, float)):
            return float(prev)

        return None

    def _compute_historical_volatility(self, delta_history: List[float]) -> float:
        """
        Compute volatility from historical deltas.

        Uses standard deviation of absolute deltas as volatility measure.

        Args:
            delta_history: List of historical deltas

        Returns:
            Volatility measure in [0, 1], or 0.5 if insufficient data
        """
        if len(delta_history) < 2:
            return 0.5  # Neutral default

        # Compute mean of absolute deltas
        abs_deltas = [abs(d) for d in delta_history]
        mean_abs = sum(abs_deltas) / len(abs_deltas)

        # Clamp to [0, 1]
        return max(0.0, min(1.0, mean_abs))

    def _compute_entropy(
        self,
        coherence_score: float,
        coherence_quality: float,
        integrity_score: float,
        tension_index: float,
        historical_volatility: float,
        missing_count: int,
    ) -> float:
        """
        Compute entropy using weighted formula.

        Formula:
            entropy = w1 * (1 - coherence_score) +
                      w2 * (1 - coherence_quality) +
                      w3 * (1 - integrity_score) +
                      w4 * tension_index +
                      w5 * historical_volatility +
                      missing_count * evidence_missing_penalty

        Args:
            coherence_score: Coherence score [0, 1]
            coherence_quality: Coherence quality [0, 1]
            integrity_score: Integrity score [0, 1]
            tension_index: Tension index [0, 1]
            historical_volatility: Historical volatility [0, 1]
            missing_count: Number of missing inputs

        Returns:
            Entropy value in [0, 1]
        """
        entropy = (
            W_COHERENCE * (1.0 - coherence_score) +
            W_QUALITY * (1.0 - coherence_quality) +
            W_INTEGRITY * (1.0 - integrity_score) +
            W_TENSION * tension_index +
            W_VOLATILITY * historical_volatility +
            missing_count * EVIDENCE_MISSING_PENALTY
        )

        # Clamp to [0, 1]
        return max(0.0, min(1.0, entropy))

    def _classify_trend(self, delta: float) -> EntropyTrend:
        """
        Classify trend based on delta value.

        Args:
            delta: Change in entropy

        Returns:
            EntropyTrend classification
        """
        if delta > TREND_EPSILON:
            return EntropyTrend.INCREASING
        elif delta < -TREND_EPSILON:
            return EntropyTrend.DECREASING
        else:
            return EntropyTrend.STABLE

    def _classify_volatility(
        self,
        deltas: List[float],
    ) -> tuple[VolatilityBand, int]:
        """
        Classify volatility band based on recent deltas.

        Args:
            deltas: List of recent deltas

        Returns:
            Tuple of (VolatilityBand, window_size_used)
        """
        if len(deltas) == 0:
            return VolatilityBand.UNKNOWN, 0

        # Use sliding window
        window = deltas[-DEFAULT_WINDOW_SIZE:]
        window_size = len(window)

        if window_size < 2:
            # Single delta: classify based on its magnitude
            if window_size == 1:
                abs_delta = abs(window[0])
                if abs_delta <= VOLATILITY_LOW_THRESHOLD:
                    return VolatilityBand.LOW, window_size
                elif abs_delta >= VOLATILITY_HIGH_THRESHOLD:
                    return VolatilityBand.HIGH, window_size
                else:
                    return VolatilityBand.MED, window_size
            return VolatilityBand.UNKNOWN, 0

        # Compute standard deviation of deltas
        mean = sum(window) / window_size
        variance = sum((d - mean) ** 2 for d in window) / window_size
        std_dev = variance ** 0.5

        # Also consider mean absolute delta
        mean_abs = sum(abs(d) for d in window) / window_size

        # Combined volatility metric
        volatility = (std_dev + mean_abs) / 2.0

        if volatility <= VOLATILITY_LOW_THRESHOLD:
            return VolatilityBand.LOW, window_size
        elif volatility >= VOLATILITY_HIGH_THRESHOLD:
            return VolatilityBand.HIGH, window_size
        else:
            return VolatilityBand.MED, window_size


# Public exports
__all__ = [
    "P18TemporalEntropyDifferential",
    "W_COHERENCE",
    "W_QUALITY",
    "W_INTEGRITY",
    "W_TENSION",
    "W_VOLATILITY",
    "EVIDENCE_MISSING_PENALTY",
    "TREND_EPSILON",
    "VOLATILITY_LOW_THRESHOLD",
    "VOLATILITY_HIGH_THRESHOLD",
    "DEFAULT_WINDOW_SIZE",
]

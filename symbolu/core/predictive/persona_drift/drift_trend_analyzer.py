"""
P35 - Drift Trend Analyzer

Rule-based trend detection using historical signal snapshots.
This module analyzes the direction of drift over time.

TREND DIRECTION RULES (LOCKED):
    - "worsening" if >= 2 signals increased > +0.05
    - "improving" if >= 2 signals decreased > -0.05
    - Else "stable"

No regression, no extrapolation beyond linear deltas.

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs -> same outputs
    - No LLM, no ML, no learning
    - Simple rule-based logic only
    - No probabilistic sampling

INVARIANTS:
    - INV-P35-4: Deterministic math only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from symbolu.core.predictive.persona_drift.drift_report import (
    TREND_CHANGE_THRESHOLD,
    TREND_MIN_SIGNALS,
)


@dataclass(frozen=True)
class SignalSnapshot:
    """
    Immutable snapshot of input signals at a point in time.

    Stores all input signals that can be used for trend analysis.
    """
    drift_fusion_index: Optional[float] = None
    schema_drift: Optional[float] = None
    temporal_entropy_diff: Optional[float] = None
    coherence_v3_quality: Optional[float] = None
    ucf_score: Optional[float] = None
    identity_harmonics_score: Optional[float] = None
    # P38: Optional cross-domain pattern instability signal.
    # Additive-only -- existing code that does not provide this field
    # continues to work identically (defaults to None, excluded from deltas).
    pattern_instability: Optional[float] = None

    def to_tuple(self) -> Tuple[Optional[float], ...]:
        """Convert to tuple for comparison."""
        return (
            self.drift_fusion_index,
            self.schema_drift,
            self.temporal_entropy_diff,
            self.coherence_v3_quality,
            self.ucf_score,
            self.identity_harmonics_score,
            self.pattern_instability,
        )


def compute_signal_deltas(
    current: SignalSnapshot,
    previous: SignalSnapshot,
) -> List[float]:
    """
    Compute deltas between current and previous signal snapshots.

    For quality signals (coherence_v3_quality, ucf_score, identity_harmonics_score),
    the delta is inverted so that a decrease in quality appears as an increase in drift.

    Args:
        current: Current signal snapshot
        previous: Previous signal snapshot

    Returns:
        List of delta values for signals that are present in both snapshots
    """
    deltas: List[float] = []

    # Drift signals (increase = worsening)
    if current.drift_fusion_index is not None and previous.drift_fusion_index is not None:
        deltas.append(current.drift_fusion_index - previous.drift_fusion_index)

    if current.schema_drift is not None and previous.schema_drift is not None:
        deltas.append(current.schema_drift - previous.schema_drift)

    if current.temporal_entropy_diff is not None and previous.temporal_entropy_diff is not None:
        deltas.append(current.temporal_entropy_diff - previous.temporal_entropy_diff)

    # Quality signals (inverted: decrease in quality = increase in drift)
    if current.coherence_v3_quality is not None and previous.coherence_v3_quality is not None:
        # Inverted: decrease in quality = positive delta (worsening)
        deltas.append(previous.coherence_v3_quality - current.coherence_v3_quality)

    if current.ucf_score is not None and previous.ucf_score is not None:
        # Inverted: decrease in UCF = positive delta (worsening)
        deltas.append(previous.ucf_score - current.ucf_score)

    if current.identity_harmonics_score is not None and previous.identity_harmonics_score is not None:
        # Inverted: decrease in harmonics = positive delta (worsening)
        deltas.append(previous.identity_harmonics_score - current.identity_harmonics_score)

    # P38: Pattern instability (increase = worsening, same direction as drift signals)
    if current.pattern_instability is not None and previous.pattern_instability is not None:
        deltas.append(current.pattern_instability - previous.pattern_instability)

    return deltas


def classify_trend_direction(
    snapshots: List[SignalSnapshot],
    threshold: float = TREND_CHANGE_THRESHOLD,
    min_signals: int = TREND_MIN_SIGNALS,
) -> str:
    """
    Classify trend direction based on historical snapshots.

    RULES (LOCKED):
        - "worsening" if >= min_signals signals increased > threshold
        - "improving" if >= min_signals signals decreased > threshold
        - Else "stable"

    Uses linear deltas between consecutive snapshots.
    No regression or extrapolation.

    Args:
        snapshots: List of historical signal snapshots (oldest first)
        threshold: Change threshold to count as significant (default 0.05)
        min_signals: Minimum signals showing change for trend detection (default 2)

    Returns:
        Trend direction: "stable", "worsening", or "improving"
    """
    if len(snapshots) < 2:
        return "stable"

    # Compute average deltas across all consecutive pairs
    all_deltas: List[List[float]] = []
    for i in range(1, len(snapshots)):
        deltas = compute_signal_deltas(snapshots[i], snapshots[i - 1])
        if deltas:
            all_deltas.append(deltas)

    if not all_deltas:
        return "stable"

    # Average the deltas per signal position
    # First, find max number of signals
    max_signals = max(len(d) for d in all_deltas)
    if max_signals == 0:
        return "stable"

    # Sum deltas per position
    sum_deltas = [0.0] * max_signals
    count_deltas = [0] * max_signals

    for deltas in all_deltas:
        for i, delta in enumerate(deltas):
            sum_deltas[i] += delta
            count_deltas[i] += 1

    # Compute averages
    avg_deltas = [
        sum_deltas[i] / count_deltas[i] if count_deltas[i] > 0 else 0.0
        for i in range(max_signals)
    ]

    # Count significant increases and decreases
    increasing_count = sum(1 for d in avg_deltas if d > threshold)
    decreasing_count = sum(1 for d in avg_deltas if d < -threshold)

    # Apply classification rules
    if increasing_count >= min_signals:
        return "worsening"
    elif decreasing_count >= min_signals:
        return "improving"
    else:
        return "stable"


def analyze_trend_from_histories(
    drift_fusion_index_history: Optional[List[Optional[float]]] = None,
    schema_drift_history: Optional[List[Optional[float]]] = None,
    temporal_entropy_diff_history: Optional[List[Optional[float]]] = None,
    coherence_v3_quality_history: Optional[List[Optional[float]]] = None,
    ucf_score_history: Optional[List[Optional[float]]] = None,
    identity_harmonics_history: Optional[List[Optional[float]]] = None,
    window_size: int = 3,
) -> str:
    """
    Analyze trend from separate history lists.

    Converts history lists into SignalSnapshots and classifies trend.

    Args:
        drift_fusion_index_history: History of drift fusion index values
        schema_drift_history: History of schema drift values
        temporal_entropy_diff_history: History of temporal entropy diff values
        coherence_v3_quality_history: History of coherence v3 quality values
        ucf_score_history: History of UCF score values
        identity_harmonics_history: History of identity harmonics values
        window_size: Number of recent snapshots to use (default 3)

    Returns:
        Trend direction: "stable", "worsening", or "improving"
    """
    # Convert histories to lists, using empty list if None
    dfi_hist = list(drift_fusion_index_history or [])
    sd_hist = list(schema_drift_history or [])
    ted_hist = list(temporal_entropy_diff_history or [])
    cq_hist = list(coherence_v3_quality_history or [])
    ucf_hist = list(ucf_score_history or [])
    ih_hist = list(identity_harmonics_history or [])

    # Find the maximum length
    max_len = max(
        len(dfi_hist),
        len(sd_hist),
        len(ted_hist),
        len(cq_hist),
        len(ucf_hist),
        len(ih_hist),
    )

    if max_len < 2:
        return "stable"

    # Build snapshots
    snapshots: List[SignalSnapshot] = []

    # Only use the most recent window_size values
    start_idx = max(0, max_len - window_size)

    for i in range(start_idx, max_len):
        snapshot = SignalSnapshot(
            drift_fusion_index=_safe_get(dfi_hist, i),
            schema_drift=_safe_get(sd_hist, i),
            temporal_entropy_diff=_safe_get(ted_hist, i),
            coherence_v3_quality=_safe_get(cq_hist, i),
            ucf_score=_safe_get(ucf_hist, i),
            identity_harmonics_score=_safe_get(ih_hist, i),
        )
        snapshots.append(snapshot)

    return classify_trend_direction(snapshots)


def _safe_get(
    history: List[Optional[float]],
    index: int,
) -> Optional[float]:
    """
    Safely get a value from history list.

    Args:
        history: List of optional values
        index: Index to retrieve

    Returns:
        Value at index if valid, None otherwise
    """
    if not history:
        return None
    if index < 0 or index >= len(history):
        return None
    return history[index]


# Public exports
__all__ = [
    "SignalSnapshot",
    "compute_signal_deltas",
    "classify_trend_direction",
    "analyze_trend_from_histories",
]

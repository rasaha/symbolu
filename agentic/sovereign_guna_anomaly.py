"""
Guna Anomaly Detection — Pure-Python Runtime-Safe Extraction.

Extracted from sovereign/guna.py (GunaMonitor) for governance consumption.
This module has NO torch or numpy dependency — it operates on plain floats.

Anomaly types:
  - Collapse:    One Guna component dominates (> threshold)
  - Oscillation: Rapid change between consecutive readings (> threshold)
  - Stagnation:  No significant change over a window of readings (< threshold)

These are temporal patterns over Guna history, distinct from the instantaneous
Guna values (volatility, stability) already surfaced in S1.

Phase S4: sovereign integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Guna component names (3D collapsed view: Sattva, Rajas, Tamas)
GUNA_NAMES: Tuple[str, ...] = ("sattva", "rajas", "tamas")


@dataclass(frozen=True)
class GunaAnomalySnapshot:
    """Immutable snapshot of Guna anomaly state.

    Designed for bridge transport — no mutable state, no tensor references.
    """
    collapse: bool = False
    oscillation: bool = False
    stagnation: bool = False
    dominant_guna: str = "unknown"
    # Optional statistics (may be empty if history too short)
    sattva_mean: Optional[float] = None
    rajas_mean: Optional[float] = None
    tamas_mean: Optional[float] = None
    sattva_std: Optional[float] = None
    rajas_std: Optional[float] = None
    tamas_std: Optional[float] = None

    @property
    def any_anomaly(self) -> bool:
        """True if any anomaly is active."""
        return self.collapse or self.oscillation or self.stagnation

    @property
    def anomaly_count(self) -> int:
        """Number of active anomalies (0–3)."""
        return sum([self.collapse, self.oscillation, self.stagnation])

    def to_audit_dict(self) -> Dict[str, object]:
        """Serialize for governance audit metadata."""
        d: Dict[str, object] = {
            "collapse": self.collapse,
            "oscillation": self.oscillation,
            "stagnation": self.stagnation,
            "dominant_guna": self.dominant_guna,
            "any_anomaly": self.any_anomaly,
            "anomaly_count": self.anomaly_count,
        }
        if self.sattva_mean is not None:
            d["statistics"] = {
                "sattva_mean": round(self.sattva_mean, 4),
                "rajas_mean": round(self.rajas_mean or 0.0, 4),
                "tamas_mean": round(self.tamas_mean or 0.0, 4),
                "sattva_std": round(self.sattva_std or 0.0, 4),
                "rajas_std": round(self.rajas_std or 0.0, 4),
                "tamas_std": round(self.tamas_std or 0.0, 4),
            }
        return d


def check_guna_anomalies(
    history: List[Tuple[float, float, float]],
    collapse_threshold: float = 0.9,
    oscillation_threshold: float = 0.3,
    stagnation_window: int = 10,
    stagnation_threshold: float = 0.05,
) -> GunaAnomalySnapshot:
    """Check for Guna anomalies over a history window.

    This is a pure-Python reimplementation of GunaMonitor.check_anomalies()
    that operates on plain float tuples instead of numpy arrays.

    Args:
        history: List of (sattva, rajas, tamas) float tuples, oldest first.
        collapse_threshold: A single guna > this → collapse detected.
        oscillation_threshold: Sum of absolute changes > this → oscillation.
        stagnation_window: Number of steps to look back for stagnation.
        stagnation_threshold: Total change below this over window → stagnation.

    Returns:
        GunaAnomalySnapshot with all anomaly flags and optional statistics.
    """
    if len(history) < 2:
        dominant = _dominant_guna(history[-1]) if history else "unknown"
        return GunaAnomalySnapshot(dominant_guna=dominant)

    current = history[-1]
    prev = history[-2]

    # Collapse: one Guna > threshold
    collapse = any(g > collapse_threshold for g in current)

    # Oscillation: large change from previous
    oscillation = (
        sum(abs(c - p) for c, p in zip(current, prev)) > oscillation_threshold
    )

    # Stagnation: no significant change over window
    stagnation = False
    if len(history) >= stagnation_window:
        window = history[-stagnation_window:]
        total_change = 0.0
        for i in range(1, len(window)):
            total_change += sum(abs(window[i][j] - window[i - 1][j]) for j in range(3))
        stagnation = total_change < stagnation_threshold

    # Dominant guna
    dominant = _dominant_guna(current)

    # Statistics (if enough history)
    stats = _compute_statistics(history)

    return GunaAnomalySnapshot(
        collapse=collapse,
        oscillation=oscillation,
        stagnation=stagnation,
        dominant_guna=dominant,
        **stats,
    )


def snapshot_from_monitor_dict(
    anomalies: Dict[str, bool],
    dominant_guna: str = "unknown",
    statistics: Optional[Dict[str, float]] = None,
) -> GunaAnomalySnapshot:
    """Build a GunaAnomalySnapshot from a GunaMonitor output dict.

    This is the bridge-side factory: the sovereign runtime's GunaMonitor
    produces dicts with {collapse, oscillation, stagnation} bools and
    optional statistics. This function normalizes them into a frozen snapshot
    suitable for bridge transport.

    Args:
        anomalies: Dict from GunaMonitor.check_anomalies()
        dominant_guna: String from GunaMonitor.get_dominant_guna()
        statistics: Optional dict from GunaMonitor.get_statistics()
    """
    stats_kwargs: Dict[str, Optional[float]] = {}
    if statistics:
        stats_kwargs = {
            "sattva_mean": statistics.get("sattva_mean"),
            "rajas_mean": statistics.get("rajas_mean"),
            "tamas_mean": statistics.get("tamas_mean"),
            "sattva_std": statistics.get("sattva_std"),
            "rajas_std": statistics.get("rajas_std"),
            "tamas_std": statistics.get("tamas_std"),
        }
    return GunaAnomalySnapshot(
        collapse=anomalies.get("collapse", False),
        oscillation=anomalies.get("oscillation", False),
        stagnation=anomalies.get("stagnation", False),
        dominant_guna=dominant_guna,
        **stats_kwargs,
    )


def _dominant_guna(reading: Tuple[float, float, float]) -> str:
    """Return name of the dominant Guna component."""
    max_idx = 0
    max_val = reading[0]
    for i in range(1, 3):
        if reading[i] > max_val:
            max_val = reading[i]
            max_idx = i
    return GUNA_NAMES[max_idx]


def _compute_statistics(
    history: List[Tuple[float, float, float]],
) -> Dict[str, Optional[float]]:
    """Compute mean/std statistics over Guna history (pure Python)."""
    if len(history) < 2:
        return {
            "sattva_mean": None, "rajas_mean": None, "tamas_mean": None,
            "sattva_std": None, "rajas_std": None, "tamas_std": None,
        }
    n = len(history)
    sums = [0.0, 0.0, 0.0]
    for reading in history:
        for i in range(3):
            sums[i] += reading[i]
    means = [s / n for s in sums]

    sq_diffs = [0.0, 0.0, 0.0]
    for reading in history:
        for i in range(3):
            sq_diffs[i] += (reading[i] - means[i]) ** 2
    stds = [(s / n) ** 0.5 for s in sq_diffs]

    return {
        "sattva_mean": means[0],
        "rajas_mean": means[1],
        "tamas_mean": means[2],
        "sattva_std": stds[0],
        "rajas_std": stds[1],
        "tamas_std": stds[2],
    }

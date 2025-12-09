"""
Temporal Bhava Tracker - Consciousness State Evolution Tracking
================================================================

This module provides deterministic, pure-Python tracking of consciousness
state evolution over time using a sliding window approach.

Key Features:
- Sliding window for temporal analysis
- Linear regression-based trend detection
- Tension corridor tracking
- Recovery pattern detection
- State classification (TENSE, RECOVERING, STABLE, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import math


@dataclass
class TemporalEntry:
    """A single temporal entry representing an analysis result at a point in time."""

    text: str
    smi: float
    bhava_id: int
    bhava_direction: str  # "upward" | "downward" | "neutral"
    kosha_id: int
    ontology_id: int
    timestamp: Optional[float] = None


class TemporalBhavaTracker:
    """
    Tracks consciousness state evolution over time using a sliding window.

    This tracker maintains a history of analysis entries and computes
    various temporal metrics including trends, tension corridors, and
    recovery patterns.

    Attributes:
        window_size: Maximum number of entries to keep in the sliding window.
    """

    # Thresholds for state classification
    HIGH_SMI_THRESHOLD = 0.6  # SMI above this is considered "tense"
    LOW_SMI_THRESHOLD = 0.35  # SMI below this is considered "calm"
    SLOPE_EPSILON = 0.02  # Slope threshold for trend detection

    def __init__(self, window_size: int = 10):
        """
        Initialize the temporal tracker.

        Args:
            window_size: Maximum number of entries to maintain in the sliding window.
        """
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        self._window_size = window_size
        self._entries: List[TemporalEntry] = []

    @property
    def window_size(self) -> int:
        """Return the configured window size."""
        return self._window_size

    @property
    def entries(self) -> List[TemporalEntry]:
        """Return a copy of current entries."""
        return list(self._entries)

    def add_analysis(
        self,
        text: str,
        smi: float,
        bhava_id: int,
        bhava_direction: str,
        kosha_id: int,
        ontology_id: int,
        timestamp: Optional[float] = None,
    ) -> None:
        """
        Append a new TemporalEntry, respecting the sliding window.

        Args:
            text: The analyzed text.
            smi: Semantic Mismatch Index value (0.0 to 1.0).
            bhava_id: Bhava state identifier.
            bhava_direction: Direction of bhava ("upward", "downward", "neutral").
            kosha_id: Kosha layer identifier.
            ontology_id: Ontology state identifier.
            timestamp: Optional timestamp for the entry.
        """
        entry = TemporalEntry(
            text=text,
            smi=smi,
            bhava_id=bhava_id,
            bhava_direction=bhava_direction,
            kosha_id=kosha_id,
            ontology_id=ontology_id,
            timestamp=timestamp,
        )
        self._entries.append(entry)

        # Enforce sliding window
        if len(self._entries) > self._window_size:
            self._entries = self._entries[-self._window_size:]

    def get_pattern_summary(self) -> Dict[str, Any]:
        """
        Return a comprehensive summary of temporal patterns.

        Returns:
            A dictionary containing:
            - state: Overall state classification (TENSE, RECOVERING, STABLE, etc.)
            - trajectory: Trend analysis with slope and confidence
            - momentum: Momentum indicators
            - tension: Tension corridor analysis
            - recovery: Recovery pattern analysis
            - stats: Basic statistical measures
        """
        if not self._entries:
            return {
                "state": "UNKNOWN",
                "trajectory": {
                    "trend": "stable",
                    "confidence": 0.0,
                    "slope": 0.0,
                },
                "momentum": {
                    "direction": "neutral",
                    "strength": 0.0,
                },
                "tension": {
                    "current": False,
                    "corridor_length": 0,
                    "max_corridor_length": 0,
                },
                "recovery": {
                    "active": False,
                    "progress": 0.0,
                },
                "stats": {
                    "avg_smi": 0.0,
                    "std_smi": 0.0,
                    "current_smi": 0.0,
                    "count": 0,
                },
            }

        # Compute basic stats
        stats = self._compute_stats()

        # Compute trajectory
        trajectory = self._compute_trajectory()

        # Compute tension analysis
        tension = self._compute_tension()

        # Compute recovery analysis
        recovery = self._compute_recovery()

        # Compute momentum
        momentum = self._compute_momentum(trajectory)

        # Classify overall state
        state = self._classify_state(stats, trajectory, tension, recovery)

        return {
            "state": state,
            "trajectory": trajectory,
            "momentum": momentum,
            "tension": tension,
            "recovery": recovery,
            "stats": stats,
        }

    def reset(self) -> None:
        """Clear the history."""
        self._entries.clear()

    def _compute_stats(self) -> Dict[str, Any]:
        """Compute basic statistical measures."""
        smis = [e.smi for e in self._entries]
        count = len(smis)

        avg_smi = sum(smis) / count

        # Compute standard deviation
        variance = sum((s - avg_smi) ** 2 for s in smis) / count
        std_smi = math.sqrt(variance)

        return {
            "avg_smi": round(avg_smi, 4),
            "std_smi": round(std_smi, 4),
            "current_smi": round(smis[-1], 4),
            "count": count,
        }

    def _compute_trajectory(self) -> Dict[str, Any]:
        """
        Compute trajectory using linear regression on SMI values.

        Uses simple linear regression: slope = Cov(x,y) / Var(x)
        where x is the index and y is the SMI value.
        """
        n = len(self._entries)

        if n < 2:
            return {
                "trend": "stable",
                "confidence": 0.0,
                "slope": 0.0,
            }

        # Simple linear regression
        smis = [e.smi for e in self._entries]
        indices = list(range(n))

        mean_x = sum(indices) / n
        mean_y = sum(smis) / n

        # Compute covariance and variance
        cov_xy = sum((indices[i] - mean_x) * (smis[i] - mean_y) for i in range(n)) / n
        var_x = sum((x - mean_x) ** 2 for x in indices) / n

        if var_x == 0:
            slope = 0.0
        else:
            slope = cov_xy / var_x

        # Determine trend based on slope
        if slope > self.SLOPE_EPSILON:
            trend = "rising"
        elif slope < -self.SLOPE_EPSILON:
            trend = "falling"
        else:
            trend = "stable"

        # Compute confidence based on:
        # 1. Absolute slope magnitude (stronger trend = higher confidence)
        # 2. Number of entries (more data = higher confidence)
        # 3. Consistency (lower variance = higher confidence)

        slope_confidence = min(abs(slope) / 0.1, 1.0)  # Scale slope to [0, 1]
        count_confidence = min(n / self._window_size, 1.0)  # Scale count to [0, 1]

        # Compute R-squared for consistency
        ss_tot = sum((y - mean_y) ** 2 for y in smis)
        if ss_tot > 0:
            predicted = [mean_y + slope * (i - mean_x) for i in indices]
            ss_res = sum((smis[i] - predicted[i]) ** 2 for i in range(n))
            r_squared = max(0, 1 - ss_res / ss_tot)
        else:
            r_squared = 1.0  # All values are the same

        # Combined confidence
        confidence = (slope_confidence * 0.4 + count_confidence * 0.3 + r_squared * 0.3)

        return {
            "trend": trend,
            "confidence": round(confidence, 4),
            "slope": round(slope, 4),
        }

    def _compute_tension(self) -> Dict[str, Any]:
        """Compute tension corridor analysis."""
        current_tension = False
        corridor_length = 0
        max_corridor_length = 0
        current_streak = 0

        for entry in self._entries:
            if entry.smi >= self.HIGH_SMI_THRESHOLD:
                current_streak += 1
                max_corridor_length = max(max_corridor_length, current_streak)
            else:
                current_streak = 0

        # Check if currently in tension
        if self._entries and self._entries[-1].smi >= self.HIGH_SMI_THRESHOLD:
            current_tension = True
            corridor_length = current_streak

        return {
            "current": current_tension,
            "corridor_length": corridor_length,
            "max_corridor_length": max_corridor_length,
        }

    def _compute_recovery(self) -> Dict[str, Any]:
        """
        Compute recovery pattern analysis.

        Recovery is detected when SMI drops from previously high levels.
        """
        if len(self._entries) < 2:
            return {
                "active": False,
                "progress": 0.0,
            }

        # Find the peak SMI in the window
        smis = [e.smi for e in self._entries]
        peak_smi = max(smis)
        peak_idx = smis.index(peak_smi)
        current_smi = smis[-1]

        # Recovery is active if:
        # 1. We had a high peak (above HIGH_SMI_THRESHOLD)
        # 2. Current SMI is lower than the peak
        # 3. Peak was not at the end (we've moved past it)

        active = (
            peak_smi >= self.HIGH_SMI_THRESHOLD
            and peak_idx < len(smis) - 1
            and current_smi < peak_smi
        )

        if active:
            # Progress is how far we've dropped from peak towards LOW_SMI_THRESHOLD
            drop = peak_smi - current_smi
            target_drop = peak_smi - self.LOW_SMI_THRESHOLD
            progress = min(drop / target_drop, 1.0) if target_drop > 0 else 1.0
        else:
            progress = 0.0

        return {
            "active": active,
            "progress": round(progress, 4),
        }

    def _compute_momentum(self, trajectory: Dict[str, Any]) -> Dict[str, Any]:
        """Compute momentum based on trajectory and recent changes."""
        if len(self._entries) < 2:
            return {
                "direction": "neutral",
                "strength": 0.0,
            }

        # Compute momentum from recent SMI changes
        recent_smis = [e.smi for e in self._entries[-3:]]

        if len(recent_smis) >= 2:
            recent_change = recent_smis[-1] - recent_smis[0]
            strength = min(abs(recent_change) / 0.3, 1.0)  # Scale to [0, 1]

            if recent_change > 0.05:
                direction = "upward"
            elif recent_change < -0.05:
                direction = "downward"
            else:
                direction = "neutral"
        else:
            direction = "neutral"
            strength = 0.0

        return {
            "direction": direction,
            "strength": round(strength, 4),
        }

    def _classify_state(
        self,
        stats: Dict[str, Any],
        trajectory: Dict[str, Any],
        tension: Dict[str, Any],
        recovery: Dict[str, Any],
    ) -> str:
        """
        Classify overall state based on all temporal indicators.

        States:
        - TENSE: High SMI with tension corridor active
        - RECOVERING: Actively recovering from high tension
        - STABLE: Consistent low/medium SMI
        - RISING: SMI trending upward
        - FALLING: SMI trending downward
        - VOLATILE: High variance, no clear pattern
        """
        current_smi = stats["current_smi"]
        avg_smi = stats["avg_smi"]
        std_smi = stats["std_smi"]
        trend = trajectory["trend"]

        # Check for tension state first (highest priority)
        if tension["current"] and tension["corridor_length"] >= 2:
            return "TENSE"

        # Check for active recovery
        if recovery["active"] and recovery["progress"] > 0.2:
            return "RECOVERING"

        # Check for volatility
        if std_smi > 0.15:
            return "VOLATILE"

        # Check for trend-based states
        if trend == "rising" and trajectory["confidence"] > 0.3:
            return "RISING"

        if trend == "falling" and trajectory["confidence"] > 0.3:
            return "FALLING"

        # Default to stable
        return "STABLE"

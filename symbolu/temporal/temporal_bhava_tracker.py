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

from symbolu.formulas.resonance_formulas import (
    compute_smi as _compute_smi_formula,
    compute_delta_smi as _compute_delta_smi_formula,
    compute_bhava_gap as _compute_bhava_gap_formula,
    compute_tension_corridor as _compute_tension_corridor_formula,
)
from symbolu.formulas.enhanced_smi import compute_enhanced_smi as _compute_enhanced_smi_formula


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


@dataclass
class TemporalFormulaSnapshot:
    """
    Per-turn snapshot of Phase 1 temporal formula values.

    This dataclass holds the computed values from the four foundational
    temporal formulas introduced in Symbol-U v3.0 Phase 1, plus the
    Phase 13 enhanced SMI (patent-level coefficients).

    Attributes:
        smi: Symbolic Mental Index (0.0 to 1.0)
        delta_smi: SMI momentum (-1.0 to 1.0)
        bhava_gap: Bhava circular distance (0.0 to 1.0)
        tension_corridor: Tension dynamics signal (0.0 to 1.0)
        enhanced_smi: Enhanced SMI with patent-level coefficients (0.0 to 1.0)
    """

    smi: Optional[float] = None
    delta_smi: Optional[float] = None
    bhava_gap: Optional[float] = None
    tension_corridor: Optional[float] = None
    enhanced_smi: Optional[float] = None

    def to_dict(self) -> Dict[str, Optional[float]]:
        """Convert snapshot to JSON-safe dictionary."""
        return {
            "smi": self.smi,
            "delta_smi": self.delta_smi,
            "bhava_gap": self.bhava_gap,
            "tension_corridor": self.tension_corridor,
            "enhanced_smi": self.enhanced_smi,
        }


@dataclass
class TemporalState:
    """
    Computed temporal state including Phase 1 resonance formulas.

    This dataclass wraps TemporalFormulaSnapshot for backward compatibility
    and future extensibility.

    Attributes:
        formulas: Snapshot of current formula values
    """

    formulas: TemporalFormulaSnapshot = field(default_factory=TemporalFormulaSnapshot)

    # Backward compatibility properties
    @property
    def smi(self) -> Optional[float]:
        """Get SMI from formulas snapshot."""
        return self.formulas.smi

    @property
    def delta_smi(self) -> Optional[float]:
        """Get delta_smi from formulas snapshot."""
        return self.formulas.delta_smi

    @property
    def bhava_gap(self) -> Optional[float]:
        """Get bhava_gap from formulas snapshot."""
        return self.formulas.bhava_gap

    @property
    def tension_corridor(self) -> Optional[float]:
        """Get tension_corridor from formulas snapshot."""
        return self.formulas.tension_corridor

    @property
    def enhanced_smi(self) -> Optional[float]:
        """Get enhanced_smi from formulas snapshot."""
        return self.formulas.enhanced_smi


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
        self._temporal_state: TemporalState = TemporalState()
        self._previous_smi: Optional[float] = None
        self._previous_bhava: Optional[int] = None

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

    def get_pattern_summary(self, include_formulas: bool = True) -> Dict[str, Any]:
        """
        Return a comprehensive summary of temporal patterns.

        Args:
            include_formulas: Whether to include Phase 1 formula snapshot (default: True)

        Returns:
            A dictionary containing:
            - state: Overall state classification (TENSE, RECOVERING, STABLE, etc.)
            - trajectory: Trend analysis with slope and confidence
            - momentum: Momentum indicators
            - tension: Tension corridor analysis
            - recovery: Recovery pattern analysis
            - stats: Basic statistical measures
            - formulas: Phase 1 formula snapshot (optional)
        """
        if not self._entries:
            base_summary = {
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
            if include_formulas:
                base_summary["formulas"] = self._temporal_state.formulas.to_dict()
            return base_summary

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

        summary = {
            "state": state,
            "trajectory": trajectory,
            "momentum": momentum,
            "tension": tension,
            "recovery": recovery,
            "stats": stats,
        }

        # Optionally include Phase 1 formulas
        if include_formulas:
            summary["formulas"] = self._temporal_state.formulas.to_dict()

        return summary

    def reset(self) -> None:
        """Clear the history."""
        self._entries.clear()
        self._temporal_state = TemporalState()
        self._previous_smi = None
        self._previous_bhava = None

    def get_temporal_state(self) -> TemporalState:
        """
        Get the current temporal state with computed formulas.

        Returns:
            TemporalState with computed SMI, delta_smi, bhava_gap, tension_corridor
        """
        return self._temporal_state

    def compute_formulas(
        self,
        dimensional_resonance: float,
        vrtti_intensity: float,
        bhava_position: float,
        current_bhava: int,
    ) -> TemporalState:
        """
        Compute all Phase 1 temporal formulas with fail-safe wrappers.

        This method computes:
        - SMI from dimensional_resonance, vrtti_intensity, bhava_position
        - ΔSMI from current and previous SMI
        - Bhava Gap from current and previous bhava
        - Tension Corridor from ΔSMI and bhava_gap
        - Enhanced SMI (Phase 13) from available inputs

        All computations are wrapped in try/except blocks for fail-safety.

        Args:
            dimensional_resonance: Dimensional resonance value (0.0 to 1.0)
            vrtti_intensity: Vrtti intensity value (0.0 to 1.0)
            bhava_position: Bhava position value (0.0 to 1.0)
            current_bhava: Current bhava ID (0 to 11)

        Returns:
            TemporalState with computed values (fields set to None on error)
        """
        snapshot = TemporalFormulaSnapshot()

        # Compute SMI with fail-safe wrapper
        try:
            snapshot.smi = _compute_smi_formula(
                dimensional_resonance=dimensional_resonance,
                vrtti_intensity=vrtti_intensity,
                bhava_position=bhava_position,
            )
        except Exception as e:
            # Log error and set to None (fail-safe)
            snapshot.smi = None
            # Silent fail - maintain backward compatibility

        # Compute ΔSMI with fail-safe wrapper
        try:
            if snapshot.smi is not None:
                snapshot.delta_smi = _compute_delta_smi_formula(
                    smi=snapshot.smi,
                    previous_smi=self._previous_smi,
                )
            else:
                snapshot.delta_smi = None
        except Exception as e:
            # Log error and set to None (fail-safe)
            snapshot.delta_smi = None

        # Compute Bhava Gap with fail-safe wrapper
        try:
            snapshot.bhava_gap = _compute_bhava_gap_formula(
                current_bhava=current_bhava,
                previous_bhava=self._previous_bhava,
            )
        except Exception as e:
            # Log error and set to None (fail-safe)
            snapshot.bhava_gap = None

        # Compute Tension Corridor with fail-safe wrapper
        try:
            if snapshot.delta_smi is not None and snapshot.bhava_gap is not None:
                snapshot.tension_corridor = _compute_tension_corridor_formula(
                    delta_smi=snapshot.delta_smi,
                    bhava_gap=snapshot.bhava_gap,
                )
            else:
                snapshot.tension_corridor = None
        except Exception as e:
            # Log error and set to None (fail-safe)
            snapshot.tension_corridor = None

        # Compute Enhanced SMI (Phase 13) with fail-safe wrapper
        # NOTE: This is observation-only and does NOT affect pipeline behavior
        try:
            snapshot.enhanced_smi = self._compute_enhanced_smi(
                dimensional_resonance=dimensional_resonance,
                vrtti_intensity=vrtti_intensity,
                bhava_position=bhava_position,
                bhava_gap=snapshot.bhava_gap,
                delta_smi=snapshot.delta_smi,
                tension_corridor=snapshot.tension_corridor,
            )
        except Exception as e:
            # Log error and set to None (fail-safe)
            snapshot.enhanced_smi = None

        # Create state with snapshot
        state = TemporalState(formulas=snapshot)

        # Update internal state for next turn
        if snapshot.smi is not None:
            self._previous_smi = snapshot.smi
        self._previous_bhava = current_bhava
        self._temporal_state = state

        return state

    def _compute_enhanced_smi(
        self,
        dimensional_resonance: float,
        vrtti_intensity: float,
        bhava_position: float,
        bhava_gap: Optional[float],
        delta_smi: Optional[float],
        tension_corridor: Optional[float],
    ) -> Optional[float]:
        """
        Compute Phase 13 enhanced SMI from available inputs.

        This method derives the six enhanced SMI components from available
        Phase 1 formula outputs and computes the patent-accurate enhanced SMI.

        Component Derivation:
        - dim_resonance: Use dimensional_resonance directly
        - vrtti_balance: Invert vrtti_intensity (high intensity → low balance)
        - bhava_alignment: Use bhava_position directly
        - semantic_weighting: Derive from bhava_gap (close gap → high weighting)
        - temporal_decay: Derive from tension_corridor (low tension → low decay)
        - noise_suppression: Derive from delta_smi stability (low delta → high suppression)

        Args:
            dimensional_resonance: Dimensional resonance [0.0, 1.0]
            vrtti_intensity: Vrtti intensity [0.0, 1.0]
            bhava_position: Bhava position [0.0, 1.0]
            bhava_gap: Bhava gap [0.0, 1.0] (optional)
            delta_smi: Delta SMI [-1.0, 1.0] (optional)
            tension_corridor: Tension corridor [0.0, 1.0] (optional)

        Returns:
            Enhanced SMI [0.0, 1.0], or None if required inputs are missing

        Note:
            This is OBSERVATION-ONLY. Enhanced SMI does NOT affect pipeline behavior.
        """
        # Derive component 1: dim_resonance (use directly)
        dim_resonance = dimensional_resonance

        # Derive component 2: vrtti_balance (invert vrtti_intensity)
        # High vrtti intensity → low balance
        vrtti_balance = 1.0 - vrtti_intensity

        # Derive component 3: bhava_alignment (use bhava_position directly)
        bhava_alignment = bhava_position

        # Derive component 4: semantic_weighting (from bhava_gap)
        # Close bhava gap → high semantic weighting
        if bhava_gap is not None:
            semantic_weighting = 1.0 - bhava_gap
        else:
            # Default to neutral if bhava_gap is unavailable
            semantic_weighting = 0.5

        # Derive component 5: temporal_decay (from tension_corridor)
        # Low tension → low decay (stable state)
        if tension_corridor is not None:
            temporal_decay = tension_corridor
        else:
            # Default to neutral if tension_corridor is unavailable
            temporal_decay = 0.5

        # Derive component 6: noise_suppression (from delta_smi)
        # Low delta_smi → high suppression (stable signal)
        if delta_smi is not None:
            noise_suppression = 1.0 - min(abs(delta_smi), 1.0)
        else:
            # Default to neutral if delta_smi is unavailable
            noise_suppression = 0.5

        # Compute enhanced SMI with patent-level coefficients
        try:
            enhanced_smi = _compute_enhanced_smi_formula(
                dim_resonance=dim_resonance,
                vrtti_balance=vrtti_balance,
                bhava_alignment=bhava_alignment,
                semantic_weighting=semantic_weighting,
                temporal_decay=temporal_decay,
                noise_suppression=noise_suppression,
            )
            return enhanced_smi
        except Exception:
            # Graceful degradation: return None on error
            return None

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

    def detect_activation_window(self, window: int = 5) -> bool:
        """
        Detect if temporal patterns warrant LAM activation.

        This method is used by TTOR router to determine if temporal patterns
        should trigger Long-Arc Mapper (LAM) activation.

        Activation Conditions (any of):
        1. Bhava momentum is accelerating upward OR downward (strength > 0.3)
        2. Trajectory slope magnitude > threshold (0.15)
        3. Tension corridor detected in recent entries (corridor_length >= 2)

        Args:
            window: Number of recent entries to analyze (default: 5)

        Returns:
            True if temporal patterns indicate LAM should be activated
        """
        if len(self._entries) < 2:
            # Not enough data to detect patterns
            return False

        # Analyze recent entries only (within window)
        effective_window = min(window, len(self._entries))
        recent_entries = self._entries[-effective_window:]

        # Build temporary summary for analysis
        summary = self.get_pattern_summary()

        # Condition 1: Bhava momentum is accelerating
        momentum = summary["momentum"]
        momentum_active = (
            momentum["direction"] in ("upward", "downward")
            and momentum["strength"] > 0.3
        )

        # Condition 2: Trajectory slope magnitude > threshold (0.15)
        trajectory = summary["trajectory"]
        trajectory_active = abs(trajectory["slope"]) > 0.15

        # Condition 3: Tension corridor detected in recent entries
        tension = summary["tension"]
        tension_corridor_active = tension["corridor_length"] >= 2

        # Return True if ANY condition is met
        return momentum_active or trajectory_active or tension_corridor_active

    def get_lam_activation_signals(self, window: int = 5) -> Dict[str, Any]:
        """
        Get detailed LAM activation signals for debugging/introspection.

        Returns a dictionary with all signals used to determine LAM activation.

        Args:
            window: Number of recent entries to analyze

        Returns:
            Dictionary with activation signals and decision
        """
        if len(self._entries) < 2:
            return {
                "temporal_patterns_detected": False,
                "momentum_active": False,
                "trajectory_active": False,
                "tension_corridor_active": False,
                "momentum_direction": "neutral",
                "momentum_strength": 0.0,
                "trajectory_slope": 0.0,
                "tension_corridor_length": 0,
                "entry_count": len(self._entries),
                "window_size": window,
            }

        summary = self.get_pattern_summary()

        momentum = summary["momentum"]
        momentum_active = (
            momentum["direction"] in ("upward", "downward")
            and momentum["strength"] > 0.3
        )

        trajectory = summary["trajectory"]
        trajectory_active = abs(trajectory["slope"]) > 0.15

        tension = summary["tension"]
        tension_corridor_active = tension["corridor_length"] >= 2

        return {
            "temporal_patterns_detected": momentum_active or trajectory_active or tension_corridor_active,
            "momentum_active": momentum_active,
            "trajectory_active": trajectory_active,
            "tension_corridor_active": tension_corridor_active,
            "momentum_direction": momentum["direction"],
            "momentum_strength": momentum["strength"],
            "trajectory_slope": trajectory["slope"],
            "tension_corridor_length": tension["corridor_length"],
            "entry_count": len(self._entries),
            "window_size": window,
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

"""
P38 - Cross-Domain Pattern Tracker
====================================

Stateful temporal tracker for CDI patterns. Wraps ``CrossDomainIntelligence``
with a sliding window to provide:

- Pattern lifecycle events (onset / sustain / exit / recurrence)
- Boundary proximity and trajectory ETA
- Pattern persistence and volatility metrics
- Pattern sequence matching (full + partial for anticipation)
- Pattern instability signal for P35 integration
- Aspect vector derivation and temporal tracking

INVARIANTS:
    - INV-P38-1: Deterministic (same inputs -> same outputs)
    - INV-P38-2: Observer-only (never influences decisions)
    - INV-P38-3: No LLM, no ML, no learning
    - INV-P38-4: Sliding window bounded (max ``window_size`` snapshots)

Version: 1.0.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from symbolu.temporal.cross_domain_intelligence import (
    CrossDomainIntelligence,
    PatternConfig,
)
from symbolu.temporal.pattern_sequence_rules import (
    PATTERN_SEQUENCES,
    PatternSequenceRule,
)
from symbolu.temporal.pattern_aspect_derivation import derive_aspect_vector


P38_VERSION = "1.0.0"

# Total number of CDI patterns (used for volatility normalisation)
_TOTAL_PATTERNS = 13

# Weights for pattern instability signal (locked)
W_VOLATILITY = 0.40
W_PERSISTENCE_INV = 0.30
W_ESCALATION = 0.20
W_RECURRENCE = 0.10

# Context-adjusted threshold bounds (locked)
THRESHOLD_FLOOR = 0.50
THRESHOLD_MAX_ADJUSTMENT = 0.10

# Minimum steps for a partial sequence match to count
MIN_PARTIAL_STEPS = 2


# =============================================================================
# Data Classes
# =============================================================================


@dataclass(frozen=True)
class PatternSnapshot:
    """Immutable record of CDI pattern state at one turn."""

    turn_index: int
    active_patterns: FrozenSet[str]
    pattern_confidences: Dict[str, float]
    dominant_pattern: Optional[str]
    dominant_confidence: float
    smi: float
    bhava_id: int
    bhava_direction: str
    kosha_id: int
    ontology_id: int
    aspect_vector: Dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PatternEvent:
    """An event in a pattern's lifecycle."""

    pattern_name: str
    event_type: str  # "onset" | "sustain" | "exit" | "recurrence"
    turn_index: int
    confidence: float
    dwell_turns: int
    gap_turns: int


@dataclass(frozen=True)
class BoundaryProximity:
    """How close a signal is to entering a pattern's region."""

    pattern_name: str
    distance_to_entry: float
    distance_to_center: float
    direction: str  # "approaching" | "receding" | "stable"
    estimated_turns_to_entry: Optional[int]


@dataclass(frozen=True)
class SequenceMatch:
    """Result of matching a pattern sequence rule against the window."""

    rule: PatternSequenceRule
    steps_completed: int
    total_steps: int
    avg_confidence: float
    is_complete: bool
    next_expected_pattern: Optional[str]


@dataclass(frozen=True)
class PatternTrackerReport:
    """Complete P38 report for one turn.

    INV-P38-2: This report is observer-only -- it MUST NOT be used
    to gate, block, or modify system behaviour.
    """

    turn_index: int
    snapshot: PatternSnapshot
    events: List[PatternEvent]
    proximities: List[BoundaryProximity]
    sequence_matches: List[SequenceMatch]
    pattern_volatility: float
    dominant_persistence: float
    pattern_stability_band: str  # "stable" | "soft" | "fragile"
    pattern_instability_signal: float


# =============================================================================
# Tracker Implementation
# =============================================================================


class CrossDomainPatternTracker:
    """
    Stateful temporal tracker for CDI patterns.

    Maintains a bounded sliding window of ``PatternSnapshot`` objects and
    computes lifecycle events, boundary trajectories, persistence / volatility
    metrics, and sequence matches each turn.

    Args:
        window_size: Maximum snapshots retained. Default 10.
    """

    def __init__(self, window_size: int = 10):
        if window_size < 1:
            raise ValueError("window_size must be at least 1")
        self._cdi = CrossDomainIntelligence()
        self._window: List[PatternSnapshot] = []
        self._window_size = window_size
        # Internal turn counter (monotonically increasing)
        self._turn_counter = 0
        # Accumulate lifecycle events for recurrence rate computation
        self._recent_events: List[PatternEvent] = []

    # ------------------------------------------------------------------
    # Public Properties
    # ------------------------------------------------------------------

    @property
    def window_size(self) -> int:
        return self._window_size

    @property
    def window(self) -> List[PatternSnapshot]:
        """Return a copy of the current window."""
        return list(self._window)

    @property
    def turn_counter(self) -> int:
        return self._turn_counter

    # ------------------------------------------------------------------
    # Core: process_turn
    # ------------------------------------------------------------------

    def process_turn(
        self,
        smi: float,
        bhava_id: int,
        bhava_direction: str,
        kosha_id: int,
        ontology_id: int,
        temporal_trend: Optional[str] = None,
    ) -> PatternTrackerReport:
        """
        Process a single turn and return a full P38 report.

        This is the main entry point. It:
        1. Runs CDI classification.
        2. Builds a ``PatternSnapshot``.
        3. Detects lifecycle events (onset/sustain/exit/recurrence).
        4. Computes boundary proximities and trajectory ETAs.
        5. Matches pattern sequences (full + partial).
        6. Computes persistence, volatility, stability band.
        7. Computes pattern instability signal.

        Args:
            smi: Semantic Mismatch Index [0.0, 1.0].
            bhava_id: Bhava state identifier.
            bhava_direction: "upward" | "downward" | "neutral".
            kosha_id: Kosha layer identifier.
            ontology_id: Ontology state identifier.
            temporal_trend: Optional temporal trend for CDI.

        Returns:
            ``PatternTrackerReport`` with all computed signals.
        """
        turn_idx = self._turn_counter
        self._turn_counter += 1

        # 1. CDI classification
        raw_patterns = self._cdi.detect_pattern(
            smi=smi,
            bhava_id=bhava_id,
            bhava_direction=bhava_direction,
            kosha_id=kosha_id,
            ontology_id=ontology_id,
            temporal_trend=temporal_trend,
        )

        # 2. Build snapshot
        active = frozenset(name for name, _ in raw_patterns)
        confidences = {name: conf for name, conf in raw_patterns}
        dominant = raw_patterns[0][0] if raw_patterns else None
        dominant_conf = raw_patterns[0][1] if raw_patterns else 0.0
        aspect_vec = derive_aspect_vector(
            smi=smi,
            bhava_id=bhava_id,
            bhava_direction=bhava_direction,
            kosha_id=kosha_id,
            ontology_id=ontology_id,
        )

        snapshot = PatternSnapshot(
            turn_index=turn_idx,
            active_patterns=active,
            pattern_confidences=confidences,
            dominant_pattern=dominant,
            dominant_confidence=dominant_conf,
            smi=smi,
            bhava_id=bhava_id,
            bhava_direction=bhava_direction,
            kosha_id=kosha_id,
            ontology_id=ontology_id,
            aspect_vector=aspect_vec,
        )

        # 3. Lifecycle events
        events = self._detect_lifecycle_events(snapshot)

        # 4. Boundary proximities
        proximities = self._compute_all_proximities(smi)

        # 5. Sequence matching
        # We need to temporarily include current snapshot in the window for matching
        combined_window = self._window + [snapshot]
        seq_matches = self._detect_sequences(combined_window)

        # 6. Persistence / volatility / stability
        volatility = self._compute_pattern_volatility_with(snapshot)
        dom_persistence = self._compute_pattern_persistence(
            dominant, with_snapshot=snapshot
        )
        stability = self._compute_stability_band(dom_persistence, volatility)

        # 7. Instability signal
        escalation_pressure = self._compute_escalation_pressure(seq_matches)
        recurrence_rate = self._compute_recurrence_rate(events)
        instability = self._compute_instability_signal(
            volatility, dom_persistence, escalation_pressure, recurrence_rate
        )

        # Append to window (enforce bound)
        self._window.append(snapshot)
        if len(self._window) > self._window_size:
            self._window = self._window[-self._window_size:]

        # Track events for recurrence calculation
        self._recent_events.extend(events)
        max_events = self._window_size * _TOTAL_PATTERNS
        if len(self._recent_events) > max_events:
            self._recent_events = self._recent_events[-max_events:]

        return PatternTrackerReport(
            turn_index=turn_idx,
            snapshot=snapshot,
            events=events,
            proximities=proximities,
            sequence_matches=seq_matches,
            pattern_volatility=volatility,
            dominant_persistence=dom_persistence,
            pattern_stability_band=stability,
            pattern_instability_signal=instability,
        )

    def reset(self) -> None:
        """Clear internal state."""
        self._window.clear()
        self._recent_events.clear()
        self._turn_counter = 0

    # ------------------------------------------------------------------
    # Capability 1: Lifecycle Events
    # ------------------------------------------------------------------

    def _detect_lifecycle_events(
        self, current: PatternSnapshot
    ) -> List[PatternEvent]:
        events: List[PatternEvent] = []
        prev = self._window[-1] if self._window else None

        for pattern in current.active_patterns:
            if prev is None or pattern not in prev.active_patterns:
                gap = self._turns_since_last_active(pattern)
                if gap is not None and gap > 0:
                    events.append(
                        PatternEvent(
                            pattern_name=pattern,
                            event_type="recurrence",
                            turn_index=current.turn_index,
                            confidence=current.pattern_confidences[pattern],
                            dwell_turns=1,
                            gap_turns=gap,
                        )
                    )
                else:
                    events.append(
                        PatternEvent(
                            pattern_name=pattern,
                            event_type="onset",
                            turn_index=current.turn_index,
                            confidence=current.pattern_confidences[pattern],
                            dwell_turns=1,
                            gap_turns=0,
                        )
                    )
            else:
                dwell = self._consecutive_active_count(pattern)
                events.append(
                    PatternEvent(
                        pattern_name=pattern,
                        event_type="sustain",
                        turn_index=current.turn_index,
                        confidence=current.pattern_confidences[pattern],
                        dwell_turns=dwell + 1,
                        gap_turns=0,
                    )
                )

        # Exit events
        if prev is not None:
            for pattern in prev.active_patterns - current.active_patterns:
                dwell = self._consecutive_active_count(pattern)
                events.append(
                    PatternEvent(
                        pattern_name=pattern,
                        event_type="exit",
                        turn_index=current.turn_index,
                        confidence=0.0,
                        dwell_turns=dwell,
                        gap_turns=0,
                    )
                )

        return events

    def _turns_since_last_active(self, pattern_name: str) -> Optional[int]:
        """Return turns since pattern was last active, or None if never seen."""
        # Skip the last entry (we check from second-to-last backwards)
        for i in range(len(self._window) - 2, -1, -1):
            if pattern_name in self._window[i].active_patterns:
                last_active_turn = self._window[i].turn_index
                current_turn = self._turn_counter  # current (not yet appended)
                return current_turn - last_active_turn - 1
        return None

    def _consecutive_active_count(self, pattern_name: str) -> int:
        """Count consecutive turns the pattern has been active (from window end)."""
        count = 0
        for snap in reversed(self._window):
            if pattern_name in snap.active_patterns:
                count += 1
            else:
                break
        return count

    # ------------------------------------------------------------------
    # Capability 2: Boundary Proximity & Trajectory
    # ------------------------------------------------------------------

    def _compute_all_proximities(self, current_smi: float) -> List[BoundaryProximity]:
        """Compute boundary proximity for all 13 patterns."""
        results: List[BoundaryProximity] = []
        for name, config in self._cdi._patterns.items():
            dist_entry = self._smi_boundary_distance(current_smi, config)
            dist_center = self._smi_center_distance(current_smi, config)
            direction, eta = self._trajectory_direction_and_eta(name, config, dist_entry)
            results.append(
                BoundaryProximity(
                    pattern_name=name,
                    distance_to_entry=round(dist_entry, 4),
                    distance_to_center=round(dist_center, 4),
                    direction=direction,
                    estimated_turns_to_entry=eta,
                )
            )
        return results

    @staticmethod
    def _smi_boundary_distance(smi: float, config: PatternConfig) -> float:
        smi_min, smi_max = config.smi_range
        if smi_min <= smi <= smi_max:
            return 0.0
        return min(abs(smi - smi_min), abs(smi - smi_max))

    @staticmethod
    def _smi_center_distance(smi: float, config: PatternConfig) -> float:
        smi_min, smi_max = config.smi_range
        center = (smi_min + smi_max) / 2.0
        return abs(smi - center)

    def _trajectory_direction_and_eta(
        self,
        pattern_name: str,
        config: PatternConfig,
        current_distance: float,
    ) -> Tuple[str, Optional[int]]:
        """Compute trajectory direction and ETA using linear regression on distances."""
        if len(self._window) < 2:
            return ("stable", None)

        distances = [
            self._smi_boundary_distance(snap.smi, config) for snap in self._window
        ]
        distances.append(current_distance)

        n = len(distances)
        indices = list(range(n))
        mean_x = sum(indices) / n
        mean_y = sum(distances) / n

        cov_xy = sum(
            (indices[i] - mean_x) * (distances[i] - mean_y) for i in range(n)
        ) / n
        var_x = sum((x - mean_x) ** 2 for x in indices) / n

        if var_x == 0:
            return ("stable", None)

        slope = cov_xy / var_x

        if slope < -0.01:
            direction = "approaching"
            if current_distance > 0 and abs(slope) > 0.001:
                eta = max(1, round(current_distance / abs(slope)))
            else:
                eta = None
            return (direction, eta)
        elif slope > 0.01:
            return ("receding", None)
        else:
            return ("stable", None)

    # ------------------------------------------------------------------
    # Capability 3: Persistence / Volatility
    # ------------------------------------------------------------------

    def _compute_pattern_persistence(
        self,
        pattern_name: Optional[str],
        with_snapshot: Optional[PatternSnapshot] = None,
    ) -> float:
        """Persistence of a specific pattern across the window.

        ``1.0 - variance(presence)`` where presence is binary per turn.
        """
        if pattern_name is None:
            return 0.5

        snaps = list(self._window)
        if with_snapshot is not None:
            snaps.append(with_snapshot)

        if len(snaps) < 2:
            return 1.0

        presence = [
            1.0 if pattern_name in s.active_patterns else 0.0 for s in snaps
        ]
        mean = sum(presence) / len(presence)
        variance = sum((v - mean) ** 2 for v in presence) / len(presence)
        return max(0.0, min(1.0, 1.0 - variance))

    def _compute_pattern_volatility_with(
        self, current_snapshot: PatternSnapshot
    ) -> float:
        """Rate of pattern switching across the window."""
        snaps = list(self._window)
        snaps.append(current_snapshot)

        if len(snaps) < 2:
            return 0.0

        diffs: List[float] = []
        for i in range(1, len(snaps)):
            prev_p = snaps[i - 1].active_patterns
            curr_p = snaps[i].active_patterns
            sym_diff = len(prev_p.symmetric_difference(curr_p))
            diffs.append(sym_diff / _TOTAL_PATTERNS)

        return sum(diffs) / len(diffs) if diffs else 0.0

    def _compute_stability_band(
        self, persistence: float, volatility: float
    ) -> str:
        """Classify pattern stability: "stable", "soft", or "fragile"."""
        if persistence < 0.40 or volatility >= 0.45:
            return "fragile"
        if persistence >= 0.75 and volatility < 0.20:
            return "stable"
        return "soft"

    # ------------------------------------------------------------------
    # Capability 4: Sequence Matching
    # ------------------------------------------------------------------

    def _detect_sequences(
        self, window: List[PatternSnapshot]
    ) -> List[SequenceMatch]:
        """Detect full and partial pattern sequences in the window."""
        results: List[SequenceMatch] = []

        for rule in PATTERN_SEQUENCES:
            steps_matched = 0
            total_confidence = 0.0
            last_turn_index = -1

            for step_pattern in rule.steps:
                found = False
                for snap in window:
                    if snap.turn_index <= last_turn_index:
                        continue
                    if (
                        last_turn_index >= 0
                        and (snap.turn_index - last_turn_index) > rule.max_gap_turns + 1
                    ):
                        break
                    if step_pattern in snap.active_patterns:
                        steps_matched += 1
                        total_confidence += snap.pattern_confidences[step_pattern]
                        last_turn_index = snap.turn_index
                        found = True
                        break
                if not found:
                    break

            if steps_matched >= MIN_PARTIAL_STEPS:
                avg_conf = total_confidence / steps_matched
                if avg_conf >= rule.min_confidence:
                    is_complete = steps_matched == len(rule.steps)
                    next_expected = (
                        rule.steps[steps_matched]
                        if steps_matched < len(rule.steps)
                        else None
                    )
                    results.append(
                        SequenceMatch(
                            rule=rule,
                            steps_completed=steps_matched,
                            total_steps=len(rule.steps),
                            avg_confidence=round(avg_conf, 4),
                            is_complete=is_complete,
                            next_expected_pattern=next_expected,
                        )
                    )

        return results

    # ------------------------------------------------------------------
    # Capability 5: Pattern Instability Signal (for P35)
    # ------------------------------------------------------------------

    def _compute_escalation_pressure(
        self, seq_matches: List[SequenceMatch]
    ) -> float:
        """Fraction of detected sequences in 'escalation' category."""
        if not seq_matches:
            return 0.0
        escalation_count = sum(
            1 for m in seq_matches if m.rule.category == "escalation"
        )
        return escalation_count / len(seq_matches)

    def _compute_recurrence_rate(self, events: List[PatternEvent]) -> float:
        """Fraction of current lifecycle events that are 'recurrence'."""
        if not events:
            return 0.0
        recurrence_count = sum(1 for e in events if e.event_type == "recurrence")
        return recurrence_count / len(events)

    def _compute_instability_signal(
        self,
        volatility: float,
        persistence: float,
        escalation_pressure: float,
        recurrence_rate: float,
    ) -> float:
        """Compute scalar instability signal for P35 consumption.

        Formula (locked):
            instability = 0.40 * volatility
                        + 0.30 * (1 - persistence)
                        + 0.20 * escalation_pressure
                        + 0.10 * recurrence_rate
        """
        instability = (
            W_VOLATILITY * volatility
            + W_PERSISTENCE_INV * (1.0 - persistence)
            + W_ESCALATION * escalation_pressure
            + W_RECURRENCE * recurrence_rate
        )
        return max(0.0, min(1.0, round(instability, 4)))

    # ------------------------------------------------------------------
    # Capability 5b: Context-Adjusted Threshold
    # ------------------------------------------------------------------

    @staticmethod
    def get_context_adjusted_threshold(
        base_threshold: float,
        drift_forecast: float,
        continuity_mode: str,
    ) -> float:
        """Adjust a pattern detection threshold based on P35/P37 context.

        When drift is high or continuity is fragmenting, lower the threshold
        to catch patterns earlier. Adjustment is bounded to ±0.10 with a
        hard floor at 0.50.

        Args:
            base_threshold: Original pattern min_confidence.
            drift_forecast: P35 predicted_drift_score [0.0, 1.0].
            continuity_mode: P37 continuity mode string.

        Returns:
            Adjusted threshold in [THRESHOLD_FLOOR, 0.95].
        """
        adjustment = 0.0
        if drift_forecast > 0.65:
            adjustment -= 0.05
        if continuity_mode == "fragmenting":
            adjustment -= 0.05
        adjusted = base_threshold + adjustment
        return max(THRESHOLD_FLOOR, min(0.95, adjusted))


__all__ = [
    "P38_VERSION",
    "PatternSnapshot",
    "PatternEvent",
    "BoundaryProximity",
    "SequenceMatch",
    "PatternTrackerReport",
    "CrossDomainPatternTracker",
]

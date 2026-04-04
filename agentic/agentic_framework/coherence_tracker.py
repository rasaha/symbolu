"""
Coherence Tracking Component — Governance-Native Turn-Level Tracker
===================================================================

Tracks conversation-level coherence metrics externally.
Inspired by Symbolu Coherence Engine (37+ metrics, sliding window).

METRICS TRACKED:
- Internal consistency: How consistent is reasoning?
- Prediction reversal risk: Risk of contradicting self
- Volatility index: How much is state changing?
- Goal alignment: Does response serve the goal?
- Factual alignment: Is it factually grounded?
- Identity stability: Is persona consistent?
- Drift magnitude: How far have we drifted?

INVARIANTS:
- INV-COH-1: Observation-only (never modifies LLM behavior)
- INV-COH-2: Deterministic (same inputs -> same outputs)
- INV-COH-3: Append-only (history never deleted)
- INV-COH-4: Sliding window creates new state

RELATIONSHIP TO CORE PIPELINE CoherenceState
=============================================
This module is the **governance-native** coherence tracker. It computes its
own 7 metrics (internal_consistency, goal_alignment, volatility, etc.) from
generation output at each turn. It runs entirely within the agentic framework,
with no pipeline dependency.

The pipeline has its own richer coherence state:
``agentic.core.coherence.coherence_state.CoherenceState`` (241+ fields),
which is bridged into governance via the dedicated adapter:
``agentic.agentic_framework.signal_adapters.coherence_state_adapter``.

These two systems are **complementary, not duplicates**:

- **This module** (``coherence_tracker``):
    Computes governance-level coherence from generation output.
    Consumed by ``agent.py``, ``safety_contract.py``.
    Owned by the governance layer.

- **Core CoherenceState adapter** (``coherence_state_adapter``):
    Reads pipeline-level coherence/drift/UCF/continuity signals.
    Contributes bounded confidence penalty + escalation bias.
    Provides audit enrichment from pipeline depth.

Neither replaces the other. ``coherence_tracker`` answers "is this
conversation coherent from the governance perspective?" while the core
adapter answers "what does the pipeline's deeper analysis say about
coherence, drift, and stability?"
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CoherenceMetrics:
    """
    Coherence metrics for a single turn.

    All metrics are bounded [0.0, 1.0].
    """

    # Internal consistency: How consistent is reasoning?
    internal_consistency: float

    # Stability metrics
    prediction_reversal_risk: float  # Risk of contradicting self
    volatility_index: float  # How much is state changing?

    # Alignment metrics
    goal_alignment: float  # Does response serve the goal?
    factual_alignment: float  # Is it factually grounded?

    # Identity metrics
    identity_stability: float  # Is persona consistent?

    # Drift metrics
    drift_magnitude: float  # How far have we drifted?
    drift_direction: str  # "stable", "improving", "degrading"

    # Aggregate
    overall_coherence: float  # Weighted combination

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "internal_consistency": self.internal_consistency,
            "prediction_reversal_risk": self.prediction_reversal_risk,
            "volatility_index": self.volatility_index,
            "goal_alignment": self.goal_alignment,
            "factual_alignment": self.factual_alignment,
            "identity_stability": self.identity_stability,
            "drift_magnitude": self.drift_magnitude,
            "drift_direction": self.drift_direction,
            "overall_coherence": self.overall_coherence,
        }


@dataclass
class CoherenceState:
    """
    Full coherence state with history.

    Based on Symbolu CoherenceState pattern:
    - Append-only histories
    - Sliding window trim
    - Deterministic computation
    """

    session_id: str
    current_turn: int

    # Current metrics
    current_metrics: CoherenceMetrics

    # Histories (append-only, window-trimmed)
    internal_consistency_history: List[float] = field(default_factory=list)
    prediction_reversal_risk_history: List[float] = field(default_factory=list)
    volatility_index_history: List[float] = field(default_factory=list)
    goal_alignment_history: List[float] = field(default_factory=list)
    factual_alignment_history: List[float] = field(default_factory=list)
    identity_stability_history: List[float] = field(default_factory=list)
    drift_magnitude_history: List[float] = field(default_factory=list)
    overall_coherence_history: List[float] = field(default_factory=list)

    def window_trim(self, window: int = 10) -> None:
        """Trim all histories to sliding window size."""
        self.internal_consistency_history = self.internal_consistency_history[-window:]
        self.prediction_reversal_risk_history = self.prediction_reversal_risk_history[-window:]
        self.volatility_index_history = self.volatility_index_history[-window:]
        self.goal_alignment_history = self.goal_alignment_history[-window:]
        self.factual_alignment_history = self.factual_alignment_history[-window:]
        self.identity_stability_history = self.identity_stability_history[-window:]
        self.drift_magnitude_history = self.drift_magnitude_history[-window:]
        self.overall_coherence_history = self.overall_coherence_history[-window:]

    def get_average_coherence(self) -> float:
        """Get average overall coherence from history."""
        if not self.overall_coherence_history:
            return 0.0
        return sum(self.overall_coherence_history) / len(self.overall_coherence_history)

    def get_recent_trend(self, window: int = 3) -> str:
        """Get recent coherence trend."""
        if len(self.overall_coherence_history) < window:
            return "stable"

        recent = self.overall_coherence_history[-window:]
        trend = recent[-1] - recent[0]

        if trend > 0.1:
            return "improving"
        elif trend < -0.1:
            return "degrading"
        return "stable"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "session_id": self.session_id,
            "current_turn": self.current_turn,
            "current_metrics": self.current_metrics.to_dict(),
            "average_coherence": self.get_average_coherence(),
            "recent_trend": self.get_recent_trend(),
            "history_length": len(self.overall_coherence_history),
        }


class CoherenceEngine:
    """
    Tracks and computes coherence metrics across turns.

    INVARIANTS (from Symbolu):
    - Observation-only: Never modifies LLM behavior
    - Deterministic: Same inputs -> same outputs
    - Append-only: History never deleted
    """

    def __init__(self, window: int = 10):
        """
        Initialize coherence engine.

        Args:
            window: Sliding window size for history retention
        """
        self.window = window

        # Weights for overall coherence computation
        self.weights = {
            "internal_consistency": 0.20,
            "prediction_reversal_risk": 0.15,  # Inverted (1 - risk)
            "volatility_index": 0.15,  # Inverted (1 - volatility)
            "goal_alignment": 0.20,
            "factual_alignment": 0.15,
            "identity_stability": 0.15,
        }

    def update(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,  # TurnSnapshot
        goal_state: Optional[Any] = None,
    ) -> CoherenceState:
        """
        Update coherence state with new turn.

        Returns new CoherenceState (never modifies prev_state).

        Args:
            prev_state: Previous coherence state (None for first turn)
            turn: Current TurnSnapshot
            goal_state: Optional GoalState for alignment

        Returns:
            New CoherenceState with updated metrics
        """
        session_id = prev_state.session_id if prev_state else str(uuid.uuid4())
        current_turn = (prev_state.current_turn + 1) if prev_state else 1

        # Compute current metrics
        metrics = self._compute_metrics(prev_state, turn, goal_state)

        # Create new state with updated histories
        new_state = CoherenceState(
            session_id=session_id,
            current_turn=current_turn,
            current_metrics=metrics,
        )

        # Copy and extend histories from prev_state
        if prev_state:
            new_state.internal_consistency_history = prev_state.internal_consistency_history.copy()
            new_state.prediction_reversal_risk_history = prev_state.prediction_reversal_risk_history.copy()
            new_state.volatility_index_history = prev_state.volatility_index_history.copy()
            new_state.goal_alignment_history = prev_state.goal_alignment_history.copy()
            new_state.factual_alignment_history = prev_state.factual_alignment_history.copy()
            new_state.identity_stability_history = prev_state.identity_stability_history.copy()
            new_state.drift_magnitude_history = prev_state.drift_magnitude_history.copy()
            new_state.overall_coherence_history = prev_state.overall_coherence_history.copy()

        # Append current metrics
        new_state.internal_consistency_history.append(metrics.internal_consistency)
        new_state.prediction_reversal_risk_history.append(metrics.prediction_reversal_risk)
        new_state.volatility_index_history.append(metrics.volatility_index)
        new_state.goal_alignment_history.append(metrics.goal_alignment)
        new_state.factual_alignment_history.append(metrics.factual_alignment)
        new_state.identity_stability_history.append(metrics.identity_stability)
        new_state.drift_magnitude_history.append(metrics.drift_magnitude)
        new_state.overall_coherence_history.append(metrics.overall_coherence)

        # Apply sliding window
        new_state.window_trim(self.window)

        return new_state

    def _compute_metrics(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
        goal_state: Optional[Any],
    ) -> CoherenceMetrics:
        """Compute coherence metrics for current turn."""

        # Internal consistency
        internal_consistency = self._compute_internal_consistency(prev_state, turn)

        # Prediction reversal risk
        prediction_reversal_risk = self._compute_reversal_risk(prev_state, turn)

        # Volatility
        volatility = self._compute_volatility(prev_state, turn)

        # Goal alignment
        goal_alignment = self._compute_goal_alignment(turn, goal_state)

        # Factual alignment (placeholder - would need fact-checking)
        factual_alignment = 0.7  # Default assumption

        # Identity stability
        identity_stability = self._compute_identity_stability(prev_state, turn)

        # Drift magnitude
        drift_magnitude = self._compute_drift(prev_state, turn)

        # Drift direction
        drift_direction = self._compute_drift_direction(prev_state)

        # Overall coherence (weighted average)
        overall = (
            self.weights["internal_consistency"] * internal_consistency
            + self.weights["prediction_reversal_risk"] * (1 - prediction_reversal_risk)
            + self.weights["volatility_index"] * (1 - volatility)
            + self.weights["goal_alignment"] * goal_alignment
            + self.weights["factual_alignment"] * factual_alignment
            + self.weights["identity_stability"] * identity_stability
        )

        return CoherenceMetrics(
            internal_consistency=internal_consistency,
            prediction_reversal_risk=prediction_reversal_risk,
            volatility_index=volatility,
            goal_alignment=goal_alignment,
            factual_alignment=factual_alignment,
            identity_stability=identity_stability,
            drift_magnitude=drift_magnitude,
            drift_direction=drift_direction,
            overall_coherence=max(0.0, min(1.0, overall)),
        )

    def _compute_internal_consistency(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
    ) -> float:
        """Check if current turn is internally consistent."""
        if prev_state is None or not prev_state.overall_coherence_history:
            return 0.8  # Default for first turn

        # Use quality score as proxy for consistency
        quality = getattr(turn, "quality_score", 0.7)
        return min(1.0, quality + 0.1)

    def _compute_reversal_risk(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
    ) -> float:
        """Estimate risk of contradicting next turn."""
        if prev_state is None or len(prev_state.internal_consistency_history) < 2:
            return 0.2  # Low default

        # If recent consistency is declining, higher reversal risk
        recent = prev_state.internal_consistency_history[-3:]
        if len(recent) >= 2:
            trend = recent[-1] - recent[0]
            if trend < -0.1:
                return min(1.0, 0.3 + abs(trend))

        return 0.2

    def _compute_volatility(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
    ) -> float:
        """Compute state volatility."""
        if prev_state is None or len(prev_state.overall_coherence_history) < 3:
            return 0.1  # Low default

        # Variance of recent coherence scores
        recent = prev_state.overall_coherence_history[-5:]
        if len(recent) < 2:
            return 0.1

        mean = sum(recent) / len(recent)
        variance = sum((x - mean) ** 2 for x in recent) / len(recent)
        return min(1.0, variance * 5)  # Scale variance

    def _compute_goal_alignment(
        self,
        turn: Any,
        goal_state: Optional[Any],
    ) -> float:
        """Check if response serves the goal."""
        if goal_state is None:
            return 0.7  # Default

        # Get purpose from goal state
        purpose = getattr(goal_state, "purpose", "")
        if not purpose:
            return 0.7

        # Get response from turn
        response = getattr(turn, "assistant_output", "")
        if not response:
            return 0.5

        # Simple keyword overlap check
        goal_words = set(w.lower() for w in purpose.split() if len(w) > 3)
        response_words = set(w.lower() for w in response.split() if len(w) > 3)

        if not goal_words:
            return 0.7

        overlap = len(goal_words & response_words) / len(goal_words)
        return min(1.0, overlap + 0.3)  # Add baseline

    def _compute_identity_stability(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
    ) -> float:
        """Check if response style is consistent."""
        if prev_state is None or not prev_state.identity_stability_history:
            return 0.8  # Default

        # Simple: assume stable unless volatility is high
        if prev_state.volatility_index_history:
            recent_volatility = prev_state.volatility_index_history[-1]
            return max(0.3, 1.0 - recent_volatility)

        return 0.8

    def _compute_drift(
        self,
        prev_state: Optional[CoherenceState],
        turn: Any,
    ) -> float:
        """Compute drift from initial state."""
        if prev_state is None or len(prev_state.overall_coherence_history) < 3:
            return 0.0  # No drift yet

        initial = prev_state.overall_coherence_history[0]
        current = prev_state.overall_coherence_history[-1]
        return abs(current - initial)

    def _compute_drift_direction(
        self,
        prev_state: Optional[CoherenceState],
    ) -> str:
        """Determine drift direction."""
        if prev_state is None or len(prev_state.overall_coherence_history) < 3:
            return "stable"

        recent = prev_state.overall_coherence_history[-3:]
        trend = recent[-1] - recent[0]

        if trend > 0.1:
            return "improving"
        elif trend < -0.1:
            return "degrading"
        return "stable"

    def should_intervene(self, state: CoherenceState) -> Tuple[bool, str]:
        """
        Detect if conversation is degrading and needs intervention.

        Returns:
            Tuple of (should_intervene: bool, reason: str)
        """
        if not state.overall_coherence_history:
            return False, "No history"

        # Check volatility trend
        if len(state.volatility_index_history) >= 3:
            recent_vol = state.volatility_index_history[-3:]
            if all(v > 0.5 for v in recent_vol):
                return True, "High sustained volatility"

        # Check consistency degradation
        if len(state.internal_consistency_history) >= 3:
            recent = state.internal_consistency_history[-3:]
            if recent[-1] < 0.5 and recent[-1] < recent[0]:
                return True, "Consistency degrading"

        # Check high reversal risk
        if state.prediction_reversal_risk_history:
            if state.prediction_reversal_risk_history[-1] > 0.7:
                return True, "High reversal risk"

        # Check overall coherence threshold
        if state.overall_coherence_history:
            if state.overall_coherence_history[-1] < 0.4:
                return True, "Overall coherence too low"

        return False, "Coherence stable"

    def get_summary(self, state: CoherenceState) -> Dict[str, Any]:
        """Get summary of coherence state."""
        return {
            "session_id": state.session_id,
            "current_turn": state.current_turn,
            "current_coherence": state.current_metrics.overall_coherence,
            "average_coherence": state.get_average_coherence(),
            "trend": state.get_recent_trend(),
            "drift_direction": state.current_metrics.drift_direction,
            "should_intervene": self.should_intervene(state),
        }


def create_initial_metrics() -> CoherenceMetrics:
    """Create initial coherence metrics for first turn."""
    return CoherenceMetrics(
        internal_consistency=0.8,
        prediction_reversal_risk=0.2,
        volatility_index=0.1,
        goal_alignment=0.7,
        factual_alignment=0.7,
        identity_stability=0.8,
        drift_magnitude=0.0,
        drift_direction="stable",
        overall_coherence=0.75,
    )


def create_initial_state(session_id: Optional[str] = None) -> CoherenceState:
    """Create initial coherence state for new session."""
    return CoherenceState(
        session_id=session_id or str(uuid.uuid4()),
        current_turn=0,
        current_metrics=create_initial_metrics(),
    )

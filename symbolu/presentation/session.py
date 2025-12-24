"""Presentation Layer Session State Manager.

Implements: PRESENTATION_LAYER_v1.0.md Part 7.2

Tracks session context across turns for presentation rules:
- Turn count
- Score history (for consecutive low/high detection)
- Motion history (for staleness detection)
- Vritti history (for mode transitions)
"""

from typing import Optional, TYPE_CHECKING

from symbolu.presentation.signals import SessionContext, VrittiDistribution

if TYPE_CHECKING:
    from symbolu.chitta_vritti.types import ChittaVrittiResult


class SessionStateManager:
    """Tracks session context for presentation rules.

    Part 7.2: Maintains history and computes derived metrics.

    This manager is stateful and should be reset between sessions.
    It computes consecutive streaks, accumulates metrics, and provides
    the SessionContext used by presentation rules.
    """

    def __init__(self, history_window: int = 10):
        """Initialize session state.

        Args:
            history_window: Number of turns to keep in history
        """
        self._history_window = history_window
        self._turn_count = 0
        self._score_history: list[float] = []
        self._motion_history: list[float] = []
        self._vritti_history: list[str] = []
        self._accumulated_smrti = 0.0

    def update(
        self,
        score: float,
        motion: float,
        dominant_vritti: str,
        vritti: Optional[VrittiDistribution] = None,
    ) -> SessionContext:
        """Update session state and return context.

        Part 7.2: Called after each CV computation.

        Args:
            score: Current CV score
            motion: Current motion signal
            dominant_vritti: Current dominant vritti mode
            vritti: Optional full distribution for accumulated_smrti

        Returns:
            Updated SessionContext for rule evaluation
        """
        self._turn_count += 1

        # Append to histories
        self._score_history.append(score)
        self._motion_history.append(motion)
        self._vritti_history.append(dominant_vritti)

        # Trim histories to window
        if len(self._score_history) > self._history_window:
            self._score_history = self._score_history[-self._history_window :]
        if len(self._motion_history) > self._history_window:
            self._motion_history = self._motion_history[-self._history_window :]
        if len(self._vritti_history) > self._history_window:
            self._vritti_history = self._vritti_history[-self._history_window :]

        # Update accumulated smrti from vritti distribution
        if vritti is not None:
            self._accumulated_smrti = vritti.smrti

        return self._build_context()

    def update_from_cv(
        self,
        result: "ChittaVrittiResult",
        motion: float = 0.0,
    ) -> SessionContext:
        """Update from a ChittaVrittiResult.

        Convenience method for integration with CV engine.

        Args:
            result: Output from ChittaVrittiEngine.compute()
            motion: Motion signal (not in CV result, must be provided)

        Returns:
            Updated SessionContext
        """
        vritti = VrittiDistribution.from_dict(result.vritti)
        return self.update(
            score=result.score,
            motion=motion,
            dominant_vritti=result.dominant_vritti,
            vritti=vritti,
        )

    def get_context(self) -> SessionContext:
        """Get current session context without updating.

        Returns:
            Current SessionContext based on accumulated state
        """
        return self._build_context()

    def reset(self) -> None:
        """Reset session state.

        Part 7.2: Called at session boundaries.
        """
        self._turn_count = 0
        self._score_history.clear()
        self._motion_history.clear()
        self._vritti_history.clear()
        self._accumulated_smrti = 0.0

    def _build_context(self) -> SessionContext:
        """Build SessionContext from current state."""
        return SessionContext(
            turn_count=self._turn_count,
            consecutive_low_scores=self._count_consecutive_low(
                self._score_history, threshold=0.5
            ),
            consecutive_high_scores=self._count_consecutive_high(
                self._score_history, threshold=0.8
            ),
            consecutive_low_motion=self._count_consecutive_low(
                self._motion_history, threshold=0.1
            ),
            previous_dominant_vritti=(
                self._vritti_history[-2] if len(self._vritti_history) > 1 else None
            ),
            accumulated_smrti=self._accumulated_smrti,
        )

    def _count_consecutive_low(
        self,
        history: list[float],
        threshold: float,
    ) -> int:
        """Count consecutive values below threshold from end.

        Part 7.2: Used for streak detection.
        """
        count = 0
        for value in reversed(history):
            if value < threshold:
                count += 1
            else:
                break
        return count

    def _count_consecutive_high(
        self,
        history: list[float],
        threshold: float,
    ) -> int:
        """Count consecutive values above threshold from end.

        Part 7.2: Used for streak detection.
        """
        count = 0
        for value in reversed(history):
            if value > threshold:
                count += 1
            else:
                break
        return count

    @property
    def turn_count(self) -> int:
        """Current turn count."""
        return self._turn_count

    @property
    def history_window(self) -> int:
        """Maximum history window size."""
        return self._history_window

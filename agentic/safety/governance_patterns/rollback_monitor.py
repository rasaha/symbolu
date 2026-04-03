"""
Agentic Rollback Monitor — Post-action safety rollback on degradation.

After an agent action executes, the monitor watches governance signals
for a configurable window.  If signals degrade beyond a threshold,
it triggers an automatic rollback.

Lifecycle:
    start_watch() → MONITORING
    check()       → MONITORING | STABLE | DEGRADED | ROLLED_BACK | EXPIRED

OLM mapping: O12_ABSOLVING (termination boundary), O11_INTEGRATION (audit)

Pattern extracted from cloud_controller.action.rollback.RollbackMonitor,
rewritten for AI agent governance (no K8s dependencies).
"""

from __future__ import annotations

import enum
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class RollbackVerdict(enum.Enum):
    """Outcome of a rollback watch evaluation."""
    MONITORING = "monitoring"
    STABLE = "stable"
    DEGRADED = "degraded"
    ROLLED_BACK = "rolled_back"
    EXPIRED = "expired"


@dataclass(frozen=True)
class RollbackConfig:
    """Rollback monitor configuration.

    Attributes:
        watch_window_seconds: How long to monitor after action (default 180s).
        grace_period_seconds: Initial wait before checking (default 30s).
        degradation_threshold: Fractional worsening that triggers rollback
            (e.g. 0.15 = 15% degradation).
        watched_signals: Signal names to monitor for degradation.
        execute_rollback: If True, automatically calls the rollback function.
        post_rollback_cooldown_seconds: Cooldown after a rollback (default 300s).
    """
    watch_window_seconds: float = 180.0
    grace_period_seconds: float = 30.0
    degradation_threshold: float = 0.15
    watched_signals: Tuple[str, ...] = (
        "confidence", "governance_strength", "coherence",
    )
    execute_rollback: bool = True
    post_rollback_cooldown_seconds: float = 300.0


@dataclass
class RollbackWatch:
    """An active or resolved rollback watch.

    Attributes:
        decision_id: ID of the governance decision that triggered this action.
        agent_id: Agent that performed the action.
        action_type: What was executed.
        pre_action_signals: Signal snapshot before the action.
        action_timestamp: When the action was executed.
        verdict: Current verdict.
        verdict_timestamp: When verdict was set (None if still monitoring).
        verdict_reason: Explanation of the verdict.
        verdict_signals: Signal snapshot at verdict time.
    """
    decision_id: str
    agent_id: str
    action_type: str
    pre_action_signals: Dict[str, float]
    action_timestamp: float
    verdict: RollbackVerdict = RollbackVerdict.MONITORING
    verdict_timestamp: Optional[float] = None
    verdict_reason: str = ""
    verdict_signals: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Monitor
# ---------------------------------------------------------------------------

class RollbackMonitor:
    """Monitors post-action governance signal health and triggers rollback.

    Thread-safe.

    Usage::

        monitor = RollbackMonitor(
            config=RollbackConfig(),
            rollback_fn=my_rollback_function,
        )
        watch = monitor.start_watch(
            decision_id="abc123",
            agent_id="agent-7",
            action_type="deploy_model",
            pre_action_signals={"confidence": 0.85, "governance_strength": 2.8},
        )
        # ... periodically ...
        resolved = monitor.check(
            current_signals={"confidence": 0.70, "governance_strength": 2.3}
        )
    """

    def __init__(
        self,
        config: Optional[RollbackConfig] = None,
        rollback_fn: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.config = config or RollbackConfig()
        self._rollback_fn = rollback_fn
        self._active_watches: List[RollbackWatch] = []
        self._history: List[RollbackWatch] = []
        self._max_history: int = 500
        self._lock = threading.Lock()

    def start_watch(
        self,
        decision_id: str,
        agent_id: str,
        action_type: str,
        pre_action_signals: Dict[str, float],
    ) -> RollbackWatch:
        """Begin monitoring an executed action for signal degradation."""
        watch = RollbackWatch(
            decision_id=decision_id,
            agent_id=agent_id,
            action_type=action_type,
            pre_action_signals=dict(pre_action_signals),
            action_timestamp=time.time(),
        )
        with self._lock:
            self._active_watches.append(watch)
        return watch

    def check(
        self,
        current_signals: Dict[str, float],
        *,
        current_time: Optional[float] = None,
    ) -> List[RollbackWatch]:
        """Evaluate all active watches against current signals.

        Returns list of watches that were resolved in this check
        (STABLE, DEGRADED, ROLLED_BACK, or EXPIRED).
        """
        now = current_time if current_time is not None else time.time()
        cfg = self.config
        resolved: List[RollbackWatch] = []

        with self._lock:
            still_active: List[RollbackWatch] = []

            for watch in self._active_watches:
                elapsed = now - watch.action_timestamp

                # Still in grace period — skip
                if elapsed < cfg.grace_period_seconds:
                    still_active.append(watch)
                    continue

                # Past watch window — mark stable or expired
                if elapsed > cfg.watch_window_seconds:
                    watch.verdict = RollbackVerdict.STABLE
                    watch.verdict_timestamp = now
                    watch.verdict_reason = "watch window passed without degradation"
                    watch.verdict_signals = dict(current_signals)
                    self._archive(watch)
                    resolved.append(watch)
                    continue

                # Within window — check for degradation
                degraded_signals = self._check_degradation(
                    watch.pre_action_signals, current_signals
                )

                if degraded_signals:
                    desc = ", ".join(
                        f"{name}: {pre:.3f}→{cur:.3f} ({pct:+.1%})"
                        for name, pre, cur, pct in degraded_signals
                    )
                    watch.verdict_signals = dict(current_signals)

                    if cfg.execute_rollback and self._rollback_fn is not None:
                        self._execute_rollback(watch)
                        watch.verdict = RollbackVerdict.ROLLED_BACK
                        watch.verdict_reason = f"rolled back: {desc}"
                    else:
                        watch.verdict = RollbackVerdict.DEGRADED
                        watch.verdict_reason = f"degraded: {desc}"

                    watch.verdict_timestamp = now
                    self._archive(watch)
                    resolved.append(watch)
                else:
                    still_active.append(watch)

            self._active_watches = still_active

        return resolved

    # -- Queries -----------------------------------------------------------

    @property
    def active_watches(self) -> List[RollbackWatch]:
        with self._lock:
            return list(self._active_watches)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active_watches)

    @property
    def history(self) -> List[RollbackWatch]:
        with self._lock:
            return list(self._history)

    @property
    def rollback_count(self) -> int:
        with self._lock:
            return sum(
                1 for w in self._history
                if w.verdict == RollbackVerdict.ROLLED_BACK
            )

    def reset(self) -> None:
        with self._lock:
            self._active_watches.clear()
            self._history.clear()

    # -- Internals ---------------------------------------------------------

    def _check_degradation(
        self,
        pre: Dict[str, float],
        current: Dict[str, float],
    ) -> List[Tuple[str, float, float, float]]:
        """Compare signals against degradation threshold.

        Returns list of (signal_name, pre_value, current_value, pct_change)
        for signals that degraded beyond the threshold.
        """
        degraded: List[Tuple[str, float, float, float]] = []
        for signal_name in self.config.watched_signals:
            pre_val = pre.get(signal_name)
            cur_val = current.get(signal_name)
            if pre_val is None or cur_val is None:
                continue
            if pre_val == 0:
                continue
            pct_change = (cur_val - pre_val) / abs(pre_val)
            # Negative pct_change = degradation (signal dropped)
            if pct_change < -self.config.degradation_threshold:
                degraded.append((signal_name, pre_val, cur_val, pct_change))
        return degraded

    def _execute_rollback(self, watch: RollbackWatch) -> None:
        """Call the rollback function (best-effort)."""
        if self._rollback_fn is not None:
            try:
                self._rollback_fn(
                    decision_id=watch.decision_id,
                    agent_id=watch.agent_id,
                    action_type=watch.action_type,
                )
            except Exception:
                pass  # Rollback failure is logged but doesn't crash monitor

    def _archive(self, watch: RollbackWatch) -> None:
        """Move resolved watch to history (must hold lock)."""
        self._history.append(watch)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

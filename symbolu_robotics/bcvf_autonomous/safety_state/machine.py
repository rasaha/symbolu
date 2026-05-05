"""SafetyStateMachine — the four-state behavioural contract.

The machine wraps:

* a :class:`~safety_state.triggers.RollingWindow` of recent ticks;
* a :class:`SafetyStateMachineConfig` carrying the calibration
  knobs (window length, dwell times, per-transition thresholds);
* a transition log (every transition timestamped + cause-named).

The public surface is intentionally thin:

* ``observe(record_or_tick)`` — feed one or many per-tick views
  and run dispatch. Returns the post-observe state.
* ``state`` — the current named state.
* ``transition_log`` — read-only tuple of transition entries.
* ``reset_with_diagnostic_clear(operator, reason)`` — the manual-
  reset gate that walks FAULT → DEGRADED or FAILSAFE → FAULT.
* ``current_state_dwell_ticks`` — count of ticks held in the
  current state since last transition (drives the recovery
  predicate).

See ``SAFETY_STATE_MACHINE_DESIGN.md`` for the full design doc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple, Union

from ..trust_diagnostics import TrustShapedEpisodeRecord
from .errors import IllegalTransitionError, SafetyStateMachineError
from .state import (
    LEGAL_TRANSITIONS,
    SafetyState,
    StateTransition,
    TRIGGER_EXCLUSION_SUSTAINED,
    TRIGGER_MANUAL_RESET,
    TRIGGER_MULTI_PREDICTOR_EXCLUDED,
    TRIGGER_NEAR_VETO_RATE,
    TRIGGER_SUSTAINED_RECOVERY,
    is_legal_transition,
    lookup_transition,
)
from .triggers import RollingWindow, TickView, tick_views_from_record


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SafetyStateMachineConfig:
    """Calibration knobs for :class:`SafetyStateMachine`.

    Defaults are chosen so the characterization grid's nominal
    scenarios sit in NORMAL and the failure families
    (``accelerating``, ``outlier``, ``sensor_dropout``) walk
    DEGRADED → FAULT cleanly at the documented magnitudes. A
    deployment partner is expected to retune against their
    operational design domain — see
    ``SAFETY_STATE_MACHINE_DESIGN.md`` §3.
    """

    rolling_window_ticks: int = 200
    near_veto_consec_floor: int = 3
    near_veto_rate_threshold: float = 0.10
    bcvf_active_threshold: float = 0.05
    bcvf_active_rate_threshold: float = 0.50
    exclusion_persistence_ticks: int = 5
    failsafe_excluded_predictor_count: int = 2
    t_recovery_ticks: int = 100

    def __post_init__(self) -> None:
        if self.rolling_window_ticks < 1:
            raise ValueError("rolling_window_ticks must be ≥ 1")
        if self.near_veto_consec_floor < 1:
            raise ValueError("near_veto_consec_floor must be ≥ 1")
        if not (0.0 <= self.near_veto_rate_threshold <= 1.0):
            raise ValueError("near_veto_rate_threshold must be in [0, 1]")
        if self.bcvf_active_threshold < 0.0:
            raise ValueError("bcvf_active_threshold must be ≥ 0")
        if not (0.0 <= self.bcvf_active_rate_threshold <= 1.0):
            raise ValueError("bcvf_active_rate_threshold must be in [0, 1]")
        if self.exclusion_persistence_ticks < 1:
            raise ValueError("exclusion_persistence_ticks must be ≥ 1")
        if self.failsafe_excluded_predictor_count < 2:
            raise ValueError(
                "failsafe_excluded_predictor_count must be ≥ 2 — "
                "FAILSAFE is multi-predictor-loss by definition"
            )
        if self.t_recovery_ticks < 1:
            raise ValueError("t_recovery_ticks must be ≥ 1")


# --------------------------------------------------------------------------- #
# Transition log entry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StateTransitionLogEntry:
    """One transition the machine recorded.

    Fields:

    * ``timestamp`` — wall-clock at the moment the transition
      committed (UTC by default; injectable clock for tests).
    * ``transition`` — the :class:`StateTransition` row from the
      legal-edge table (carries from / to / trigger / ASIL).
    * ``cause`` — human-readable description of why the trigger
      fired (e.g. ``"near_veto_rate=0.150 ≥ threshold 0.100"``).
    * ``tick_index`` — the index of the tick that committed the
      transition. ``-1`` for manual resets.
    * ``operator`` — set on manual-reset transitions; ``None``
      otherwise. The audit trail records who pressed the button.
    """

    timestamp: datetime
    transition: StateTransition
    cause: str
    tick_index: int
    operator: Optional[str] = None


# Type alias for what observe() accepts.
ObserveInput = Union[TickView, TrustShapedEpisodeRecord]


# --------------------------------------------------------------------------- #
# Machine
# --------------------------------------------------------------------------- #


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StateTransitionLog:
    """Append-only log of transition entries.

    Wraps a list with a typed read-only view. Tests assert on the
    list contents directly via :meth:`entries`; production callers
    read :meth:`as_tuple` for an immutable snapshot they can
    serialize without worrying about concurrent mutation.
    """

    _entries: List[StateTransitionLogEntry] = field(default_factory=list)

    def append(self, entry: StateTransitionLogEntry) -> None:
        self._entries.append(entry)

    def entries(self) -> List[StateTransitionLogEntry]:
        """Live list — caller must not mutate (machine appends)."""
        return self._entries

    def as_tuple(self) -> Tuple[StateTransitionLogEntry, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        """Clear the log. Used by tests + by an explicit
        diagnostic clear that wants to wipe pre-incident history."""
        self._entries = []


class SafetyStateMachine:
    """Four-state safety state machine.

    See ``SAFETY_STATE_MACHINE_DESIGN.md`` for the full design.

    Args:
        config: calibration knobs. Defaults to
            :class:`SafetyStateMachineConfig` defaults.
        clock: callable returning the current ``datetime`` for
            transition log timestamps. Defaults to UTC ``now``.
            Tests inject a fake clock.
    """

    def __init__(
        self,
        config: Optional[SafetyStateMachineConfig] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._config = config or SafetyStateMachineConfig()
        self._clock = clock or _utc_now
        self._state: SafetyState = SafetyState.NORMAL
        self._window = RollingWindow(self._config.rolling_window_ticks)
        # Ticks held in the current state since last transition.
        # Reported via current_state_dwell_ticks for diagnostics.
        self._dwell_ticks: int = 0
        # Consecutive ticks the recovery predicate has been
        # satisfied (near_veto_rate < threshold). Drives the
        # DEGRADED → NORMAL recovery dwell — incremented when
        # the predicate is satisfied, reset to 0 when it is not.
        # The two counters are deliberately separate so a long
        # period in DEGRADED with intermittent above-threshold
        # ticks does NOT auto-recover the moment rate dips below
        # threshold.
        self._below_threshold_ticks: int = 0
        # Ticks observed since machine creation. Identifies the
        # tick in the transition log when no explicit index is
        # provided to observe().
        self._tick_count: int = 0
        self._log = StateTransitionLog()

    # ----- public read-only properties ----- #

    @property
    def state(self) -> SafetyState:
        return self._state

    @property
    def config(self) -> SafetyStateMachineConfig:
        return self._config

    @property
    def transition_log(self) -> StateTransitionLog:
        return self._log

    @property
    def current_state_dwell_ticks(self) -> int:
        """Ticks the machine has held the current state since the
        last transition. Resets to 0 on every transition."""
        return self._dwell_ticks

    @property
    def n_ticks_observed(self) -> int:
        return self._tick_count

    # ----- core observe ----- #

    def observe(
        self,
        record_or_tick: ObserveInput,
        tick_index: Optional[int] = None,
        classification: Optional[str] = None,  # noqa: ARG002
    ) -> SafetyState:
        """Feed one or many per-tick views; run dispatch; return state.

        Accepts either a single :class:`TickView` (live planning
        loop, one tick at a time) or a full
        :class:`TrustShapedEpisodeRecord` (batch replay of a
        post-incident trace). For a record, every per-step row is
        appended to the rolling window in order and dispatch runs
        once per tick.

        ``tick_index`` is recorded on transition log entries;
        defaults to the running tick counter.

        ``classification`` is currently unused — accepted for
        forward-compat with a future variant that runs different
        thresholds per scenario class. Kept on the signature so
        adding the dispatch later is non-breaking.

        Returns the post-observe state.
        """
        if isinstance(record_or_tick, TrustShapedEpisodeRecord):
            for tick in tick_views_from_record(record_or_tick):
                self._observe_one(tick, tick_index)
                if tick_index is not None:
                    tick_index += 1
            return self._state
        elif isinstance(record_or_tick, TickView):
            self._observe_one(record_or_tick, tick_index)
            return self._state
        else:
            raise TypeError(
                f"observe() expects TickView or TrustShapedEpisodeRecord; "
                f"got {type(record_or_tick).__name__}"
            )

    def _observe_one(
        self, tick: TickView, tick_index: Optional[int]
    ) -> None:
        self._window.append(tick)
        self._tick_count += 1
        self._dwell_ticks += 1
        if tick_index is None:
            tick_index = self._tick_count - 1
        # Run the per-state dispatcher.
        if self._state == SafetyState.NORMAL:
            self._dispatch_from_normal(tick_index)
        elif self._state == SafetyState.DEGRADED:
            self._dispatch_from_degraded(tick_index)
        elif self._state == SafetyState.FAULT:
            self._dispatch_from_fault(tick_index)
        # FAILSAFE has no automatic transitions; only manual reset
        # (handled by reset_with_diagnostic_clear).

    # ----- per-state dispatchers ----- #

    def _dispatch_from_normal(self, tick_index: int) -> None:
        rate = self._window.near_veto_rate(self._config.near_veto_consec_floor)
        if rate >= self._config.near_veto_rate_threshold:
            self._transition(
                SafetyState.NORMAL,
                SafetyState.DEGRADED,
                cause=(
                    f"near_veto_rate={rate:.3f} ≥ threshold "
                    f"{self._config.near_veto_rate_threshold:.3f}"
                ),
                tick_index=tick_index,
            )

    def _dispatch_from_degraded(self, tick_index: int) -> None:
        # Escalation check first — DEGRADED → FAULT takes
        # precedence over DEGRADED → NORMAL (escalation always
        # wins over recovery on the same tick).
        excluded_persistent = self._window.any_excluded_persistence(
            self._config.exclusion_persistence_ticks
        )
        bcvf_rate = self._window.bcvf_active_rate(
            self._config.bcvf_active_threshold
        )
        bcvf_sustained = bcvf_rate >= self._config.bcvf_active_rate_threshold
        if excluded_persistent and bcvf_sustained:
            self._transition(
                SafetyState.DEGRADED,
                SafetyState.FAULT,
                cause=(
                    f"exclusion_sustained "
                    f"(persistence ≥ {self._config.exclusion_persistence_ticks}) "
                    f"AND bcvf_active_rate={bcvf_rate:.3f} ≥ "
                    f"threshold {self._config.bcvf_active_rate_threshold:.3f}"
                ),
                tick_index=tick_index,
            )
            return
        # Recovery: the rate has been below threshold for at
        # least T_recovery consecutive ticks. The
        # _below_threshold_ticks counter is updated below;
        # reading it here is the recovery trigger.
        rate = self._window.near_veto_rate(self._config.near_veto_consec_floor)
        if rate < self._config.near_veto_rate_threshold:
            self._below_threshold_ticks += 1
        else:
            self._below_threshold_ticks = 0
        if (
            rate < self._config.near_veto_rate_threshold
            and self._below_threshold_ticks
                >= self._config.t_recovery_ticks
        ):
            self._transition(
                SafetyState.DEGRADED,
                SafetyState.NORMAL,
                cause=(
                    f"sustained_recovery "
                    f"(near_veto_rate={rate:.3f} < threshold "
                    f"{self._config.near_veto_rate_threshold:.3f} for "
                    f"≥ {self._config.t_recovery_ticks} ticks)"
                ),
                tick_index=tick_index,
            )

    def _dispatch_from_fault(self, tick_index: int) -> None:
        n_excl = self._window.distinct_excluded_predictors()
        if n_excl >= self._config.failsafe_excluded_predictor_count:
            self._transition(
                SafetyState.FAULT,
                SafetyState.FAILSAFE,
                cause=(
                    f"distinct_excluded_predictors={n_excl} ≥ "
                    f"threshold {self._config.failsafe_excluded_predictor_count}"
                ),
                tick_index=tick_index,
            )

    # ----- transition primitive ----- #

    def _transition(
        self,
        from_state: SafetyState,
        to_state: SafetyState,
        cause: str,
        tick_index: int,
        operator: Optional[str] = None,
    ) -> None:
        """Commit a transition. Raises IllegalTransitionError if the
        edge is not in the legal-edge table."""
        if self._state != from_state:
            raise SafetyStateMachineError(
                f"transition from_state mismatch: machine is in "
                f"{self._state.name}, transition asserts from_state="
                f"{from_state.name}"
            )
        if not is_legal_transition(from_state, to_state):
            raise IllegalTransitionError(from_state, to_state, reason=cause)
        edge = lookup_transition(from_state, to_state)
        entry = StateTransitionLogEntry(
            timestamp=self._clock(),
            transition=edge,
            cause=cause,
            tick_index=tick_index,
            operator=operator,
        )
        self._log.append(entry)
        self._state = to_state
        self._dwell_ticks = 0
        self._below_threshold_ticks = 0

    # ----- manual reset ----- #

    def reset_with_diagnostic_clear(
        self,
        operator: str,
        reason: str,
    ) -> SafetyState:
        """Walk FAULT → DEGRADED or FAILSAFE → FAULT.

        The machine refuses to reset from NORMAL or DEGRADED — the
        manual-reset path is for the latched FAULT / FAILSAFE
        states only. Calling reset from NORMAL / DEGRADED raises
        :class:`SafetyStateMachineError`.

        ``operator`` and ``reason`` are recorded on the transition
        log for the audit trail.
        """
        if not operator:
            raise ValueError("operator must be a non-empty string")
        if not reason:
            raise ValueError("reason must be a non-empty string")
        if self._state == SafetyState.FAULT:
            target = SafetyState.DEGRADED
        elif self._state == SafetyState.FAILSAFE:
            target = SafetyState.FAULT
        else:
            raise SafetyStateMachineError(
                f"reset_with_diagnostic_clear() called from "
                f"{self._state.name}; reset is only valid from "
                f"FAULT or FAILSAFE"
            )
        cause = (
            f"manual_reset (operator={operator!r}, reason={reason!r})"
        )
        self._transition(
            self._state,
            target,
            cause=cause,
            tick_index=-1,
            operator=operator,
        )
        return self._state

"""Trigger-condition primitives + rolling-window view over per-step diagnostics.

Two pieces:

* :class:`RollingWindow` — append-only ring buffer of the last
  ``N`` per-step observations the state machine has seen. Tracks
  the per-step quantities the trigger predicates read
  (``bcvf_total``, ``is_excluded``, ``consec_suspect``) plus an
  internal "ticks held in current state" counter the
  recovery-dwell predicate uses.
* Trigger functions — pure, side-effect-free callables that take
  a :class:`RollingWindow` + a :class:`SafetyStateMachineConfig`
  and return ``bool``. Each trigger is named (``__name__`` is
  the cause-string the transition log records).

The :class:`TriggerCondition` Protocol exists for type-system
clarity — a future contributor wiring a custom trigger only
needs to satisfy the protocol; the existing trigger functions
all bind ``(window, config) → bool`` directly so the protocol
never needs an instantiated class.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional, Protocol, Tuple

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord


# --------------------------------------------------------------------------- #
# Per-tick view extracted from a TrustShapedEpisodeRecord row
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TickView:
    """One per-tick row extracted from a TrustShapedEpisodeRecord.

    Fields mirror the per-step arrays in
    :class:`~symbolu_robotics.bcvf_autonomous.trust_diagnostics.TrustShapedEpisodeRecord`,
    sliced to the single tick the state machine is observing. The
    state machine works tick-by-tick (one ``observe()`` per
    planning step) so the rolling window aggregates ticks rather
    than full episodes.
    """

    bcvf_total: float
    is_excluded: np.ndarray         # (M,) bool
    consec_suspect: np.ndarray      # (M,) int
    M: int


def tick_views_from_record(
    record: TrustShapedEpisodeRecord,
) -> Tuple[TickView, ...]:
    """Extract per-tick :class:`TickView` rows from an episode record.

    A caller using the state machine in batch mode (replaying a
    JSON-dumped record after a fleet trip) can iterate these
    views and feed them to the machine one at a time. Online use
    (live planning loop) constructs :class:`TickView` directly
    each tick from the live trust-computer output.
    """
    if record.n_steps == 0:
        return ()
    consec_full = (
        record.per_step_consec_suspect
        if record.per_step_consec_suspect.size
        else np.zeros((record.n_steps, record.M), dtype=np.int64)
    )
    excl_full = (
        record.per_step_is_excluded
        if record.per_step_is_excluded.size
        else np.zeros((record.n_steps, record.M), dtype=bool)
    )
    out = []
    for t in range(record.n_steps):
        out.append(
            TickView(
                bcvf_total=float(record.per_step_bcvf_total[t]),
                is_excluded=np.asarray(excl_full[t], dtype=bool),
                consec_suspect=np.asarray(consec_full[t], dtype=np.int64),
                M=int(record.M),
            )
        )
    return tuple(out)


# --------------------------------------------------------------------------- #
# Rolling window
# --------------------------------------------------------------------------- #


class RollingWindow:
    """Fixed-capacity ring buffer of :class:`TickView` rows.

    ``append`` is O(1) amortised. ``predicate_rate`` and the
    convenience scans (``any_excluded_persistence``,
    ``distinct_excluded_predictors``) walk the buffer once and
    return the per-trigger summary statistics. The window is the
    only thing the trigger predicates read — they are pure
    functions of (window, config).

    Args:
        capacity: window length in ticks. Must be ≥ 1.
    """

    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be ≥ 1; got {capacity}")
        self._capacity = int(capacity)
        self._ticks: Deque[TickView] = deque(maxlen=self._capacity)

    @property
    def capacity(self) -> int:
        return self._capacity

    def __len__(self) -> int:
        return len(self._ticks)

    def append(self, tick: TickView) -> None:
        self._ticks.append(tick)

    def clear(self) -> None:
        self._ticks.clear()

    def latest(self) -> Optional[TickView]:
        return self._ticks[-1] if self._ticks else None

    # ----- predicates used by triggers ----- #

    def near_veto_rate(self, consec_floor: int) -> float:
        """Fraction of ticks in the window where any predictor's
        consec_suspect counter ≥ ``consec_floor``. Returns 0.0 on
        an empty window."""
        if not self._ticks:
            return 0.0
        n_near = 0
        for tick in self._ticks:
            if tick.consec_suspect.size and (
                tick.consec_suspect >= consec_floor
            ).any():
                n_near += 1
        return n_near / len(self._ticks)

    def bcvf_active_rate(self, threshold: float) -> float:
        """Fraction of ticks in the window where bcvf_total >
        threshold. Returns 0.0 on an empty window."""
        if not self._ticks:
            return 0.0
        n_active = sum(1 for t in self._ticks if t.bcvf_total > threshold)
        return n_active / len(self._ticks)

    def any_excluded_persistence(self, persistence_ticks: int) -> bool:
        """``True`` if any single predictor is ``is_excluded == True``
        for ≥ ``persistence_ticks`` consecutive ticks at the tail
        of the window. Encodes "exclusion is sustained" — a
        single-tick exclusion that immediately recovers does not
        trigger.
        """
        if persistence_ticks < 1:
            raise ValueError(
                f"persistence_ticks must be ≥ 1; got {persistence_ticks}"
            )
        if len(self._ticks) < persistence_ticks:
            return False
        # Walk from the tail backwards, tallying per-predictor
        # consecutive-excluded counts. As soon as any predictor's
        # count crosses the threshold, return True.
        tail = list(self._ticks)[-persistence_ticks:]
        # All ticks in the tail must have the same M; pick from the
        # first.
        M = tail[0].M
        # Defensive: if M varies across ticks (record reshape mid-
        # window), fall back to the smallest M. The state machine's
        # input contract is constant-M-per-episode; this guard is
        # for adversarial inputs that would otherwise crash.
        for tick in tail[1:]:
            if tick.M < M:
                M = tick.M
        consec = np.zeros(M, dtype=np.int64)
        for tick in tail:
            excl = tick.is_excluded
            for m in range(M):
                if m < excl.shape[0] and bool(excl[m]):
                    consec[m] += 1
                else:
                    consec[m] = 0
        return bool((consec >= persistence_ticks).any())

    def distinct_excluded_predictors(self) -> int:
        """Count of distinct predictor indices m such that any tick
        in the window has ``is_excluded[m] == True``. Used by the
        FAULT → FAILSAFE trigger.
        """
        if not self._ticks:
            return 0
        # Defensive about M variance: take the union over the per-
        # tick exclusion masks aligned to the smallest M. A multi-
        # episode rolling window with mid-window M change would
        # otherwise mis-count.
        M = min(t.M for t in self._ticks)
        if M <= 0:
            return 0
        union = np.zeros(M, dtype=bool)
        for tick in self._ticks:
            excl = tick.is_excluded[:M] if tick.is_excluded.size else None
            if excl is not None and excl.size:
                union |= excl.astype(bool)
        return int(union.sum())


# --------------------------------------------------------------------------- #
# Trigger Protocol
# --------------------------------------------------------------------------- #


class TriggerCondition(Protocol):
    """A pure callable predicate evaluated against a rolling window.

    Concrete triggers are bound via :func:`functools.partial` or
    inline lambdas in :mod:`safety_state.machine`; the protocol
    exists so a future contributor wiring a custom trigger has a
    type-checked target.
    """

    name: str

    def __call__(self, window: RollingWindow, config) -> bool:  # noqa: D401
        ...

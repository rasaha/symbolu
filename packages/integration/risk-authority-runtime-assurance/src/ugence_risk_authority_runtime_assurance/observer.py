"""Runtime assurance observer + bounded trajectory window (spec §11, §13, §24).

The observer consumes *already-admitted* observations (the trust gate is the
ingress, §10) and maintains the minimal derived working state needed to assess a
trajectory — it is **not** a second execution ledger (invariant I13). A
trajectory is keyed by ``(tenant_id, workflow_instance_id)`` (spec §11); within a
key the observer:

  * **deduplicates by ``event_id``** — a replayed/duplicate observation is an
    idempotent no-op (spec §13, invariant I8);
  * **re-sequences by ``(sequence_number, observed_at, event_id)``** — an
    out-of-order observation converges to the same ordered window, never widening
    authority (spec §13);
  * keeps only a **bounded window** of the most-recent observations per key.

The derived cumulative state (per-dimension exposure totals, per-action attempt
counts, latest data-class and context size) is computed from the ordered window
on demand — the numbers themselves are owned by the Agent Runtime; RA-7 only
reads and risk-types them (D3/§6).

The observer holds transient in-memory state only (spec §24). It requires no
Agent Runtime change: it is fed observations produced from the neutral event seam
by :mod:`.event_adapter`, or from external telemetry via the ingress.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .contracts import TrajectoryObservation, TrajectoryPolicyRef

__all__ = [
    "DEFAULT_WINDOW_SIZE",
    "Trajectory",
    "RuntimeAssuranceObserver",
]

#: Default bounded working-window size per trajectory key. Keeps the observer's
#: derived state bounded (spec §24) — not a durable ledger.
DEFAULT_WINDOW_SIZE = 256


def _sort_key(obs: TrajectoryObservation) -> Tuple[int, float, str]:
    seq = obs.sequence_number if obs.sequence_number is not None else 0
    ts = obs.observed_at.timestamp() if isinstance(obs.observed_at, datetime) else 0.0
    return (seq, ts, obs.event_id)


@dataclass(frozen=True)
class Trajectory:
    """An ordered, bounded view of one workflow instance's runtime behavior.

    Derived from the ordered observation window; carries no authority. The
    cumulative helpers below are *reads* of facts the Agent Runtime owns — RA-7
    risk-types them (D3), it does not maintain the authoritative accounting.
    """

    tenant_id: str
    workflow_instance_id: str
    envelope_id: str
    observations: Tuple[TrajectoryObservation, ...] = ()
    policy_ref: Optional[TrajectoryPolicyRef] = None
    truncated: bool = False

    @property
    def event_refs(self) -> Tuple[str, ...]:
        return tuple(o.event_id for o in self.observations)

    def cumulative_exposure(self) -> Dict[str, float]:
        """Sum the ``exposure`` detail across the window, per named dimension.

        Each observation MAY carry ``detail["exposure"] = {dimension: amount}`` (the
        per-action settled/consumed amount read from the runtime portfolio ledger).
        Missing/malformed amounts are skipped (never fabricated), so a partial view
        under-counts rather than inventing exposure.
        """

        totals: Dict[str, float] = {}
        for obs in self.observations:
            exposure = obs.detail.get("exposure")
            if not isinstance(exposure, Mapping):
                continue
            for dim, amount in exposure.items():
                val = _coerce_amount(amount)
                if val is None or not isinstance(dim, str) or not dim:
                    continue
                totals[dim] = totals.get(dim, 0.0) + val
        return totals

    def per_action_amounts(self) -> Dict[str, List[Tuple[str, float]]]:
        """Return, per dimension, the list of ``(action_id, amount)`` in order."""

        out: Dict[str, List[Tuple[str, float]]] = {}
        for obs in self.observations:
            exposure = obs.detail.get("exposure")
            if not isinstance(exposure, Mapping):
                continue
            for dim, amount in exposure.items():
                val = _coerce_amount(amount)
                if val is None or not isinstance(dim, str) or not dim:
                    continue
                out.setdefault(dim, []).append((obs.action_id, val))
        return out

    def attempts_by_action(self) -> Dict[str, int]:
        """Count runtime events per ``action_id`` — a proxy for retry/loop pressure.

        An action id that recurs across many observations (repeated
        invoke/fail/retry) is the retry-loop signal (spec §6, reason ``RETRY_LOOP``).
        Observations with no ``action_id`` are not counted.
        """

        counts: Dict[str, int] = {}
        for obs in self.observations:
            if not obs.action_id:
                continue
            counts[obs.action_id] = counts.get(obs.action_id, 0) + 1
        return counts

    def latest_detail(self, key: str) -> Optional[Any]:
        """Return the most-recent non-``None`` value of ``detail[key]`` in the window."""

        for obs in reversed(self.observations):
            val = obs.detail.get(key)
            if val is not None:
                return val
        return None

    def data_class_sequence(self) -> Tuple[str, ...]:
        """The ordered sequence of ``detail["data_class"]`` values seen (str only)."""

        seq: List[str] = []
        for obs in self.observations:
            dc = obs.detail.get("data_class")
            if isinstance(dc, str) and dc:
                seq.append(dc)
        return tuple(seq)


def _coerce_amount(amount: Any) -> Optional[float]:
    import math

    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return None
    val = float(amount)
    if not math.isfinite(val) or val < 0:
        return None
    return val


class RuntimeAssuranceObserver:
    """Builds bounded per-``(tenant, workflow)`` trajectories from admitted observations.

    Thread-safe. Read-only with respect to the Agent Runtime — observing it, or an
    observer being unavailable, never affects the runtime hot path (the event seam
    is optional; spec §7/§17). Holds transient in-memory state only (spec §24).
    """

    def __init__(self, *, window_size: int = DEFAULT_WINDOW_SIZE) -> None:
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self._window_size = window_size
        self._lock = threading.Lock()
        # key -> (ordered observations, seen event_ids, truncated flag)
        self._windows: Dict[Tuple[str, str], List[TrajectoryObservation]] = {}
        self._seen: Dict[Tuple[str, str], set] = {}
        self._truncated: Dict[Tuple[str, str], bool] = {}

    def record(self, obs: TrajectoryObservation) -> bool:
        """Record one admitted observation. Returns ``False`` if it was a duplicate.

        Idempotent by ``event_id`` within its trajectory key (invariant I8). The
        window is kept sorted and bounded; dropping the oldest observation marks the
        trajectory ``truncated`` so the evaluator knows its view is partial.
        """

        key = obs.trajectory_key
        with self._lock:
            seen = self._seen.setdefault(key, set())
            if obs.event_id in seen:
                return False
            seen.add(obs.event_id)
            window = self._windows.setdefault(key, [])
            window.append(obs)
            window.sort(key=_sort_key)
            if len(window) > self._window_size:
                # Drop the oldest; the view becomes bounded/partial (spec §24).
                overflow = len(window) - self._window_size
                del window[:overflow]
                self._truncated[key] = True
            return True

    def trajectory(
        self, tenant_id: str, workflow_instance_id: str
    ) -> Optional[Trajectory]:
        """Return the current bounded trajectory for a key, or ``None`` if unseen."""

        key = (tenant_id, workflow_instance_id)
        with self._lock:
            window = self._windows.get(key)
            if not window:
                return None
            observations = tuple(window)
            truncated = self._truncated.get(key, False)
        latest = observations[-1]
        # Prefer the most-recent policy ref carried on an observation.
        policy_ref = None
        for obs in reversed(observations):
            if obs.policy_ref is not None:
                policy_ref = obs.policy_ref
                break
        return Trajectory(
            tenant_id=tenant_id,
            workflow_instance_id=workflow_instance_id,
            envelope_id=latest.envelope_id,
            observations=observations,
            policy_ref=policy_ref,
            truncated=truncated,
        )

    def forget(self, tenant_id: str, workflow_instance_id: str) -> None:
        """Drop a trajectory's working state (e.g. after workflow completion)."""

        key = (tenant_id, workflow_instance_id)
        with self._lock:
            self._windows.pop(key, None)
            self._seen.pop(key, None)
            self._truncated.pop(key, None)

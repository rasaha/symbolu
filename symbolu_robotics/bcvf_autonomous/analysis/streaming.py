"""Streaming online aggregator over per-episode trust diagnostics.

The batch :func:`aggregate_fleet` answers "summarise these N records";
the SRE question is "what did the last 24 hours look like, and alert
me if a metric crossed a threshold." This module serves the second:

* :class:`StreamingFleetMonitor` — append-only buffer of
  per-episode observations. Stores the small
  :class:`~symbolu_robotics.bcvf_autonomous.analysis.episode.EpisodeSummary`
  (≈ a few KB) plus a per-predictor exclusion vector. The raw
  :class:`~symbolu_robotics.bcvf_autonomous.trust_diagnostics.TrustShapedEpisodeRecord`
  (potentially MB) is **not** retained — that's the whole point of
  streaming.
* :class:`WindowedFleetSummary` — a :class:`FleetSummary` plus the
  ``[window_start, window_end]`` it covers and an episode count.
* :class:`AlertRule` / :class:`Alert` — threshold rules evaluated
  against the windowed summary; fires when the metric crosses the
  rule's bound and the window has at least ``min_episodes``.

Concurrency: the monitor is intended for single-writer use (one
ingest thread). Multi-process fleet ingest fans observations into
one monitor via :meth:`observe_summary` — the fast path that
accepts a pre-summarised episode + exclusion vector, so a
distributed deployment can pre-summarise on each vehicle and ship
small payloads to a central monitor.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Deque, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ..trust_diagnostics import TrustShapedEpisodeRecord
from .episode import EpisodeSummary, summarize_episode
from .fleet import FleetSummary, _percentiles
from .flips import V2StateFlip
from .near_veto import NearVeto


# --------------------------------------------------------------------------- #
# Internal observation record
# --------------------------------------------------------------------------- #


@dataclass
class _Observation:
    """One stored observation: timestamp + summary + exclusion vector.

    The exclusion vector ``per_predictor_excluded_ever`` is the only
    field that can't be reconstructed from :class:`EpisodeSummary`
    alone — :func:`aggregate_fleet` derives it from the raw record's
    ``per_step_is_excluded`` array. We extract it once at observation
    time so the streaming monitor never needs to keep the raw record.
    """

    observed_at: datetime
    summary: EpisodeSummary
    per_predictor_excluded_ever: np.ndarray   # (M,) int 0/1


# --------------------------------------------------------------------------- #
# Public dataclasses
# --------------------------------------------------------------------------- #


@dataclass
class WindowedFleetSummary:
    """A :class:`FleetSummary` over a specific ``[start, end]`` window."""

    fleet: FleetSummary
    window_start: datetime
    window_end: datetime
    n_observed_in_window: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fleet": self.fleet.to_dict(),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "n_observed_in_window": int(self.n_observed_in_window),
        }


@dataclass(frozen=True)
class AlertRule:
    """Threshold rule on a metric of a windowed summary.

    ``metric`` is a dotted-path key into :meth:`WindowedFleetSummary.to_dict`'s
    ``"fleet"`` block — e.g. ``"argmax_flips_per_step.p95"``,
    ``"deadband_fired_rate"``, ``"v2_engaged_fraction.mean"``. The
    monitor walks the path; a missing key raises :class:`KeyError` so
    a typo'd rule fails loudly rather than silently never firing.

    ``direction``:

    * ``"above"`` (default) — fire when ``observed > threshold``.
    * ``"below"`` — fire when ``observed < threshold``.

    ``min_episodes`` suppresses the rule until the window has at
    least that many episodes — guards against alerts on a single
    point estimate.
    """

    name: str
    metric: str
    threshold: float
    direction: str = "above"
    min_episodes: int = 1

    def __post_init__(self) -> None:
        if self.direction not in ("above", "below"):
            raise ValueError(
                f"direction must be 'above' or 'below'; got {self.direction!r}"
            )
        if self.min_episodes < 0:
            raise ValueError("min_episodes must be >= 0")


@dataclass(frozen=True)
class Alert:
    """One fired alert."""

    rule: AlertRule
    observed_value: float
    window_start: datetime
    window_end: datetime
    fired_at: datetime
    n_episodes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule.name,
            "metric": self.rule.metric,
            "threshold": float(self.rule.threshold),
            "direction": self.rule.direction,
            "observed_value": float(self.observed_value),
            "window_start": self.window_start.isoformat(),
            "window_end": self.window_end.isoformat(),
            "fired_at": self.fired_at.isoformat(),
            "n_episodes": int(self.n_episodes),
        }


# --------------------------------------------------------------------------- #
# StreamingFleetMonitor
# --------------------------------------------------------------------------- #


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _per_predictor_excluded_ever(record: TrustShapedEpisodeRecord) -> np.ndarray:
    if record.per_step_is_excluded.size == 0:
        return np.zeros(record.M, dtype=np.int64)
    return record.per_step_is_excluded.any(axis=0).astype(np.int64)


class StreamingFleetMonitor:
    """Online fleet monitor with rolling-window summaries + alerts.

    Args:
        retention: optional max age for stored observations. On every
            :meth:`observe_episode` / :meth:`observe_summary` call,
            observations older than ``now - retention`` are evicted.
            ``None`` disables age-based eviction.
        max_retained: optional maximum number of stored observations.
            On overflow, the oldest observation is evicted (FIFO).
            ``None`` disables count-based eviction.
        clock: callable returning the current :class:`datetime`.
            Defaults to UTC ``now``. Tests inject a fake clock.
    """

    def __init__(
        self,
        retention: Optional[timedelta] = None,
        max_retained: Optional[int] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if retention is not None and retention.total_seconds() <= 0:
            raise ValueError("retention must be a positive timedelta")
        if max_retained is not None and max_retained <= 0:
            raise ValueError("max_retained must be > 0")
        self._retention = retention
        self._max_retained = max_retained
        self._clock: Callable[[], datetime] = clock or _utc_now
        self._observations: Deque[_Observation] = deque()
        # Track the largest M seen so per-predictor aggregation has
        # a stable width. Per-predictor vectors are right-padded /
        # truncated when shorter / longer.
        self._fleet_M: int = 0
        # Max ``observed_at`` across stored observations, tracked
        # separately so out-of-order ingest (network jitter is typical
        # in production fleets) doesn't cause ``latest_observed_at``
        # to return a wall-clock-stale timestamp. Updated on every
        # ``_append`` and recomputed on every eviction.
        self._max_observed_at: Optional[datetime] = None

    # ----- ingestion ----- #

    def observe_episode(
        self,
        record: TrustShapedEpisodeRecord,
        episode_id: str = "",
        classification: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        near_veto_fraction: float = 0.7,
        observed_at: Optional[datetime] = None,
    ) -> EpisodeSummary:
        """Summarise + store one raw episode record.

        Returns the :class:`EpisodeSummary` so the caller can inspect
        / persist the per-episode roll-up without re-summarising.
        """
        ts = observed_at or self._clock()
        summary = summarize_episode(
            record,
            episode_id=episode_id,
            classification=classification,
            near_veto_fraction=near_veto_fraction,
            metadata=metadata,
        )
        excl = _per_predictor_excluded_ever(record)
        self._append(_Observation(
            observed_at=ts, summary=summary, per_predictor_excluded_ever=excl,
        ))
        return summary

    def observe_summary(
        self,
        summary: EpisodeSummary,
        per_predictor_excluded_ever: Sequence[int],
        observed_at: Optional[datetime] = None,
    ) -> None:
        """Fast-path ingest for a pre-summarised episode.

        Production deployments summarise on the vehicle (or in a
        regional aggregator) and ship the small payload to the
        central monitor; this method accepts that payload directly.
        """
        ts = observed_at or self._clock()
        excl = np.asarray(per_predictor_excluded_ever, dtype=np.int64)
        if excl.ndim != 1:
            raise ValueError(
                f"per_predictor_excluded_ever must be 1-D; got shape {excl.shape}"
            )
        if excl.shape[0] != summary.M:
            raise ValueError(
                f"per_predictor_excluded_ever length {excl.shape[0]} "
                f"!= summary.M ({summary.M})"
            )
        self._append(_Observation(
            observed_at=ts, summary=summary, per_predictor_excluded_ever=excl,
        ))

    def _append(self, obs: _Observation) -> None:
        self._observations.append(obs)
        self._fleet_M = max(self._fleet_M, obs.summary.M)
        if (self._max_observed_at is None
                or obs.observed_at > self._max_observed_at):
            self._max_observed_at = obs.observed_at
        self._evict_if_needed(now=obs.observed_at)

    # ----- eviction ----- #

    def _evict_if_needed(self, now: datetime) -> None:
        evicted: List[_Observation] = []
        if self._retention is not None:
            cutoff = now - self._retention
            while self._observations and self._observations[0].observed_at < cutoff:
                evicted.append(self._observations.popleft())
        if self._max_retained is not None:
            while len(self._observations) > self._max_retained:
                evicted.append(self._observations.popleft())
        if not evicted:
            return
        # ``_max_observed_at`` may have referred to one of the evicted
        # observations (out-of-order ingest can park the max in the
        # *insertion-oldest* slot, which the FIFO eviction pops first).
        # Refresh only when an eviction actually happened — and only
        # when the pre-eviction max was among the evicted set, so the
        # common monotone-ingest path stays O(1) per insert.
        if not self._observations:
            self._max_observed_at = None
            return
        evicted_max = max(o.observed_at for o in evicted)
        if (self._max_observed_at is None
                or evicted_max >= self._max_observed_at):
            self._max_observed_at = max(
                o.observed_at for o in self._observations
            )

    def prune(self, older_than: datetime) -> int:
        """Evict observations strictly older than ``older_than``.

        Returns the number of observations evicted. Callers driving
        their own retention policy (e.g. mirroring an external store)
        use this directly.
        """
        before = len(self._observations)
        while self._observations and self._observations[0].observed_at < older_than:
            self._observations.popleft()
        return before - len(self._observations)

    # ----- introspection ----- #

    @property
    def n_observed(self) -> int:
        return len(self._observations)

    @property
    def latest_observed_at(self) -> Optional[datetime]:
        """Largest ``observed_at`` across stored observations.

        Returned by-timestamp rather than by-insertion-order so an
        out-of-order ingest (one episode arrives late after a newer
        one was already observed — typical of network-jittered
        production fleet uploads) doesn't cause the rolling window
        in ``summary(...)`` to anchor on a stale wall-clock time and
        silently drop the genuinely-newest data.
        """
        return self._max_observed_at

    @property
    def earliest_observed_at(self) -> Optional[datetime]:
        if not self._observations:
            return None
        # Smallest observed_at across stored observations. Computed
        # from the buffer rather than tracked separately because
        # eviction prunes the *insertion-oldest* head, not necessarily
        # the *timestamp-oldest*; the value is informational and
        # cheap (deque length is bounded by retention/max_retained).
        return min(o.observed_at for o in self._observations)

    # ----- windowed summary ----- #

    def summary(
        self,
        window: Optional[timedelta] = None,
        now: Optional[datetime] = None,
    ) -> WindowedFleetSummary:
        """Return a :class:`WindowedFleetSummary` over ``[now - window, now]``.

        ``now`` defaults to the latest observation's timestamp (or
        the configured clock if no observations yet). ``window=None``
        returns the entire retained buffer (no time filter).

        The fleet aggregate matches what
        :func:`~symbolu_robotics.bcvf_autonomous.analysis.aggregate_fleet`
        would produce on the same episodes — the streaming monitor's
        invariant is *batch-parity within the window*.
        """
        end = now if now is not None else (
            self.latest_observed_at or self._clock()
        )
        if window is None:
            start = (
                self.earliest_observed_at
                if self.earliest_observed_at is not None else end
            )
            in_window = list(self._observations)
        else:
            if window.total_seconds() <= 0:
                raise ValueError("window must be a positive timedelta")
            start = end - window
            in_window = [
                obs for obs in self._observations
                if start <= obs.observed_at <= end
            ]

        fleet = self._aggregate(in_window)
        return WindowedFleetSummary(
            fleet=fleet,
            window_start=start,
            window_end=end,
            n_observed_in_window=len(in_window),
        )

    def _aggregate(self, observations: Sequence[_Observation]) -> FleetSummary:
        n = len(observations)
        if n == 0:
            return FleetSummary(
                n_episodes=0,
                n_total_steps=0,
                classification_counts={},
                argmax_flips_per_step={
                    "mean": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0,
                },
                v2_engaged_fraction=None,
                deadband_fired_rate=0.0,
                per_predictor_excluded_rate=[],
                near_vetoes=[],
                v2_state_flips=[],
                episodes=[],
            )

        M = max(obs.summary.M for obs in observations)
        flip_rates: List[float] = []
        engaged_fractions: List[float] = []
        deadband_rates: List[float] = []
        excluded_counts = np.zeros(M, dtype=np.int64)
        n_total_steps = 0
        near_vetoes_all: List[NearVeto] = []
        v2_flips_all: List[V2StateFlip] = []
        episode_summaries: List[EpisodeSummary] = []
        cls_counts: Counter = Counter()

        for obs in observations:
            ep = obs.summary
            episode_summaries.append(ep)
            n_total_steps += ep.n_steps
            if ep.n_steps > 0:
                flip_rates.append(ep.n_argmax_flips / ep.n_steps)
            if ep.fraction_engaged is not None:
                engaged_fractions.append(ep.fraction_engaged)
            deadband_rates.append(ep.deadband_fired_rate)
            if ep.classification is not None:
                cls_counts[ep.classification] += 1
            excl = obs.per_predictor_excluded_ever
            if excl.shape[0] <= M:
                excluded_counts[: excl.shape[0]] += excl
            near_vetoes_all.extend(ep.near_vetoes)
            v2_flips_all.extend(ep.v2_state_flips)

        argmax_stats = _percentiles(np.asarray(flip_rates, dtype=np.float64))
        v2_stats = (
            None if not engaged_fractions
            else _percentiles(np.asarray(engaged_fractions, dtype=np.float64))
        )
        deadband_rate_mean = (
            float(np.mean(deadband_rates)) if deadband_rates else 0.0
        )
        per_predictor_rate = [float(c / n) for c in excluded_counts.tolist()]

        return FleetSummary(
            n_episodes=n,
            n_total_steps=n_total_steps,
            classification_counts=dict(cls_counts),
            argmax_flips_per_step=argmax_stats,
            v2_engaged_fraction=v2_stats,
            deadband_fired_rate=deadband_rate_mean,
            per_predictor_excluded_rate=per_predictor_rate,
            near_vetoes=near_vetoes_all,
            v2_state_flips=v2_flips_all,
            episodes=episode_summaries,
        )

    # ----- alerts ----- #

    def evaluate_alerts(
        self,
        rules: Sequence[AlertRule],
        window: timedelta,
        now: Optional[datetime] = None,
    ) -> List[Alert]:
        """Evaluate threshold rules against the rolling window.

        Returns the list of fired alerts (rules whose metric crossed
        the threshold in the configured direction, with at least
        ``rule.min_episodes`` episodes in the window). Rules that
        don't fire are simply absent from the return; non-firing is
        the success case for an SRE pipeline.
        """
        ws = self.summary(window=window, now=now)
        fired_at = self._clock()
        out: List[Alert] = []
        # Use the to_dict view so the metric path is the same as the
        # one a downstream JSON consumer (Grafana, Prometheus textfile
        # exporter, alertmanager rule) would index.
        view = ws.fleet.to_dict()
        for rule in rules:
            if ws.n_observed_in_window < rule.min_episodes:
                continue
            value = _resolve_metric_path(view, rule.metric)
            if value is None:
                # The metric path resolved to None (e.g. v2_engaged_fraction
                # when V2 was never enabled in the window). A rule that
                # references such a metric simply doesn't fire — it's a
                # data-availability issue, not an alert condition.
                continue
            crossed = (
                (rule.direction == "above" and value > rule.threshold)
                or (rule.direction == "below" and value < rule.threshold)
            )
            if crossed:
                out.append(Alert(
                    rule=rule,
                    observed_value=float(value),
                    window_start=ws.window_start,
                    window_end=ws.window_end,
                    fired_at=fired_at,
                    n_episodes=ws.n_observed_in_window,
                ))
        return out


def _resolve_metric_path(view: Dict[str, Any], path: str) -> Optional[float]:
    """Walk a dotted-path metric key; raise KeyError on miss.

    Returns the resolved numeric value, or ``None`` if the path lands
    on a ``None`` (legitimately-missing metric like
    ``v2_engaged_fraction`` when V2 was never enabled).
    """
    cursor: Any = view
    for part in path.split("."):
        if cursor is None:
            return None
        if not isinstance(cursor, dict) or part not in cursor:
            raise KeyError(
                f"metric path {path!r} does not resolve in fleet summary"
            )
        cursor = cursor[part]
    if cursor is None:
        return None
    # ``bool`` is a subclass of ``int`` — reject it explicitly so a
    # boolean field added to FleetSummary (e.g. a future
    # ``meets_certification_floor`` flag) doesn't silently become a
    # numeric metric a threshold rule fires on as if it were a rate.
    if isinstance(cursor, bool):
        raise TypeError(
            f"metric path {path!r} resolves to bool; alert rules "
            "require a numeric metric"
        )
    if not isinstance(cursor, (int, float)):
        raise TypeError(
            f"metric path {path!r} resolves to non-numeric "
            f"{type(cursor).__name__}"
        )
    return float(cursor)

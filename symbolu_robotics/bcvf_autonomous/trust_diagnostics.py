"""Per-step trust diagnostics — autonomous analog of BCVF LLM's
``TrustShapedDecodeResult``.

The trust kernel and consumer pattern already compute everything
needed at every planning tick (per-predictor cost, EMA mean, EMA
std, deadband activations, exclusion state, weights). What was
missing was a typed record that *persists* those quantities tick by
tick and survives into a structured episode artifact, so an
incident replay can answer "why was predictor M3 down-weighted at
tick 142?" without rerunning the simulation.

Design contracts:

* ``TrustStepRecord`` is the per-tick record. It's built directly
  from a ``TrustWeightResult`` and aggregates across the ``K``
  rollouts in that tick — caller-side aggregation strategy is
  pluggable (``mean``, ``argmin_total``, ``manual_index``).
* ``TrustShapedEpisodeRecord`` is the episode-level container. It
  stacks the per-tick records into ``(T, M)`` arrays and keeps the
  raw record list for cases where per-tick metadata matters.
* The recorder is intentionally separate from the planner / runner
  so non-MPPI consumers of ``TrustWeightComputer`` can record their
  own diagnostics without depending on the rest of the planner
  stack.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

from .trust import TrustWeightResult


class RolloutAggregation(str, Enum):
    """How to collapse a ``(K, M)`` weight/cost matrix to a ``(M,)`` record."""

    MEAN = "mean"
    """Mean across the K rollouts — population view of trust."""

    ARGMIN_TOTAL = "argmin_total"
    """Pick the rollout with the smallest summed per-predictor cost.

    Approximates "which rollout did the planner pick" without a
    perf-cost handshake; useful when the recorder lives outside
    the planner."""


@dataclass
class TrustStepRecord:
    """Per-planning-tick trust diagnostic record."""

    step_index: int
    aggregation: RolloutAggregation
    weights: np.ndarray              # (M,) tick-aggregated trust
    per_predictor_cost: np.ndarray   # (M,) tick-aggregated raw BCVF cost
    bcvf_total: float                # tick-aggregated BCVF total
    residual: Optional[np.ndarray]   # (M,) cost - ema_mean, or None
    ema_mean: Optional[np.ndarray]   # (M,) post-update EMA mean
    ema_std: Optional[np.ndarray]    # (M,) post-update EMA std
    deadband_active_count: int       # K-side count of deadband fallbacks
    deadband_fired: bool             # whether this tick's chosen rollout fell in deadband
    is_excluded: Optional[np.ndarray]  # (M,) bool exclusion state, or None
    gate_activations: int            # diagnostic — only set if recorder has access
    # §14a V2 state — None if V2 is disabled. "uniform" = softmin
    # bypassed and weights forced to 1/M; "engaged" = V1 pipeline ran.
    v2_state: Optional[str] = None
    v2_signal: Optional[float] = None
    # §6.6a exclusion counters (snapshot). None when exclusion is
    # disabled. Used by analysis.find_near_vetoes to detect predictors
    # that came close to being excluded but never crossed the threshold.
    consec_suspect: Optional[np.ndarray] = None  # (M,) int
    consec_ok: Optional[np.ndarray] = None       # (M,) int
    exclusion_T: Optional[int] = None            # T_exclude in effect
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrustShapedEpisodeRecord:
    """Episode-level container of per-tick trust diagnostics.

    Stacks every ``TrustStepRecord`` into ``(T, M)`` arrays. Mirrors
    BCVF LLM's ``TrustShapedDecodeResult``: per-step weights, costs,
    residuals, BCVF totals, gate activations, and §14a V2 state.
    """

    n_steps: int
    M: int
    aggregation: RolloutAggregation
    per_step_weights: np.ndarray         # (T, M)
    per_step_costs: np.ndarray           # (T, M)
    per_step_residuals: np.ndarray       # (T, M) — zeros where ema disabled
    per_step_ema_mean: np.ndarray        # (T, M) — zeros where ema disabled
    per_step_ema_std: np.ndarray         # (T, M) — zeros where deadband disabled
    per_step_bcvf_total: np.ndarray      # (T,)
    per_step_deadband_active_count: np.ndarray  # (T,) int
    per_step_deadband_fired: np.ndarray  # (T,) bool
    per_step_is_excluded: np.ndarray     # (T, M) bool
    per_step_gate_activations: np.ndarray  # (T,) int
    # §14a V2 state per tick. ``per_step_v2_state`` carries the string
    # state ("uniform" | "engaged") or "" when V2 was disabled at the
    # tick. ``per_step_v2_signal`` carries the engage-signal value or
    # NaN when V2 was disabled.
    per_step_v2_state: List[str] = field(default_factory=list)
    per_step_v2_signal: np.ndarray = field(
        default_factory=lambda: np.zeros(0, dtype=np.float64)
    )
    # §6.6a exclusion counters per tick. -1 sentinel where exclusion
    # was disabled at the tick (so post-hoc tools can distinguish
    # "counter was zero" from "counter was unavailable").
    per_step_consec_suspect: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0), dtype=np.int64)
    )
    per_step_consec_ok: np.ndarray = field(
        default_factory=lambda: np.zeros((0, 0), dtype=np.int64)
    )
    exclusion_T: Optional[int] = None
    records: List[TrustStepRecord] = field(repr=False, default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Plain-dict view for JSON serialization."""
        return {
            "n_steps": self.n_steps,
            "M": self.M,
            "aggregation": self.aggregation.value,
            "per_step_weights": self.per_step_weights.tolist(),
            "per_step_costs": self.per_step_costs.tolist(),
            "per_step_residuals": self.per_step_residuals.tolist(),
            "per_step_ema_mean": self.per_step_ema_mean.tolist(),
            "per_step_ema_std": self.per_step_ema_std.tolist(),
            "per_step_bcvf_total": self.per_step_bcvf_total.tolist(),
            "per_step_deadband_active_count": (
                self.per_step_deadband_active_count.tolist()
            ),
            "per_step_deadband_fired": self.per_step_deadband_fired.tolist(),
            "per_step_is_excluded": self.per_step_is_excluded.tolist(),
            "per_step_gate_activations": (
                self.per_step_gate_activations.tolist()
            ),
            "per_step_v2_state": list(self.per_step_v2_state),
            "per_step_v2_signal": self.per_step_v2_signal.tolist(),
            "per_step_consec_suspect": self.per_step_consec_suspect.tolist(),
            "per_step_consec_ok": self.per_step_consec_ok.tolist(),
            "exclusion_T": self.exclusion_T,
        }


class TrustDiagnosticsRecorder:
    """Stateful per-episode recorder for trust diagnostics.

    Usage:

        rec = TrustDiagnosticsRecorder(M=4)
        for tick in episode:
            result = trust_computer.compute(trajectories)  # TrustWeightResult
            rec.record(result, gate_activations=bcvf_result.gate_activation_count)
            ... use result.weights ...
        episode_record = rec.finalize()

    The ``aggregation`` keyword controls how each tick's ``(K, M)``
    weight matrix is collapsed into a ``(M,)`` per-step record:

      * ``MEAN`` (default) — weight/cost rows averaged across rollouts.
      * ``ARGMIN_TOTAL`` — use the rollout with the lowest summed
        per-predictor cost (a stand-in for "the rollout the planner
        chose"). Falls back to ``MEAN`` if every rollout's cost is
        identical.
    """

    def __init__(
        self,
        M: int,
        aggregation: RolloutAggregation = RolloutAggregation.MEAN,
    ) -> None:
        if M < 1:
            raise ValueError(f"M must be >= 1; got {M}")
        self._M = int(M)
        self._aggregation = aggregation
        self._records: List[TrustStepRecord] = []
        self._step_index = 0

    def reset(self) -> None:
        self._records = []
        self._step_index = 0

    @property
    def M(self) -> int:
        return self._M

    @property
    def n_steps(self) -> int:
        return len(self._records)

    def record(
        self,
        result: TrustWeightResult,
        gate_activations: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TrustStepRecord:
        """Append a ``TrustStepRecord`` for one ``TrustWeightComputer.compute()`` call."""
        weights = np.asarray(result.weights, dtype=np.float64)
        per_pred = np.asarray(result.per_pred_cost, dtype=np.float64)
        if weights.ndim != 2 or weights.shape[1] != self._M:
            raise ValueError(
                f"weights must have shape (K, {self._M}); got {weights.shape}"
            )
        if per_pred.shape != weights.shape:
            raise ValueError(
                f"per_pred_cost must match weights shape; "
                f"{per_pred.shape} vs {weights.shape}"
            )

        chosen_idx = self._select_rollout(per_pred)
        if self._aggregation == RolloutAggregation.MEAN:
            agg_weights = weights.mean(axis=0)
            agg_cost = per_pred.mean(axis=0)
        else:
            agg_weights = weights[chosen_idx]
            agg_cost = per_pred[chosen_idx]

        bcvf_total_arr = np.asarray(result.bcvf_total, dtype=np.float64)
        bcvf_total = (
            float(bcvf_total_arr.mean()) if bcvf_total_arr.size > 0 else 0.0
        )

        ema_mean = (
            None if result.ema_mean is None
            else np.asarray(result.ema_mean, dtype=np.float64).copy()
        )
        ema_std = (
            None if result.ema_std is None
            else np.asarray(result.ema_std, dtype=np.float64).copy()
        )
        # Residual must be computed against the pre-update EMA — that's
        # the value the trust shaper actually used to form the deadband
        # / softmin signal this tick. Falling back to post-update EMA
        # when pre-update isn't supplied keeps backward compat with
        # callers building TrustWeightResult by hand, but logs a slight
        # off-by-one EMA step in that case.
        ema_pre = getattr(result, "ema_mean_pre_update", None)
        residual = None
        if ema_pre is not None:
            residual = agg_cost - np.asarray(ema_pre, dtype=np.float64)
        elif ema_mean is not None:
            residual = agg_cost - ema_mean

        deadband_count = int(getattr(result, "deadband_active_count", 0) or 0)
        deadband_fired = False
        # The TrustWeightComputer fires the deadband per-rollout, so we
        # cannot recover the exact mask here without the planner's
        # cooperation — we use a proxy: more than half the rollouts
        # falling in the deadband ⇒ "this tick was dominated by the
        # deadband fallback."
        n_rollouts = weights.shape[0]
        if n_rollouts > 0 and deadband_count > n_rollouts // 2:
            deadband_fired = True

        is_excluded = (
            None if result.is_excluded is None
            else np.asarray(result.is_excluded, dtype=bool).copy()
        )

        consec_suspect = (
            None if getattr(result, "consec_suspect", None) is None
            else np.asarray(result.consec_suspect, dtype=np.int64).copy()
        )
        consec_ok = (
            None if getattr(result, "consec_ok", None) is None
            else np.asarray(result.consec_ok, dtype=np.int64).copy()
        )
        record = TrustStepRecord(
            step_index=self._step_index,
            aggregation=self._aggregation,
            weights=agg_weights,
            per_predictor_cost=agg_cost,
            bcvf_total=bcvf_total,
            residual=residual,
            ema_mean=ema_mean,
            ema_std=ema_std,
            deadband_active_count=deadband_count,
            deadband_fired=deadband_fired,
            is_excluded=is_excluded,
            gate_activations=int(gate_activations),
            v2_state=getattr(result, "v2_state", None),
            v2_signal=getattr(result, "v2_signal", None),
            consec_suspect=consec_suspect,
            consec_ok=consec_ok,
            exclusion_T=getattr(result, "exclusion_T", None),
            metadata=dict(metadata or {}),
        )
        self._records.append(record)
        self._step_index += 1
        return record

    def finalize(self) -> TrustShapedEpisodeRecord:
        """Stack the recorded ticks into a ``TrustShapedEpisodeRecord``."""
        T = len(self._records)
        M = self._M
        zeros_TM = np.zeros((T, M), dtype=np.float64)
        if T == 0:
            return TrustShapedEpisodeRecord(
                n_steps=0,
                M=M,
                aggregation=self._aggregation,
                per_step_weights=zeros_TM,
                per_step_costs=zeros_TM,
                per_step_residuals=zeros_TM,
                per_step_ema_mean=zeros_TM,
                per_step_ema_std=zeros_TM,
                per_step_bcvf_total=np.zeros(0, dtype=np.float64),
                per_step_deadband_active_count=np.zeros(0, dtype=np.int64),
                per_step_deadband_fired=np.zeros(0, dtype=bool),
                per_step_is_excluded=np.zeros((0, M), dtype=bool),
                per_step_gate_activations=np.zeros(0, dtype=np.int64),
                per_step_v2_state=[],
                per_step_v2_signal=np.zeros(0, dtype=np.float64),
                per_step_consec_suspect=np.zeros((0, M), dtype=np.int64),
                per_step_consec_ok=np.zeros((0, M), dtype=np.int64),
                exclusion_T=None,
                records=[],
            )

        weights = np.stack([r.weights for r in self._records], axis=0)
        costs = np.stack(
            [r.per_predictor_cost for r in self._records], axis=0
        )
        bcvf_total = np.array(
            [r.bcvf_total for r in self._records], dtype=np.float64
        )
        deadband_count = np.array(
            [r.deadband_active_count for r in self._records], dtype=np.int64
        )
        deadband_fired = np.array(
            [r.deadband_fired for r in self._records], dtype=bool
        )
        gate_acts = np.array(
            [r.gate_activations for r in self._records], dtype=np.int64
        )

        residuals = np.stack(
            [
                r.residual if r.residual is not None else np.zeros(M)
                for r in self._records
            ],
            axis=0,
        )
        ema_mean = np.stack(
            [
                r.ema_mean if r.ema_mean is not None else np.zeros(M)
                for r in self._records
            ],
            axis=0,
        )
        ema_std = np.stack(
            [
                r.ema_std if r.ema_std is not None else np.zeros(M)
                for r in self._records
            ],
            axis=0,
        )
        is_excluded = np.stack(
            [
                r.is_excluded if r.is_excluded is not None
                else np.zeros(M, dtype=bool)
                for r in self._records
            ],
            axis=0,
        )

        v2_states = [r.v2_state if r.v2_state is not None else "" for r in self._records]
        v2_signals = np.array(
            [
                r.v2_signal if r.v2_signal is not None else float("nan")
                for r in self._records
            ],
            dtype=np.float64,
        )

        # -1 sentinel where exclusion was disabled at the tick.
        consec_suspect_stack = np.stack(
            [
                r.consec_suspect if r.consec_suspect is not None
                else np.full(M, -1, dtype=np.int64)
                for r in self._records
            ],
            axis=0,
        )
        consec_ok_stack = np.stack(
            [
                r.consec_ok if r.consec_ok is not None
                else np.full(M, -1, dtype=np.int64)
                for r in self._records
            ],
            axis=0,
        )
        exclusion_T_seen = next(
            (
                r.exclusion_T for r in self._records
                if r.exclusion_T is not None
            ),
            None,
        )

        return TrustShapedEpisodeRecord(
            n_steps=T,
            M=M,
            aggregation=self._aggregation,
            per_step_weights=weights,
            per_step_costs=costs,
            per_step_residuals=residuals,
            per_step_ema_mean=ema_mean,
            per_step_ema_std=ema_std,
            per_step_bcvf_total=bcvf_total,
            per_step_deadband_active_count=deadband_count,
            per_step_deadband_fired=deadband_fired,
            per_step_is_excluded=is_excluded,
            per_step_gate_activations=gate_acts,
            per_step_v2_state=v2_states,
            per_step_v2_signal=v2_signals,
            per_step_consec_suspect=consec_suspect_stack,
            per_step_consec_ok=consec_ok_stack,
            exclusion_T=exclusion_T_seen,
            records=list(self._records),
        )

    def _select_rollout(self, per_pred: np.ndarray) -> int:
        if (
            self._aggregation == RolloutAggregation.ARGMIN_TOTAL
            and per_pred.shape[0] > 0
        ):
            sums = per_pred.sum(axis=1)
            return int(np.argmin(sums))
        return 0

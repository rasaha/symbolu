"""Consumer-layer trust-weight computation (§5.1 / §6.3).

Extracts the consumer-layer trust-shaping pipeline — per-source EMA
mean centering, deadband gate, optional dynamic predictor exclusion,
and softmin — out of ``MPPIPlanner`` into a standalone, planner-
agnostic API. Any planner that produces ``M`` predictor trajectories
per candidate rollout can consume ``TrustWeightComputer.compute`` to
obtain a ``(K, M)`` trust-weight matrix and per-step diagnostics.

The BCVF kernel itself (``core.compute_bcvf_cost_batch``) is not
reimplemented here — the kernel stays in ``core.py`` and this module
calls into it. What lives here is the *consumer pattern*:
normalization, significance gate, exclusion, softmin.

Stateful. Per-episode state (EMA mean/variance, exclusion counters)
resets on ``.reset()``.

Design notes:

- Kept as a class, not a function, because the consumer pattern is
  genuinely stateful across planning steps (EMA tracks context
  baselines; exclusion tracks consecutive-suspect counts).
- The class is planner-agnostic: it consumes a ``(K, M, H, 3)`` tensor
  of predictor trajectories and returns trust weights + diagnostics.
  MPPI's weighted-consensus step is not inside this module — that
  belongs in the planner adapter (``MPPIPlanner`` is the reference
  adapter; see ``docs/experiments/phase_6_3_extraction.md`` for
  how to write additional adapters).
- Backward compatible with V1: a zero-configuration ``TrustWeightComputer``
  produces the same weights the V1 planner produced (uniform weights
  when ``lambda_c = 0``; raw softmin when ``ema_alpha = 0``; etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from .core import BCVFConfig, compute_bcvf_cost_batch


class ConsumerState(str, Enum):
    """Top-level state of the §14a V2 Schmitt-triggered consumer.

    ``UNIFORM`` — softmin disengaged; weights are 1/M for every
    rollout. The engage signal must rise above
    ``ConsumerV2Config.engage_threshold`` for ``T_engage`` consecutive
    ticks to transition to ``ENGAGED``.

    ``ENGAGED`` — V1 shaping pipeline runs (EMA centering, per-rollout
    deadband, softmin, optional exclusion). The engage signal must
    drop below ``ConsumerV2Config.disengage_threshold`` for
    ``T_disengage`` consecutive ticks to transition back to
    ``UNIFORM``.
    """

    UNIFORM = "uniform"
    ENGAGED = "engaged"


@dataclass
class ConsumerV2Config:
    """§14a V2 consumer pattern — Schmitt-triggered softmin.

    See ``CONSUMER_V2_DESIGN.md`` for the full motivation and
    threshold-selection rationale.

    Attributes:
        enabled: master switch. When False the consumer is exactly V1.
        engage_threshold: scalar threshold on the engage signal (default
            ``bcvf_total.mean()``). Engages shaping when the signal
            stays at or above this value for ``T_engage`` consecutive
            ticks.
        disengage_threshold: strictly less than ``engage_threshold``.
            Reverts to uniform when the signal stays at or below this
            value for ``T_disengage`` consecutive ticks. The
            hysteresis gap ``engage_threshold - disengage_threshold``
            kills chatter at the threshold boundary.
        T_engage: consecutive-tick count required to engage. Defaults
            to 3 (≈ 0.3 s at dt = 0.1 s).
        T_disengage: consecutive-tick count required to disengage.
            Defaults to 5 — slightly slower than engage so the safety
            mode stays active a bit longer once a real signal appears.
    """

    enabled: bool = False
    engage_threshold: float = 0.5
    disengage_threshold: float = 0.2
    T_engage: int = 3
    T_disengage: int = 5

    def __post_init__(self) -> None:
        if self.engage_threshold <= self.disengage_threshold:
            raise ValueError(
                f"engage_threshold ({self.engage_threshold}) must be "
                f"strictly greater than disengage_threshold "
                f"({self.disengage_threshold}) so the Schmitt trigger "
                f"has hysteresis"
            )
        if self.T_engage < 1 or self.T_disengage < 1:
            raise ValueError(
                f"T_engage and T_disengage must be >= 1; got "
                f"T_engage={self.T_engage}, T_disengage={self.T_disengage}"
            )


@dataclass
class TrustWeightResult:
    """Output of a single ``TrustWeightComputer.compute`` call.

    Shapes are per-batch (``K`` rollouts). ``bcvf_total`` and
    ``per_pred_cost`` are the raw kernel outputs before any consumer-
    layer processing; ``weights`` is the final trust distribution the
    caller should use for the consensus.

    ``ema_mean`` is the *post-update* EMA (the state at the end of
    this tick). ``ema_mean_pre_update`` is the EMA snapshot used to
    compute this tick's residual — the value the deadband and trust-
    softmin actually saw. Diagnostics that want the exact residual
    the shaper used must subtract from ``ema_mean_pre_update``, not
    ``ema_mean``.
    """

    weights: np.ndarray             # (K, M), rows sum to 1
    bcvf_total: np.ndarray          # (K,), diagnostic sum of pair costs
    per_pred_cost: np.ndarray       # (K, M), raw per-source cost
    ema_mean: Optional[np.ndarray]  # (M,) or None if ema_alpha = 0
    ema_std: Optional[np.ndarray]   # (M,) or None if deadband not active
    deadband_active_count: int      # # rollouts below deadband threshold
    is_excluded: Optional[np.ndarray]  # (M,) bool or None
    ema_mean_pre_update: Optional[np.ndarray] = None  # (M,) snapshot before update
    # §14a V2 Schmitt-triggered consumer diagnostics. None when V2 is
    # disabled (the default), so V1 callers see the same field set as
    # before.
    v2_state: Optional[str] = None        # "uniform" | "engaged" | None
    v2_signal: Optional[float] = None     # scalar engage signal this tick
    # §6.6a exclusion counters (snapshot). None when exclusion is
    # disabled. Surfaced for post-hoc near-veto analysis: a predictor
    # whose ``consec_suspect`` reaches a high fraction of T_exclude
    # without ever being excluded was a "near-miss" that a SOTIF
    # recall-triage tool wants to flag.
    consec_suspect: Optional[np.ndarray] = None  # (M,) int
    consec_ok: Optional[np.ndarray] = None       # (M,) int
    exclusion_T: Optional[int] = None            # T_exclude in effect


class TrustWeightComputer:
    """Stateful consumer-layer trust-weight computer.

    Wraps ``compute_bcvf_cost_batch`` with the autonomy-validated §5.1
    consumer pattern: per-source EMA mean centering, significance gate
    (deadband), optional §6.6a dynamic predictor exclusion, softmin.

    Usage (planner-agnostic):
        computer = TrustWeightComputer(bcvf_config)
        computer.set_ema_alpha(0.05)
        computer.set_deadband_k_sigma(2.0)
        for planning_step in episode:
            trajectories = my_planner.rollout_predictors(...)  # (K, M, H, 3)
            result = computer.compute(trajectories)
            weights = result.weights
            # ... use weights for consensus / voting / selection ...
        computer.reset()  # between episodes
    """

    def __init__(self, bcvf_config: BCVFConfig) -> None:
        self._bcvf_config = bcvf_config
        # Softmin temperature. τ_w = 1 matches V1.
        self._trust_temperature: float = 1.0
        # Level-2 adaptive normalization — disabled by default.
        self._ema_alpha: float = 0.0
        self._ema_mean: Optional[np.ndarray] = None
        # Solution-3 deadband gate — disabled by default.
        self._deadband_k_sigma: float = 0.0
        self._ema_var: Optional[np.ndarray] = None
        # §6.6a exclusion — disabled by default (rejected in §6.6a
        # decision gate; kept in codebase for §6.6b reopens).
        self._exclusion_enabled: bool = False
        self._exclusion_r: float = 1.5
        self._exclusion_T: int = 20
        self._exclusion_T_reinstate: int = 20
        self._consec_suspect: Optional[np.ndarray] = None
        self._consec_ok: Optional[np.ndarray] = None
        self._is_excluded: Optional[np.ndarray] = None
        # §14a V2 Schmitt-triggered consumer — disabled by default.
        # When enabled the engage signal (default: bcvf_total.mean())
        # gates the entire shaping pipeline: in UNIFORM state the
        # softmin is bypassed and weights are 1/M; in ENGAGED state
        # the V1 pipeline runs unchanged.
        self._v2_config: Optional[ConsumerV2Config] = None
        self._v2_state: ConsumerState = ConsumerState.UNIFORM
        self._v2_above_count: int = 0
        self._v2_below_count: int = 0

    # --- lifecycle ---

    def reset(self) -> None:
        """Clear per-episode state. Call between episodes."""
        self._ema_mean = None
        self._ema_var = None
        self._consec_suspect = None
        self._consec_ok = None
        self._is_excluded = None
        self._v2_state = ConsumerState.UNIFORM
        self._v2_above_count = 0
        self._v2_below_count = 0

    # --- setters ---

    def set_trust_temperature(self, tau: float) -> None:
        if tau <= 0.0:
            raise ValueError(f"trust_temperature must be > 0; got {tau}")
        self._trust_temperature = tau

    def set_ema_alpha(self, alpha: float) -> None:
        if alpha < 0.0 or alpha > 1.0:
            raise ValueError(f"ema_alpha must be in [0, 1]; got {alpha}")
        self._ema_alpha = alpha
        self._ema_mean = None
        self._ema_var = None

    def set_deadband_k_sigma(self, k_sigma: float) -> None:
        if k_sigma < 0.0:
            raise ValueError(f"deadband k_sigma must be >= 0; got {k_sigma}")
        self._deadband_k_sigma = k_sigma

    def set_v2_consumer(self, config: ConsumerV2Config) -> None:
        """Install or replace the §14a V2 consumer config.

        Resets the V2 state machine — calling mid-episode flushes
        the engage / disengage tick counters so the new config takes
        effect from a known starting state (UNIFORM).
        """
        self._v2_config = config
        self._v2_state = ConsumerState.UNIFORM
        self._v2_above_count = 0
        self._v2_below_count = 0

    @property
    def v2_state(self) -> ConsumerState:
        """Current §14a V2 state — UNIFORM or ENGAGED."""
        return self._v2_state

    def set_exclusion(
        self,
        enabled: bool,
        r: float = 1.5,
        T_exclude: int = 20,
        T_reinstate: int = 20,
    ) -> None:
        if r <= 1.0:
            raise ValueError(f"exclusion r must be > 1.0; got {r}")
        if T_exclude < 1 or T_reinstate < 1:
            raise ValueError(
                f"exclusion thresholds must be >= 1; got "
                f"T_exclude={T_exclude}, T_reinstate={T_reinstate}"
            )
        self._exclusion_enabled = bool(enabled)
        self._exclusion_r = float(r)
        self._exclusion_T = int(T_exclude)
        self._exclusion_T_reinstate = int(T_reinstate)
        self._consec_suspect = None
        self._consec_ok = None
        self._is_excluded = None

    # --- public compute ---

    def compute(self, trajectories: np.ndarray) -> TrustWeightResult:
        """Compute trust weights from ``(K, M, H, 3)`` predictor trajectories.

        When ``lambda_c == 0`` in the ``BCVFConfig``, returns uniform
        weights and zero ``bcvf_total`` — matches A0 baseline behavior
        without invoking the kernel.
        """
        if trajectories.ndim != 4 or trajectories.shape[-1] != 3:
            raise ValueError(
                f"trajectories must have shape (K, M, H, 3); got "
                f"{trajectories.shape}"
            )
        k_batch, num_models, horizon, _ = trajectories.shape
        c = self._bcvf_config

        if c.lambda_c <= 0.0:
            weights = np.full(
                (k_batch, num_models), 1.0 / num_models, dtype=np.float64
            )
            return TrustWeightResult(
                weights=weights,
                bcvf_total=np.zeros(k_batch, dtype=np.float64),
                per_pred_cost=np.zeros((k_batch, num_models), dtype=np.float64),
                ema_mean=None,
                ema_std=None,
                deadband_active_count=0,
                is_excluded=None,
            )

        # BCVF kernel (stays in core.py).
        trajectories_list = [
            [trajectories[k, m] for m in range(num_models)]
            for k in range(k_batch)
        ]
        bcvf_total, per_pred_cost = compute_bcvf_cost_batch(
            trajectories_list, c, return_per_predictor=True
        )

        # Level-2 EMA mean centering. Runs before the §14a V2 gate so
        # the EMA continues tracking the cost baseline even while V2
        # is in UNIFORM mode — V2 suspends shaping, not learning. The
        # canonical SOTIF case: a vehicle spends the first 30 ticks
        # below the engage threshold; when the signal crosses the
        # threshold we want the deadband / softmin to start with a
        # warm baseline, not a cold start that cripples the first
        # ENGAGED tick. (See CONSUMER_V2_DESIGN.md §2.)
        ema_mean_pre_update: Optional[np.ndarray] = None
        if self._ema_alpha > 0.0:
            step_mean = per_pred_cost.mean(axis=0)
            if self._ema_mean is None:
                self._ema_mean = step_mean.copy()
                if self._deadband_k_sigma > 0.0:
                    self._ema_var = per_pred_cost.var(axis=0).copy()
            # Snapshot the EMA before the update — this is the value
            # used to form the residual that drives the deadband and
            # softmin. Diagnostics consumers want this snapshot, not
            # the post-update EMA.
            ema_mean_pre_update = self._ema_mean.copy()
            pred_signal = per_pred_cost - self._ema_mean[np.newaxis, :]
            a = self._ema_alpha
            if self._deadband_k_sigma > 0.0:
                resid_sq = (pred_signal ** 2).mean(axis=0)
                self._ema_var = a * resid_sq + (1.0 - a) * self._ema_var
            self._ema_mean = a * step_mean + (1.0 - a) * self._ema_mean
        else:
            pred_signal = per_pred_cost

        # §14a V2 Schmitt-trigger gate. When enabled, the top-level
        # state machine decides whether the V1 *shaping* (deadband +
        # softmin + exclusion) runs at all. EMA learning above
        # already happened.
        v2_signal: Optional[float] = None
        v2_state_view: Optional[str] = None
        if self._v2_config is not None and self._v2_config.enabled:
            v2_signal = (
                float(bcvf_total.mean()) if bcvf_total.size > 0 else 0.0
            )
            self._update_v2_state(v2_signal)
            v2_state_view = self._v2_state.value
            if self._v2_state == ConsumerState.UNIFORM:
                weights = np.full(
                    (k_batch, num_models),
                    1.0 / num_models,
                    dtype=np.float64,
                )
                return TrustWeightResult(
                    weights=weights,
                    bcvf_total=bcvf_total,
                    per_pred_cost=per_pred_cost,
                    ema_mean=(
                        self._ema_mean.copy()
                        if self._ema_mean is not None else None
                    ),
                    ema_std=None,
                    deadband_active_count=0,
                    is_excluded=(
                        self._is_excluded.copy()
                        if self._is_excluded is not None else None
                    ),
                    ema_mean_pre_update=ema_mean_pre_update,
                    v2_state=v2_state_view,
                    v2_signal=v2_signal,
                    consec_suspect=(
                        self._consec_suspect.copy()
                        if self._consec_suspect is not None else None
                    ),
                    consec_ok=(
                        self._consec_ok.copy()
                        if self._consec_ok is not None else None
                    ),
                    exclusion_T=(
                        int(self._exclusion_T)
                        if self._exclusion_enabled else None
                    ),
                )

        # Softmin (per-rollout min-shifted).
        tau_w = max(self._trust_temperature, 1e-9)
        shifted = pred_signal - pred_signal.min(axis=1, keepdims=True)
        arg = np.clip(-shifted / tau_w, -50.0, 50.0)
        raw = np.exp(arg)
        weights = raw / raw.sum(axis=1, keepdims=True)

        # Deadband gate (Solution 3).
        deadband_active_count = 0
        ema_std_view: Optional[np.ndarray] = None
        if (
            self._deadband_k_sigma > 0.0
            and self._ema_alpha > 0.0
            and self._ema_var is not None
        ):
            eps = 1e-9
            ema_std = np.sqrt(self._ema_var) + eps
            ema_std_view = ema_std.copy()
            z = np.abs(pred_signal) / ema_std[np.newaxis, :]
            max_abs_z = z.max(axis=1)
            insignificant = max_abs_z < self._deadband_k_sigma
            deadband_active_count = int(np.sum(insignificant))
            if np.any(insignificant):
                uniform = np.full(
                    (num_models,), 1.0 / num_models, dtype=np.float64
                )
                weights[insignificant] = uniform

        # §6.6a dynamic predictor exclusion.
        if self._exclusion_enabled:
            if self._consec_suspect is None:
                self._consec_suspect = np.zeros(num_models, dtype=np.int64)
                self._consec_ok = np.zeros(num_models, dtype=np.int64)
                self._is_excluded = np.zeros(num_models, dtype=bool)
            m = per_pred_cost.mean(axis=0)
            m_min = float(m.min())
            if m_min > 1e-12:
                suspect_mask = m > self._exclusion_r * m_min
            else:
                suspect_mask = np.zeros(num_models, dtype=bool)
            self._consec_suspect[suspect_mask] += 1
            self._consec_suspect[~suspect_mask] = 0
            self._consec_ok[~suspect_mask] += 1
            self._consec_ok[suspect_mask] = 0
            newly_excluded = self._consec_suspect >= self._exclusion_T
            newly_ok = self._is_excluded & (
                self._consec_ok >= self._exclusion_T_reinstate
            )
            self._is_excluded = np.where(
                newly_ok, False, self._is_excluded | newly_excluded
            )
            if self._is_excluded.any() and not self._is_excluded.all():
                weights[:, self._is_excluded] = 0.0
                row_sum = weights.sum(axis=1, keepdims=True)
                weights = weights / np.where(row_sum > 0, row_sum, 1.0)

        return TrustWeightResult(
            weights=weights,
            bcvf_total=bcvf_total,
            per_pred_cost=per_pred_cost,
            ema_mean=self._ema_mean.copy() if self._ema_mean is not None else None,
            ema_std=ema_std_view,
            deadband_active_count=deadband_active_count,
            is_excluded=(
                self._is_excluded.copy() if self._is_excluded is not None else None
            ),
            ema_mean_pre_update=ema_mean_pre_update,
            v2_state=v2_state_view,
            v2_signal=v2_signal,
            consec_suspect=(
                self._consec_suspect.copy()
                if self._consec_suspect is not None else None
            ),
            consec_ok=(
                self._consec_ok.copy()
                if self._consec_ok is not None else None
            ),
            exclusion_T=(
                int(self._exclusion_T)
                if self._exclusion_enabled else None
            ),
        )

    # --- V2 state machine ---

    def _update_v2_state(self, signal: float) -> None:
        """Advance the §14a V2 Schmitt trigger by one tick.

        UNIFORM → ENGAGED when ``signal >= engage_threshold`` for
        ``T_engage`` consecutive ticks.
        ENGAGED → UNIFORM when ``signal <= disengage_threshold`` for
        ``T_disengage`` consecutive ticks.

        The two counters are reset on any tick that breaks the streak,
        and on every state transition, so half-counted streaks don't
        leak across boundaries.
        """
        cfg = self._v2_config
        if cfg is None:
            return
        if self._v2_state == ConsumerState.UNIFORM:
            if signal >= cfg.engage_threshold:
                self._v2_above_count += 1
                if self._v2_above_count >= cfg.T_engage:
                    self._v2_state = ConsumerState.ENGAGED
                    self._v2_above_count = 0
                    self._v2_below_count = 0
            else:
                self._v2_above_count = 0
        else:  # ENGAGED
            if signal <= cfg.disengage_threshold:
                self._v2_below_count += 1
                if self._v2_below_count >= cfg.T_disengage:
                    self._v2_state = ConsumerState.UNIFORM
                    self._v2_above_count = 0
                    self._v2_below_count = 0
            else:
                self._v2_below_count = 0

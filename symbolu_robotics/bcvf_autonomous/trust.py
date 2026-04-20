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
from typing import Optional

import numpy as np

from .core import BCVFConfig, compute_bcvf_cost_batch


@dataclass
class TrustWeightResult:
    """Output of a single ``TrustWeightComputer.compute`` call.

    Shapes are per-batch (``K`` rollouts). ``bcvf_total`` and
    ``per_pred_cost`` are the raw kernel outputs before any consumer-
    layer processing; ``weights`` is the final trust distribution the
    caller should use for the consensus.
    """

    weights: np.ndarray             # (K, M), rows sum to 1
    bcvf_total: np.ndarray          # (K,), diagnostic sum of pair costs
    per_pred_cost: np.ndarray       # (K, M), raw per-source cost
    ema_mean: Optional[np.ndarray]  # (M,) or None if ema_alpha = 0
    ema_std: Optional[np.ndarray]   # (M,) or None if deadband not active
    deadband_active_count: int      # # rollouts below deadband threshold
    is_excluded: Optional[np.ndarray]  # (M,) bool or None


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

    # --- lifecycle ---

    def reset(self) -> None:
        """Clear per-episode state. Call between episodes."""
        self._ema_mean = None
        self._ema_var = None
        self._consec_suspect = None
        self._consec_ok = None
        self._is_excluded = None

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

        # Level-2 EMA mean centering.
        if self._ema_alpha > 0.0:
            step_mean = per_pred_cost.mean(axis=0)
            if self._ema_mean is None:
                self._ema_mean = step_mean.copy()
                if self._deadband_k_sigma > 0.0:
                    self._ema_var = per_pred_cost.var(axis=0).copy()
            pred_signal = per_pred_cost - self._ema_mean[np.newaxis, :]
            a = self._ema_alpha
            if self._deadband_k_sigma > 0.0:
                resid_sq = (pred_signal ** 2).mean(axis=0)
                self._ema_var = a * resid_sq + (1.0 - a) * self._ema_var
            self._ema_mean = a * step_mean + (1.0 - a) * self._ema_mean
        else:
            pred_signal = per_pred_cost

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
        )

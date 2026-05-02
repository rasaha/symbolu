"""Per-horizon-step decomposition of the BCVF kernel.

The single-trajectory ``compute_bcvf_cost`` in ``core`` reduces the
``gate * pseudo_huber(signal_norm)`` array to a scalar by summing
across the horizon. Several observables need that array *before*
the horizon-sum, both as a vector (per-step total cost) and decomposed
by predictor (per-step per-predictor cost). This module exposes those
intermediate quantities without duplicating the gate / huber math.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np

from ..core import (
    BCVFConfig,
    CostOrder,
    _enumerate_pairs,
    pseudo_huber,
    smooth_gate,
)
from ..manifold import body_frame_error_trajectory


@dataclass
class BCVFPerStepBreakdown:
    """Per-horizon-step breakdown of one (M, H, 3) trajectory tensor.

    Attributes:
        per_step_total: ``(H_signal,)`` — sum across pairs of
            ``gate * pseudo_huber(signal) * dt`` at each horizon step.
            ``H_signal`` depends on cost_order (``H`` for ZEROTH,
            ``H-1`` for FIRST, ``H-2`` for SECOND).
        per_step_per_pair: dict ``(i, j) -> (H_signal,)`` per-pair
            per-step cost.
        per_step_per_predictor: ``(M, H_signal)`` — same attribution
            convention as ``compute_bcvf_cost_batch`` (a pair's cost
            is added to both predictors in the pair).
        gate_activations_per_step: ``(H_signal,)`` int — number of
            pairs whose gate exceeds 0.5 at each step.
        signal_norm_max_per_step: ``(H_signal,)`` — max signal norm
            across pairs at each step (diagnostic).
    """

    per_step_total: np.ndarray
    per_step_per_pair: Dict[Tuple[int, int], np.ndarray]
    per_step_per_predictor: np.ndarray
    gate_activations_per_step: np.ndarray
    signal_norm_max_per_step: np.ndarray


def _stencil_lengths(horizon: int, cost_order: CostOrder) -> int:
    if cost_order == CostOrder.SECOND:
        return horizon - 2
    if cost_order == CostOrder.FIRST:
        return horizon - 1
    return horizon


def compute_bcvf_per_step(
    trajectories: np.ndarray, config: BCVFConfig
) -> BCVFPerStepBreakdown:
    """Compute the per-horizon-step BCVF breakdown for a single tick.

    Args:
        trajectories: ``(M, H, 3)`` predictor trajectories, ``M >= 2``,
            ``H >= 3``.
        config: ``BCVFConfig`` (cost_order / gate / huber / pairing
            knobs are honored exactly as in ``compute_bcvf_cost``).

    Returns:
        ``BCVFPerStepBreakdown``. ``sum(per_step_total) * 1`` reproduces
        ``compute_bcvf_cost(...).total_cost`` up to numerical roundoff
        (the ``* dt`` factor is already folded into ``per_step_total``).
    """
    if trajectories.ndim != 3 or trajectories.shape[-1] != 3:
        raise ValueError(
            f"trajectories must have shape (M, H, 3); got {trajectories.shape}"
        )
    num_models, horizon, _ = trajectories.shape
    if num_models < 2:
        raise ValueError(f"BCVF requires M >= 2; got M={num_models}")
    if horizon < 3:
        raise ValueError(f"BCVF requires H >= 3; got H={horizon}")

    pairs = _enumerate_pairs(
        num_models, config.use_anchor_pairing, config.anchor_index
    )

    h_signal = _stencil_lengths(horizon, config.cost_order)
    per_step_total = np.zeros(h_signal, dtype=np.float64)
    per_step_per_pair: Dict[Tuple[int, int], np.ndarray] = {}
    per_step_per_predictor = np.zeros(
        (num_models, h_signal), dtype=np.float64
    )
    gate_activations = np.zeros(h_signal, dtype=np.int64)
    signal_norm_max = np.zeros(h_signal, dtype=np.float64)

    w_sqrt = np.sqrt(np.asarray(config.weight_matrix, dtype=np.float64))

    for (i, j) in pairs:
        e = body_frame_error_trajectory(
            trajectories[i], trajectories[j], config.lever_arm
        )
        if config.cost_order == CostOrder.SECOND:
            signal = (e[2:] - 2.0 * e[1:-1] + e[:-2]) / (config.dt * config.dt)
            gate_input = e[1:-1]
        elif config.cost_order == CostOrder.FIRST:
            signal = (e[1:] - e[:-1]) / config.dt
            gate_input = 0.5 * (e[:-1] + e[1:])
        else:
            signal = e
            gate_input = e

        gate = smooth_gate(
            gate_input, config.gate_threshold, config.gate_beta, config.weight_matrix
        )
        signal_norms = np.linalg.norm(signal * w_sqrt, axis=-1)
        penalty = pseudo_huber(signal_norms, config.huber_delta)
        pair_per_step = gate * penalty * config.dt

        per_step_per_pair[(i, j)] = pair_per_step
        per_step_total += pair_per_step
        per_step_per_predictor[i] += pair_per_step
        per_step_per_predictor[j] += pair_per_step
        gate_activations += (gate > 0.5).astype(np.int64)
        signal_norm_max = np.maximum(signal_norm_max, signal_norms)

    return BCVFPerStepBreakdown(
        per_step_total=per_step_total,
        per_step_per_pair=per_step_per_pair,
        per_step_per_predictor=per_step_per_predictor,
        gate_activations_per_step=gate_activations,
        signal_norm_max_per_step=signal_norm_max,
    )


def stencil_align_to_signal(
    full_horizon_series: np.ndarray, cost_order: CostOrder
) -> np.ndarray:
    """Align an ``(H,)`` series to the BCVF per-step stencil length.

    For ``SECOND`` order returns the centered slice ``[1:-1]``; for
    ``FIRST`` the midpoint average ``0.5 * (s[:-1] + s[1:])``; for
    ``ZEROTH`` the input unchanged.
    """
    arr = np.asarray(full_horizon_series, dtype=np.float64)
    if arr.ndim != 1:
        raise ValueError(f"expected 1D series; got shape {arr.shape}")
    if cost_order == CostOrder.SECOND:
        if arr.shape[0] < 3:
            raise ValueError("SECOND-order alignment needs H >= 3")
        return arr[1:-1]
    if cost_order == CostOrder.FIRST:
        if arr.shape[0] < 2:
            raise ValueError("FIRST-order alignment needs H >= 2")
        return 0.5 * (arr[:-1] + arr[1:])
    return arr

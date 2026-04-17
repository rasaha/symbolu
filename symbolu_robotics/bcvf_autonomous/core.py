"""BCVF cost functional (V3.1 Sections 3.3-3.5, Lemma 1).

Implements the complete BCVF cost chain over a set of predictor
trajectories:

    disagreement -> velocity -> acceleration -> gate -> huber -> sum

All functions are pure. Trajectory inputs are NumPy float64 arrays
of shape (H, 3) with columns [x, y, theta]. No imports from other
``symbolu_robotics`` modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Tuple

import numpy as np

from .manifold import body_frame_error_trajectory


class CostOrder(IntEnum):
    """Which derivative order of disagreement the gate-Huber chain scores.

    V3.1 §E.5 / DESIGN.md §3B.10 ablation variants:

    * ``ZEROTH`` — penalize ``||e_ij||`` (magnitude of disagreement).
    * ``FIRST``  — penalize ``||v_ij||`` (velocity of disagreement).
    * ``SECOND`` — penalize ``||a_ij||`` (BCVF, the V3.1 innovation).
    """

    ZEROTH = 0
    FIRST = 1
    SECOND = 2


@dataclass
class BCVFConfig:
    """All tunable parameters for the BCVF cost functional."""

    lambda_c: float = 1.0
    gate_threshold: float = 0.1
    gate_beta: float = 200.0
    huber_delta: float = 0.5
    lever_arm: float = 2.5
    weight_matrix: np.ndarray = field(
        default_factory=lambda: np.ones(3, dtype=np.float64)
    )
    use_anchor_pairing: bool = True
    anchor_index: int = 0
    dt: float = 0.1
    cost_order: CostOrder = CostOrder.SECOND


@dataclass
class BCVFResult:
    """Detailed output from BCVF cost computation."""

    total_cost: float
    per_pair_costs: Dict[Tuple[int, int], float]
    max_acceleration_norm: float
    gate_activation_count: int


def compute_disagreement(
    traj_i: np.ndarray, traj_j: np.ndarray, lever_arm: float
) -> np.ndarray:
    """V3.1 Definition 1. Body-frame error over the full trajectory.

    Inputs: (H, 3). Output: (H, 3).
    """
    return body_frame_error_trajectory(traj_i, traj_j, lever_arm)


def compute_disagreement_velocity(
    disagreement: np.ndarray, dt: float
) -> np.ndarray:
    """V3.1 Definition 2. First finite difference of the disagreement.

    Input: (H, 3). Output: (H-1, 3).
    """
    return (disagreement[1:] - disagreement[:-1]) / dt


def compute_disagreement_acceleration(
    disagreement: np.ndarray, dt: float
) -> np.ndarray:
    """V3.1 Definition 3. Second finite difference of the disagreement.

    a(k) = [e(k+1) - 2 e(k) + e(k-1)] / dt^2

    Input: (H, 3). Output: (H-2, 3). This is the core innovation.
    """
    return (disagreement[2:] - 2.0 * disagreement[1:-1] + disagreement[:-2]) / (
        dt * dt
    )


def smooth_gate(
    disagreement: np.ndarray,
    threshold: float,
    beta: float,
    weight_matrix: np.ndarray,
) -> np.ndarray:
    """V3.1 Definition 4. Smooth gate in [0, 1].

    g(k) = sigmoid(beta * (||W_g^{1/2} e(k)|| - T))

    Input disagreement: (N, 3). Output: (N,).
    """
    w_sqrt = np.sqrt(np.asarray(weight_matrix, dtype=np.float64))
    weighted = disagreement * w_sqrt
    norm = np.linalg.norm(weighted, axis=-1)
    arg = beta * (norm - threshold)
    # Clip for numerical stability before exp
    arg_clipped = np.clip(arg, -50.0, 50.0)
    return 1.0 / (1.0 + np.exp(-arg_clipped))


def pseudo_huber(r: np.ndarray, delta: float) -> np.ndarray:
    """V3.1 Definition 5. Pseudo-Huber penalty.

    rho(r; delta) = delta^2 * (sqrt(1 + (r/delta)^2) - 1)

    Quadratic near zero, linear for large |r|.
    """
    r_arr = np.asarray(r, dtype=np.float64)
    return (delta * delta) * (np.sqrt(1.0 + (r_arr / delta) ** 2) - 1.0)


def _enumerate_pairs(
    num_models: int, use_anchor_pairing: bool, anchor_index: int
) -> List[Tuple[int, int]]:
    """Enumerate (i, j) model pairs. j is the body-frame reference.

    Anchor mode: j = anchor_index, i ranges over the other models
    (V3.1 Section 4.5). All-pairs mode enumerates every unordered
    pair once with the lower-indexed model as the reference j so
    that for M=2 both modes produce the same single pair.
    """
    if use_anchor_pairing:
        return [
            (i, anchor_index) for i in range(num_models) if i != anchor_index
        ]
    return [(i, j) for i in range(num_models) for j in range(i)]


def _pair_cost(
    traj_i: np.ndarray,
    traj_j: np.ndarray,
    config: BCVFConfig,
) -> Tuple[float, float, int]:
    """Compute the per-pair BCVF cost plus diagnostic stats.

    Returns (pair_cost, max_signal_norm, gate_activation_count).
    """
    e = compute_disagreement(traj_i, traj_j, config.lever_arm)  # (H, 3)
    # Select which derivative-order signal to penalize and align the gate
    # to the same stencil indices (DESIGN.md §3B.10 ablation variants).
    if config.cost_order == CostOrder.SECOND:
        signal = compute_disagreement_acceleration(e, config.dt)  # (H-2, 3)
        gate_input = e[1:-1]                                      # (H-2, 3)
    elif config.cost_order == CostOrder.FIRST:
        signal = compute_disagreement_velocity(e, config.dt)      # (H-1, 3)
        gate_input = 0.5 * (e[:-1] + e[1:])                       # (H-1, 3)
    else:  # ZEROTH
        signal = e                                                # (H, 3)
        gate_input = e                                            # (H, 3)

    gate = smooth_gate(
        gate_input, config.gate_threshold, config.gate_beta, config.weight_matrix
    )

    w_sqrt = np.sqrt(np.asarray(config.weight_matrix, dtype=np.float64))
    signal_norms = np.linalg.norm(signal * w_sqrt, axis=-1)

    penalty = pseudo_huber(signal_norms, config.huber_delta)
    pair_cost = float(np.sum(gate * penalty) * config.dt)

    max_signal = float(signal_norms.max()) if signal_norms.size > 0 else 0.0
    activations = int(np.count_nonzero(gate > 0.5))
    return pair_cost, max_signal, activations


def compute_bcvf_cost(
    trajectories: List[np.ndarray], config: BCVFConfig
) -> BCVFResult:
    """V3.1 Definition 6. Full J_BCVF over a set of model trajectories.

    ``trajectories`` is a list of M arrays shaped (H, 3).
    """
    if len(trajectories) < 2:
        raise ValueError(
            f"BCVF requires at least 2 model trajectories; got {len(trajectories)}"
        )
    horizons = {t.shape[0] for t in trajectories}
    if len(horizons) != 1:
        raise ValueError(f"Trajectories must share the same horizon; got {horizons}")
    if any(t.shape[-1] != 3 for t in trajectories):
        raise ValueError("Each trajectory must have shape (H, 3) for SE(2)")
    if next(iter(horizons)) < 3:
        raise ValueError("BCVF requires H >= 3 for the second-difference stencil")

    pairs = _enumerate_pairs(
        len(trajectories), config.use_anchor_pairing, config.anchor_index
    )

    per_pair: Dict[Tuple[int, int], float] = {}
    max_accel = 0.0
    activations = 0
    total = 0.0
    for (i, j) in pairs:
        cost, pair_max_accel, pair_activations = _pair_cost(
            trajectories[i], trajectories[j], config
        )
        per_pair[(i, j)] = cost
        total += cost
        if pair_max_accel > max_accel:
            max_accel = pair_max_accel
        activations += pair_activations

    return BCVFResult(
        total_cost=total,
        per_pair_costs=per_pair,
        max_acceleration_norm=max_accel,
        gate_activation_count=activations,
    )


def compute_bcvf_cost_batch(
    trajectories_batch: List[List[np.ndarray]],
    config: BCVFConfig,
) -> np.ndarray:
    """Vectorized batch entry point for MPPI.

    ``trajectories_batch`` is a list of K items, each a list of M
    trajectories of shape (H, 3). Returns (K,) scalar costs.

    The inner per-pair computation is vectorized across K rollouts:
    disagreement, acceleration, gate, and Huber all operate on
    (K, H, 3) tensors. The only Python-level loop is over model pairs,
    which is O(M) in anchor mode.
    """
    if len(trajectories_batch) == 0:
        return np.zeros(0, dtype=np.float64)

    # Stack to a (K, M, H, 3) tensor.
    stacked = np.asarray(trajectories_batch, dtype=np.float64)
    if stacked.ndim != 4 or stacked.shape[-1] != 3:
        raise ValueError(
            f"trajectories_batch must stack to (K, M, H, 3); got {stacked.shape}"
        )
    k_batch, num_models, horizon, _ = stacked.shape
    if num_models < 2:
        raise ValueError(f"BCVF requires M >= 2; got M={num_models}")
    if horizon < 3:
        raise ValueError(f"BCVF requires H >= 3; got H={horizon}")

    pairs = _enumerate_pairs(
        num_models, config.use_anchor_pairing, config.anchor_index
    )

    w_sqrt = np.sqrt(np.asarray(config.weight_matrix, dtype=np.float64))
    total = np.zeros(k_batch, dtype=np.float64)

    for (i, j) in pairs:
        traj_i = stacked[:, i, :, :]  # (K, H, 3)
        traj_j = stacked[:, j, :, :]  # (K, H, 3)

        # Body-frame error over (K, H, 3): reuse vectorized manifold op.
        e = body_frame_error_trajectory(traj_i, traj_j, config.lever_arm)

        if config.cost_order == CostOrder.SECOND:
            signal = (e[:, 2:, :] - 2.0 * e[:, 1:-1, :] + e[:, :-2, :]) / (
                config.dt * config.dt
            )
            gate_input = e[:, 1:-1, :]
        elif config.cost_order == CostOrder.FIRST:
            signal = (e[:, 1:, :] - e[:, :-1, :]) / config.dt
            gate_input = 0.5 * (e[:, :-1, :] + e[:, 1:, :])
        else:  # ZEROTH
            signal = e
            gate_input = e

        gate_norm = np.linalg.norm(gate_input * w_sqrt, axis=-1)
        gate_arg = config.gate_beta * (gate_norm - config.gate_threshold)
        gate_arg = np.clip(gate_arg, -50.0, 50.0)
        gate = 1.0 / (1.0 + np.exp(-gate_arg))

        signal_norms = np.linalg.norm(signal * w_sqrt, axis=-1)
        penalty = (config.huber_delta ** 2) * (
            np.sqrt(1.0 + (signal_norms / config.huber_delta) ** 2) - 1.0
        )

        total += np.sum(gate * penalty, axis=-1) * config.dt

    return total

"""Disagreement Signal Characterization (DESIGN.md Phase 1.5).

Six synthetic SE(2) trace families that isolate one disagreement dynamic
each, plus helpers for computing e/v/a statistics and a parameter
sensitivity sweep. The goal is to prove the second-order disagreement
signal is actionable before building predictors and a planner.

All traces use shape (H, 3) float64 arrays with columns [x, y, theta].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import numpy as np

from .core import (
    BCVFConfig,
    compute_bcvf_cost,
    compute_disagreement,
    compute_disagreement_acceleration,
    compute_disagreement_velocity,
    smooth_gate,
)

TRACE_FAMILIES: Tuple[str, ...] = (
    "constant_bias",
    "linear_drift",
    "quadratic_divergence",
    "one_time_jump",
    "repeated_jitter",
    "mode_switch",
)

# Which families represent nominal (should-be-quiet) vs. failure (should-fire)
# disagreement. `constant_bias` has large ||e|| so its gate is always on by
# construction; we keep it in the nominal set because its BCVF *cost* is zero
# (acceleration is zero). The sensitivity report therefore uses cost-based
# separation, with a jitter-only gate-rate metric reported alongside.
NOMINAL_FAMILIES: Tuple[str, ...] = ("constant_bias", "linear_drift", "repeated_jitter")
FAILURE_FAMILIES: Tuple[str, ...] = (
    "quadratic_divergence",
    "one_time_jump",
    "mode_switch",
)


@dataclass
class TraceResult:
    """Statistics from one synthetic trace evaluation."""

    name: str
    e_max: float
    e_mean: float
    e_std: float
    v_max: float
    v_mean: float
    a_max: float
    a_mean: float
    a_std: float
    bcvf_cost: float
    gate_activation_rate: float


def _zero_traj(horizon: int) -> np.ndarray:
    return np.zeros((horizon, 3), dtype=np.float64)


def generate_trace(
    name: str,
    H: int = 50,
    dt: float = 0.1,
    **kwargs: Any,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a pair of (H, 3) trajectories for one trace family.

    Supported families: constant_bias, linear_drift, quadratic_divergence,
    one_time_jump, repeated_jitter, mode_switch. See DESIGN.md §1.5.3 for
    expected magnitudes.
    """
    if name not in TRACE_FAMILIES:
        raise ValueError(f"unknown trace family: {name!r}; expected one of {TRACE_FAMILIES}")

    ks = np.arange(H, dtype=np.float64)
    traj_i = _zero_traj(H)
    traj_j = _zero_traj(H)

    if name == "constant_bias":
        offset = float(kwargs.get("offset", 0.5))
        traj_j[:, 0] = offset
    elif name == "linear_drift":
        rate = float(kwargs.get("rate", 0.01))
        traj_j[:, 0] = rate * ks
    elif name == "quadratic_divergence":
        coeff = float(kwargs.get("coeff", 0.01))
        traj_j[:, 0] = coeff * ks * ks
    elif name == "one_time_jump":
        step = int(kwargs.get("step", H // 2))
        amplitude = float(kwargs.get("amplitude", 2.0))
        traj_j[step:, 0] = amplitude
    elif name == "repeated_jitter":
        noise_std = float(kwargs.get("noise_std", 0.05))
        seed = int(kwargs.get("seed", 12345))
        rng = np.random.default_rng(seed)
        traj_j[:, 0] = rng.normal(loc=0.0, scale=noise_std, size=H)
    elif name == "mode_switch":
        switch_step = int(kwargs.get("switch_step", 20))
        coeff = float(kwargs.get("coeff", 0.02))
        # traj_j matches traj_i up to switch_step, then diverges quadratically.
        post = ks[switch_step:] - switch_step
        traj_j[switch_step:, 0] = coeff * post * post

    return traj_i, traj_j


def analyze_trace(
    traj_i: np.ndarray,
    traj_j: np.ndarray,
    config: BCVFConfig,
    name: str = "",
) -> TraceResult:
    """Compute e, v, a statistics and BCVF cost for a trace pair."""
    e = compute_disagreement(traj_i, traj_j, config.lever_arm)
    v = compute_disagreement_velocity(e, config.dt)
    a = compute_disagreement_acceleration(e, config.dt)

    e_norms = np.linalg.norm(e, axis=-1)
    v_norms = np.linalg.norm(v, axis=-1)
    a_norms = np.linalg.norm(a, axis=-1)

    gate = smooth_gate(
        e[1:-1], config.gate_threshold, config.gate_beta, config.weight_matrix
    )
    gate_rate = float(np.mean(gate > 0.5)) if gate.size > 0 else 0.0

    cost = compute_bcvf_cost([traj_i, traj_j], config).total_cost

    return TraceResult(
        name=name,
        e_max=float(e_norms.max()),
        e_mean=float(e_norms.mean()),
        e_std=float(e_norms.std()),
        v_max=float(v_norms.max()) if v_norms.size else 0.0,
        v_mean=float(v_norms.mean()) if v_norms.size else 0.0,
        a_max=float(a_norms.max()) if a_norms.size else 0.0,
        a_mean=float(a_norms.mean()) if a_norms.size else 0.0,
        a_std=float(a_norms.std()) if a_norms.size else 0.0,
        bcvf_cost=float(cost),
        gate_activation_rate=gate_rate,
    )


def run_all_traces(
    config: BCVFConfig, H: int = 50, dt: float | None = None
) -> Dict[str, TraceResult]:
    """Evaluate every trace family with the given config."""
    if dt is None:
        dt = config.dt
    results: Dict[str, TraceResult] = {}
    for name in TRACE_FAMILIES:
        traj_i, traj_j = generate_trace(name, H=H, dt=dt)
        results[name] = analyze_trace(traj_i, traj_j, config, name=name)
    return results


def parameter_sensitivity_report(
    T_values: List[float] | None = None,
    beta_multipliers: List[float] | None = None,
    H: int = 50,
    dt: float = 0.1,
    lever_arm: float = 2.5,
    huber_delta: float = 0.5,
) -> Dict[str, Any]:
    """Sweep gate threshold T and beta multiplier across trace families.

    For each (T, beta=multiplier/T) the report records:

    - ``false_cost``: max BCVF cost over nominal families
      (constant_bias, linear_drift, repeated_jitter).
    - ``true_cost``: min BCVF cost over failure families
      (quadratic_divergence, one_time_jump, mode_switch).
    - ``separation_ratio``: ``true_cost / max(false_cost, 1e-9)``.
    - ``false_activation_rate_jitter``: gate activation rate on the
      repeated_jitter family — the narrow metric that matches the
      §1.5.6 success gate #4.
    - ``true_activation_rate``: mean gate activation rate across failure
      families.

    A recommended pair satisfies ``separation_ratio > 10`` and
    ``false_activation_rate_jitter < 0.05``.
    """
    if T_values is None:
        T_values = [0.01, 0.05, 0.1, 0.2, 0.5]
    if beta_multipliers is None:
        beta_multipliers = [10.0, 20.0, 50.0, 100.0]

    grid: List[Dict[str, Any]] = []
    recommended: Dict[str, Any] | None = None
    best_score = -np.inf

    for T in T_values:
        for mult in beta_multipliers:
            beta = mult / T
            config = BCVFConfig(
                lambda_c=1.0,
                gate_threshold=T,
                gate_beta=beta,
                huber_delta=huber_delta,
                lever_arm=lever_arm,
                weight_matrix=np.ones(3, dtype=np.float64),
                use_anchor_pairing=True,
                anchor_index=0,
                dt=dt,
            )
            results = run_all_traces(config, H=H, dt=dt)
            nominal_costs = [results[f].bcvf_cost for f in NOMINAL_FAMILIES]
            failure_costs = [results[f].bcvf_cost for f in FAILURE_FAMILIES]
            failure_gate_rates = [
                results[f].gate_activation_rate for f in FAILURE_FAMILIES
            ]
            false_cost = max(nominal_costs)
            true_cost = min(failure_costs)
            separation = true_cost / max(false_cost, 1e-9)
            jitter_rate = results["repeated_jitter"].gate_activation_rate
            true_rate = float(np.mean(failure_gate_rates))

            entry = {
                "T": T,
                "beta": beta,
                "beta_multiplier": mult,
                "false_cost": false_cost,
                "true_cost": true_cost,
                "separation_ratio": separation,
                "false_activation_rate_jitter": jitter_rate,
                "true_activation_rate": true_rate,
                "per_trace": {name: r.bcvf_cost for name, r in results.items()},
            }
            grid.append(entry)

            # Score: prefer high separation with jitter suppressed.
            score = separation - 100.0 * max(jitter_rate - 0.05, 0.0)
            if score > best_score:
                best_score = score
                recommended = entry

    return {"grid": grid, "recommended": recommended}

"""Tests for bcvf_autonomous.traces — DESIGN.md Section 1.5.5 + 1.5.6."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.core import BCVFConfig
from symbolu_robotics.bcvf_autonomous.traces import (
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    TRACE_FAMILIES,
    analyze_trace,
    generate_trace,
    parameter_sensitivity_report,
    run_all_traces,
)


DEFAULT_T = 0.2       # Phase 1.5 sweep result; see default_se2.yaml.
DEFAULT_BETA = 100.0  # multiplier 20/T, matches V3.1 [20/T, 50/T] lower bound.


def _default_config() -> BCVFConfig:
    return BCVFConfig(
        lambda_c=1.0,
        gate_threshold=DEFAULT_T,
        gate_beta=DEFAULT_BETA,
        huber_delta=0.5,
        lever_arm=2.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=True,
        anchor_index=0,
        dt=0.1,
    )


# --- §1.5.5 trace property tests ---


def test_constant_bias_quiet() -> None:
    traj_i, traj_j = generate_trace("constant_bias")
    result = analyze_trace(traj_i, traj_j, _default_config(), name="constant_bias")
    assert result.a_max < 1e-10
    assert result.bcvf_cost < 1e-10


def test_linear_drift_quiet() -> None:
    traj_i, traj_j = generate_trace("linear_drift")
    result = analyze_trace(traj_i, traj_j, _default_config(), name="linear_drift")
    assert result.a_mean < 1e-6
    assert result.bcvf_cost < 1e-6


def test_quadratic_divergence_loud() -> None:
    traj_i, traj_j = generate_trace("quadratic_divergence")
    result = analyze_trace(
        traj_i, traj_j, _default_config(), name="quadratic_divergence"
    )
    assert result.bcvf_cost > 0.1


def test_one_time_jump_detected() -> None:
    traj_i, traj_j = generate_trace("one_time_jump", step=25, amplitude=2.0)
    result = analyze_trace(traj_i, traj_j, _default_config(), name="one_time_jump")
    # Second-difference amplifies a 2m jump by 1/dt^2 = 100.
    assert result.a_max > 1.0
    assert result.bcvf_cost > 0.1


def test_jitter_suppressed_by_gate() -> None:
    traj_i, traj_j = generate_trace("repeated_jitter", noise_std=0.05, seed=12345)
    result = analyze_trace(traj_i, traj_j, _default_config(), name="repeated_jitter")
    # Section 1.5.6 success gate #4.
    assert result.gate_activation_rate < 0.05


def test_mode_switch_localized() -> None:
    traj_i, traj_j = generate_trace("mode_switch", switch_step=20, coeff=0.02)
    cfg = _default_config()
    result = analyze_trace(traj_i, traj_j, cfg, name="mode_switch")

    # Gate activations should cluster strictly after the switch step.
    from symbolu_robotics.bcvf_autonomous.core import (
        compute_disagreement,
        smooth_gate,
    )

    e = compute_disagreement(traj_i, traj_j, cfg.lever_arm)
    gate = smooth_gate(e[1:-1], cfg.gate_threshold, cfg.gate_beta, cfg.weight_matrix)
    # Acceleration indices are [1, H-2], so gate index k corresponds to traj step k+1.
    active_idx = np.nonzero(gate > 0.5)[0]
    assert active_idx.size > 0
    # All activations occur on or after the switch step (20).
    assert int(active_idx.min()) + 1 >= 20
    assert result.bcvf_cost > 0.0


def test_separation_ratio() -> None:
    report = parameter_sensitivity_report()
    matches = [
        e
        for e in report["grid"]
        if abs(e["T"] - DEFAULT_T) < 1e-12 and abs(e["beta"] - DEFAULT_BETA) < 1e-9
    ]
    assert matches, (
        f"default (T={DEFAULT_T}, beta={DEFAULT_BETA}) must appear in the grid"
    )
    default_entry = matches[0]
    assert default_entry["separation_ratio"] > 10.0
    assert default_entry["false_activation_rate_jitter"] < 0.05


def test_all_traces_generate() -> None:
    for name in TRACE_FAMILIES:
        traj_i, traj_j = generate_trace(name, H=50, dt=0.1)
        assert traj_i.shape == (50, 3)
        assert traj_j.shape == (50, 3)
        assert traj_i.dtype == np.float64
        assert traj_j.dtype == np.float64


# --- §1.5.6 success-gate smoke: all nominal traces quiet, all failures loud ---


def test_success_gate_cost_separation() -> None:
    results = run_all_traces(_default_config())
    nominal_costs = [results[name].bcvf_cost for name in NOMINAL_FAMILIES]
    failure_costs = [results[name].bcvf_cost for name in FAILURE_FAMILIES]
    assert max(nominal_costs) < 1e-2, f"nominal costs too high: {nominal_costs}"
    assert min(failure_costs) > 0.1, f"failure costs too low: {failure_costs}"
    # §1.5.6 gate #2: failure cost at least 100x repeated_jitter cost.
    jitter_cost = max(results["repeated_jitter"].bcvf_cost, 1e-12)
    assert min(failure_costs) / jitter_cost > 100.0


def test_unknown_trace_raises() -> None:
    with pytest.raises(ValueError):
        generate_trace("not_a_family")

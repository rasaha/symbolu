"""Tests for the BCVF Autonomous characterization sweep."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    CostOrder,
    compute_bcvf_cost,
)
from symbolu_robotics.bcvf_autonomous.characterization import (
    AlignmentMetrics,
    FAILURE_FAMILIES,
    NOMINAL_FAMILIES,
    aggregate_alignment,
    compute_alignment_metrics,
    family_pass_rate,
    generate_trace,
    pick_winner_tuple,
    run_ablation_grid,
    run_primary_grid,
    run_sensitivity_grid,
    summarize_grid,
)


# --------------------------------------------------------------------------- #
# Trace bundle generators
# --------------------------------------------------------------------------- #


def test_baseline_traces_are_identical():
    bundle = generate_trace("baseline", M=3, H=20)
    np.testing.assert_array_equal(bundle.trajectories[0], bundle.trajectories[1])
    np.testing.assert_array_equal(bundle.trajectories[1], bundle.trajectories[2])
    assert bundle.truth_label is None
    assert bundle.valid_masks is None


def test_constant_bias_only_target_predictor_offset():
    bundle = generate_trace("constant_bias", M=3, H=10, bias=1.0, target_predictor=1)
    np.testing.assert_array_equal(bundle.trajectories[0], bundle.trajectories[2])
    assert (bundle.trajectories[1, :, 1] - bundle.trajectories[0, :, 1] == 1.0).all()


def test_linear_drift_growth_is_linear():
    bundle = generate_trace("linear_drift", M=3, H=20, drift_rate=0.1, dt=0.1)
    diff = bundle.trajectories[1, :, 1] - bundle.trajectories[0, :, 1]
    # diff[k] = 0.1 * k * 0.1 = 0.01 * k → first difference is constant 0.01.
    np.testing.assert_allclose(np.diff(diff), 0.01, atol=1e-12)


def test_accelerating_growth_is_quadratic():
    bundle = generate_trace("accelerating", M=3, H=20, accel_mag=1.0, dt=0.1)
    diff = bundle.trajectories[1, :, 1] - bundle.trajectories[0, :, 1]
    # diff[k] = 0.5 * 1.0 * (k * 0.1)^2 → second difference is constant.
    second = np.diff(np.diff(diff))
    np.testing.assert_allclose(second, second[0], atol=1e-12)
    assert second[0] != 0.0
    assert bundle.truth_label == 1


def test_noise_floor_perturbs_all_predictors():
    bundle = generate_trace("noise_floor", M=3, H=20, sigma_noise=0.05, seed=7)
    # No two predictors should be exactly equal under noise.
    assert not np.allclose(bundle.trajectories[0], bundle.trajectories[1])
    assert not np.allclose(bundle.trajectories[1], bundle.trajectories[2])
    assert bundle.truth_label is None


def test_outlier_truth_label_defaults_to_zero():
    bundle = generate_trace("outlier", M=3, H=10)
    assert bundle.truth_label == 0
    # Predictor 1 and 2 are nominal — identical.
    np.testing.assert_array_equal(bundle.trajectories[1], bundle.trajectories[2])


def test_sensor_dropout_freezes_after_k_dropout():
    H = 30
    k = 10
    bundle = generate_trace(
        "sensor_dropout",
        M=3,
        H=H,
        outer_family="baseline",
        k_dropout=k,
        dropped_predictor=2,
    )
    frozen = bundle.trajectories[2]
    # Pose at every step after k matches pose at k.
    for t in range(k + 1, H):
        np.testing.assert_array_equal(frozen[t], frozen[k])
    assert bundle.truth_label == 2
    assert bundle.valid_masks.shape == (3, H)
    assert bundle.valid_masks[2, k + 1 :].sum() == 0
    assert bundle.valid_masks[2, : k + 1].all()


def test_sensor_dropout_rejects_self_wrap():
    with pytest.raises(ValueError):
        generate_trace(
            "sensor_dropout",
            outer_family="sensor_dropout",
            k_dropout=5,
            dropped_predictor=0,
        )


def test_unknown_family_rejected():
    with pytest.raises(ValueError):
        generate_trace("not_a_family")


def test_invalid_dimensions_rejected():
    with pytest.raises(ValueError):
        generate_trace("baseline", M=1)
    with pytest.raises(ValueError):
        generate_trace("baseline", H=2)


# --------------------------------------------------------------------------- #
# Kernel correctness on each family at V1 defaults
# --------------------------------------------------------------------------- #


def _v1_config() -> BCVFConfig:
    return BCVFConfig(
        lambda_c=1.0,
        gate_threshold=0.2,
        gate_beta=100.0,
        huber_delta=0.5,
        weight_matrix=np.ones(3, dtype=np.float64),
        use_anchor_pairing=False,
        anchor_index=0,
        dt=0.1,
        cost_order=CostOrder.SECOND,
    )


@pytest.mark.parametrize("family", ["baseline", "constant_bias", "linear_drift"])
def test_nominal_families_produce_zero_cost_under_second_order(family):
    bundle = generate_trace(family, M=3, H=50)
    cfg = _v1_config()
    result = compute_bcvf_cost(
        [bundle.trajectories[m] for m in range(3)], cfg
    )
    assert result.total_cost <= 1e-9


def test_accelerating_fires_kernel():
    bundle = generate_trace("accelerating", M=3, H=50, accel_mag=0.5)
    cfg = _v1_config()
    result = compute_bcvf_cost(
        [bundle.trajectories[m] for m in range(3)], cfg
    )
    assert result.total_cost > 1e-3
    assert result.gate_activation_count > 0


def test_outlier_attributes_to_truth_predictor():
    bundle = generate_trace("outlier", M=3, H=50, accel_mag=1.0)
    cfg = _v1_config()
    from symbolu_robotics.bcvf_autonomous.observables.kernel_per_step import (
        compute_bcvf_per_step,
    )
    breakdown = compute_bcvf_per_step(bundle.trajectories, cfg)
    per_pred = breakdown.per_step_per_predictor.sum(axis=1)
    metrics = compute_alignment_metrics(per_pred, bundle.truth_label)
    assert metrics is not None
    assert metrics.hit == 1
    assert metrics.rank == 1


# --------------------------------------------------------------------------- #
# Alignment helpers
# --------------------------------------------------------------------------- #


def test_compute_alignment_metrics_basic():
    arr = np.array([3.0, 1.0, 0.5])
    m = compute_alignment_metrics(arr, truth_label=0)
    assert m.hit == 1
    assert m.rank == 1
    assert m.margin == pytest.approx(3.0 / ((1.0 + 0.5) / 2))


def test_compute_alignment_metrics_no_truth_label_returns_none():
    arr = np.array([1.0, 2.0, 3.0])
    assert compute_alignment_metrics(arr, truth_label=None) is None


def test_compute_alignment_metrics_index_validation():
    with pytest.raises(IndexError):
        compute_alignment_metrics(np.array([1.0, 2.0]), truth_label=5)


def test_aggregate_alignment_summarises():
    metrics = [
        AlignmentMetrics(hit=1, margin=2.0, rank=1),
        AlignmentMetrics(hit=0, margin=0.5, rank=2),
        AlignmentMetrics(hit=1, margin=3.0, rank=1),
    ]
    agg = aggregate_alignment(metrics)
    assert agg is not None
    assert agg.n_cells == 3
    assert agg.hit_rate == pytest.approx(2 / 3)
    assert agg.margin_mean == pytest.approx((2.0 + 0.5 + 3.0) / 3)
    assert agg.rank_distribution[1] == pytest.approx(2 / 3)


def test_aggregate_alignment_empty_returns_none():
    assert aggregate_alignment([]) is None
    assert aggregate_alignment([None, None]) is None


# --------------------------------------------------------------------------- #
# Sweep harness — acceptance criteria from DESIGN.md §8
# --------------------------------------------------------------------------- #


def test_primary_grid_zero_false_positives_or_negatives():
    """DESIGN §8.1 + §8.2: every nominal family quiet, every failure family fires."""
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    assert summary["false_positive_rate"] == pytest.approx(0.0)
    assert summary["false_negative_rate"] == pytest.approx(0.0)
    for fam, rec in summary["per_family"].items():
        assert rec["pass_rate"] == pytest.approx(1.0), (
            f"family {fam} failed: {rec}"
        )


def test_ablation_only_second_order_rejects_linear_drift():
    """DESIGN §8.3: ZEROTH and FIRST cost orders fire on linear drift; SECOND rejects."""
    cells = run_ablation_grid()
    by_order: dict = defaultdict(list)
    for c in cells:
        by_order[c.cost_order].append(c)

    n_second_pass = sum(1 for c in by_order["SECOND"] if c.cell_pass)
    assert n_second_pass == len(by_order["SECOND"]) > 0

    n_zeroth_pass = sum(1 for c in by_order["ZEROTH"] if c.cell_pass)
    n_first_pass = sum(1 for c in by_order["FIRST"] if c.cell_pass)
    # ZEROTH and FIRST should fire on linear drift (cost above threshold).
    # That fires the threshold check ⇒ cell_pass = False.
    assert n_zeroth_pass < len(by_order["ZEROTH"])
    assert n_first_pass < len(by_order["FIRST"])


def test_sensitivity_picks_winner_close_to_v1_defaults():
    """DESIGN §8.4: sensitivity grid yields at least one all-pass winner near V1 defaults."""
    cells = run_sensitivity_grid()
    winner, candidates = pick_winner_tuple(cells)
    assert winner is not None, "no all-pass (T, β, δ) tuple found"
    assert len(candidates) >= 1
    # The V1 defaults must themselves be a candidate.
    assert {"T": 0.2, "beta": 100.0, "delta": 0.5} in candidates


def test_sensitivity_winner_is_v1_defaults():
    """Stronger §8.4 check: winner = V1 defaults (closest by tiebreaker)."""
    cells = run_sensitivity_grid()
    winner, _ = pick_winner_tuple(cells)
    assert winner == {"T": 0.2, "beta": 100.0, "delta": 0.5}


def test_pick_winner_returns_none_when_no_all_pass():
    """If we hand in a cell list where every cell fails, the picker returns None."""
    cells = run_primary_grid()
    # Mark every cell as failed.
    for c in cells:
        c.cell_pass = False
    winner, candidates = pick_winner_tuple(cells)
    assert winner is None
    assert candidates == []


def test_summarize_grid_shapes():
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    assert "n_cells" in summary
    assert "per_family" in summary
    assert "false_positive_rate" in summary
    assert "false_negative_rate" in summary
    assert set(summary["per_family"].keys()) == set(
        list(NOMINAL_FAMILIES) + list(FAILURE_FAMILIES)
    )


def test_family_pass_rate_per_family():
    cells = run_primary_grid()
    rates = family_pass_rate(cells)
    for fam in NOMINAL_FAMILIES + FAILURE_FAMILIES:
        assert fam in rates
        assert rates[fam]["total"] > 0

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
    CERTIFICATION_FLOOR,
    FAILURE_FAMILIES,
    LEGACY_PRIMARY_SEEDS,
    NOMINAL_FAMILIES,
    PRIMARY_SEEDS,
    PerConfigPassStat,
    WILSON_Z_95,
    aggregate_alignment,
    compute_alignment_metrics,
    family_pass_rate,
    generate_trace,
    per_config_pass_stats,
    pick_winner_tuple,
    run_ablation_grid,
    run_primary_grid,
    run_sensitivity_grid,
    summarize_grid,
    wilson_ci,
    wilson_lower_bound,
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
    assert summary.false_positive_rate == pytest.approx(0.0)
    assert summary.false_negative_rate == pytest.approx(0.0)
    for fam, rec in summary.per_family.items():
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
    assert summary.n_cells > 0
    assert summary.per_family
    assert summary.false_positive_rate == 0.0
    assert summary.false_negative_rate == 0.0
    assert set(summary.per_family.keys()) == set(
        list(NOMINAL_FAMILIES) + list(FAILURE_FAMILIES)
    )


def test_summarize_grid_to_dict_matches_legacy_shape():
    """``GridSummary.to_dict()`` mirrors the dict shape callers used to
    read off the legacy ``summarize_grid`` return — preserves the JSON
    contract for downstream consumers (artifact archives, dashboards)."""
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    payload = summary.to_dict()
    expected_keys = {
        "n_cells", "per_family",
        "false_positive_rate", "false_negative_rate",
        "per_config", "min_ci_lower_bound",
        "cells_below_certification_floor",
        "certification_floor", "wilson_z",
    }
    assert expected_keys.issubset(payload.keys())
    assert payload["n_cells"] == summary.n_cells
    assert payload["false_positive_rate"] == summary.false_positive_rate


# --------------------------------------------------------------------------- #
# Production-parity coverage — M = 4 (IMU + LiDAR + VO + GNSS)
# --------------------------------------------------------------------------- #


def test_primary_grid_passes_at_m_equals_4():
    """The production autonomous stack runs four predictors. The
    characterization suite must hold at M=4 too — anchor pairing
    enumerates more pairs and per-predictor attribution dilutes
    differently, so M=3 coverage doesn't carry over automatically.
    """
    cells = run_primary_grid(M=4)
    summary = summarize_grid(cells)
    assert summary.false_positive_rate == pytest.approx(0.0)
    assert summary.false_negative_rate == pytest.approx(0.0)
    for fam, rec in summary.per_family.items():
        assert rec["pass_rate"] == pytest.approx(1.0), (
            f"M=4: family {fam} failed: {rec}"
        )


def test_outlier_attribution_at_m_equals_4():
    """Outlier (truth_label=0) at M=4 must rank-1 the truth predictor
    even though the kernel now distributes pair costs across three
    non-truth predictors instead of two. This is the regression check
    that anchor-pairing changes don't move the outlier off rank 1.
    """
    bundle = generate_trace("outlier", M=4, H=50, accel_mag=1.0)
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


def test_sensor_dropout_at_m_equals_4_keeps_alignment_loose():
    """At M=4 the sensor_dropout alignment criterion is "rank < 4"
    (not last). With one outer outlier and one dropout on different
    predictors, the dropped predictor should land in rank 1, 2, or 3
    but not 4."""
    bundle = generate_trace(
        "sensor_dropout",
        M=4,
        H=50,
        outer_family="outlier",
        accel_mag=1.0,
        k_dropout=20,
        dropped_predictor=3,
    )
    cfg = _v1_config()
    from symbolu_robotics.bcvf_autonomous.observables.kernel_per_step import (
        compute_bcvf_per_step,
    )
    breakdown = compute_bcvf_per_step(bundle.trajectories, cfg)
    per_pred = breakdown.per_step_per_predictor.sum(axis=1)
    metrics = compute_alignment_metrics(per_pred, bundle.truth_label)
    assert metrics is not None
    assert metrics.rank < 4


def test_family_pass_rate_per_family():
    cells = run_primary_grid()
    rates = family_pass_rate(cells)
    for fam in NOMINAL_FAMILIES + FAILURE_FAMILIES:
        assert fam in rates
        assert rates[fam]["total"] > 0


# --------------------------------------------------------------------------- #
# Kernel-sensitivity regression tests
# (DESIGN.md §8 — confirms the sweep would FAIL if the kernel broke)
# --------------------------------------------------------------------------- #


def test_sweep_catches_silenced_gate():
    """Sabotage: set gate_threshold absurdly high so the gate never opens.

    Failure families should now register zero cost and miss every
    threshold gate. If this test ever passes a failure-family cell,
    the threshold tables in ``_evaluate_thresholds`` are vacuously
    permissive and the sweep is not actually defending the kernel.
    """
    from symbolu_robotics.bcvf_autonomous.characterization.sweep import (
        _eval_cell,
    )
    cell_accel = _eval_cell(
        grid="sabotage_silenced_gate",
        family="accelerating",
        family_params={"accel_mag": 1.0},
        T=1e9,  # gate never opens
        beta=100.0,
        delta=0.5,
        seed=42,
    )
    assert not cell_accel.cell_pass
    assert cell_accel.gate_activations == 0
    # The "gate_open" threshold check must have fired.
    assert any("gate_activations" in r for r in cell_accel.failure_reasons)

    cell_outlier = _eval_cell(
        grid="sabotage_silenced_gate",
        family="outlier",
        family_params={"accel_mag": 1.0},
        T=1e9,
        beta=100.0,
        delta=0.5,
        seed=42,
    )
    assert not cell_outlier.cell_pass


def test_sweep_catches_zeroed_per_step_kernel(monkeypatch):
    """Sabotage: replace ``compute_bcvf_per_step`` with one that always
    returns zeros. Failure families should fail their cost-magnitude
    threshold checks and outlier should fail alignment (truth predictor
    can no longer be ranked above non-truth when every cost is zero).
    """
    import symbolu_robotics.bcvf_autonomous.characterization.sweep as sw
    from symbolu_robotics.bcvf_autonomous.observables.kernel_per_step import (
        BCVFPerStepBreakdown,
    )

    def fake_per_step(trajectories, config):
        M, H, _ = trajectories.shape
        if config.cost_order.value == 2:
            stencil = H - 2
        elif config.cost_order.value == 1:
            stencil = H - 1
        else:
            stencil = H
        return BCVFPerStepBreakdown(
            per_step_total=np.zeros(stencil),
            per_step_per_pair={},
            per_step_per_predictor=np.zeros((M, stencil)),
            gate_activations_per_step=np.zeros(stencil, dtype=np.int64),
            signal_norm_max_per_step=np.zeros(stencil),
        )

    monkeypatch.setattr(sw, "compute_bcvf_per_step", fake_per_step)

    cell_accel = sw._eval_cell(
        grid="sabotage_zero_kernel",
        family="accelerating",
        family_params={"accel_mag": 1.0},
        T=0.2,
        beta=100.0,
        delta=0.5,
        seed=42,
    )
    # Per-predictor breakdown is zero ⇒ all four predictors tie for
    # "lowest cost" and the alignment check picks index 0 by stable
    # sort. The accelerating truth_label is 1, so alignment misses.
    assert not cell_accel.cell_pass


def test_sweep_catches_uniform_attribution(monkeypatch):
    """Sabotage: ``compute_bcvf_per_step`` returns uniform per-predictor
    cost. Outlier should miss its truth-ratio gate (>= 1.5)."""
    import symbolu_robotics.bcvf_autonomous.characterization.sweep as sw
    from symbolu_robotics.bcvf_autonomous.observables.kernel_per_step import (
        BCVFPerStepBreakdown,
    )

    def uniform_per_step(trajectories, config):
        M, H, _ = trajectories.shape
        stencil = H - 2 if config.cost_order.value == 2 else H
        return BCVFPerStepBreakdown(
            per_step_total=np.ones(stencil),
            per_step_per_pair={},
            per_step_per_predictor=np.ones((M, stencil)),
            gate_activations_per_step=np.full(stencil, M, dtype=np.int64),
            signal_norm_max_per_step=np.ones(stencil),
        )

    monkeypatch.setattr(sw, "compute_bcvf_per_step", uniform_per_step)

    cell = sw._eval_cell(
        grid="sabotage_uniform",
        family="outlier",
        family_params={"accel_mag": 1.0},
        T=0.2,
        beta=100.0,
        delta=0.5,
        seed=42,
    )
    assert not cell.cell_pass
    # Either the ratio gate or the alignment hit must have fired.
    assert any(
        "ratio" in r or "alignment" in r for r in cell.failure_reasons
    )


# --------------------------------------------------------------------------- #
# Statistical-significance gate — Wilson CIs on the 1320-cell primary grid
# (DESIGN §5.1 + §6.1 — ties the regression suite to a stated bound)
# --------------------------------------------------------------------------- #


def test_primary_seeds_default_count_is_60():
    """The audit fixed the seed count at 60 — 22 configs × 60 seeds =
    1320 cells. Pinned so a future tweak that quietly halves the seeds
    fails the suite instead of silently halving the certification bar."""
    assert len(PRIMARY_SEEDS) == 60
    assert len(set(PRIMARY_SEEDS)) == 60   # deterministic + unique
    assert PRIMARY_SEEDS[0] == 42 and PRIMARY_SEEDS[-1] == 101


def test_legacy_primary_seeds_is_three():
    """Legacy 3-seed tuple is preserved for callers that explicitly want a
    smoke run (e.g. CI sanity checks). No internal call site uses it."""
    assert LEGACY_PRIMARY_SEEDS == (42, 43, 44)


def test_primary_grid_default_emits_1320_cells():
    cells = run_primary_grid()
    assert len(cells) == 1320


def test_wilson_ci_zero_total_returns_unit_interval():
    low, high = wilson_ci(0, 0)
    assert (low, high) == (0.0, 1.0)


def test_wilson_ci_textbook_n_60_perfect_pass():
    """At n=60 with 60-of-60 pass and z=WILSON_Z_95, the Wilson lower
    bound is ~0.940. Pinned: this is the cleanest-kernel ceiling on
    what the primary-grid regression suite can certify at the current N."""
    low, high = wilson_ci(60, 60)
    assert low == pytest.approx(0.93982814785791, abs=1e-9)
    assert high == pytest.approx(1.0, abs=1e-9)


def test_wilson_ci_textbook_n_60_one_failure():
    """One statistical failure (59/60 pass) keeps the lower bound at
    ~0.9114 — the floor is calibrated so this stays ABOVE 0.90."""
    low, _ = wilson_ci(59, 60)
    assert low == pytest.approx(0.9114487027240993, abs=1e-9)
    assert low > CERTIFICATION_FLOOR


def test_wilson_ci_textbook_n_60_two_failures_drops_below_floor():
    """Two failures (58/60) takes the lower bound to ~0.8864, BELOW the
    0.90 floor. The floor is calibrated so the second failure is the
    one that trips the alarm — exactly the regime the audit asked the
    suite to detect ("kernel flips pass→fail with a small kernel
    change")."""
    low, _ = wilson_ci(58, 60)
    assert low == pytest.approx(0.886362257256914, abs=1e-9)
    assert low < CERTIFICATION_FLOOR


def test_wilson_ci_rejects_invalid_successes():
    with pytest.raises(ValueError):
        wilson_ci(-1, 10)
    with pytest.raises(ValueError):
        wilson_ci(11, 10)


def test_wilson_lower_bound_matches_full_ci():
    successes, total = 47, 50
    low_full, _ = wilson_ci(successes, total)
    assert wilson_lower_bound(successes, total) == low_full


def test_per_config_pass_stats_groups_by_family_magnitude():
    """22 configs out of the primary grid: 1 baseline + 4 constant_bias +
    4 linear_drift + 4 accelerating + 4 noise_floor + 1 outlier +
    4 sensor_dropout. Each carries 60 seeds → n == 60."""
    cells = run_primary_grid()
    stats = per_config_pass_stats(cells)
    assert len(stats) == 22
    for s in stats:
        assert s.n == 60
        assert isinstance(s, PerConfigPassStat)
        # Magnitude labels are deterministic + non-empty.
        assert s.magnitude_label
        # Pass rate matches passed / n.
        assert s.pass_rate == pytest.approx(s.passed / s.n)
        # CI lower bound never exceeds upper bound.
        assert s.ci_low <= s.ci_high


def test_per_config_pass_stats_threshold_edge_accel_03_clears_floor():
    """The audit explicitly called out ``accelerating[accel_mag=0.3]``
    as the threshold-edge magnitude where the kernel is most likely to
    flip pass→fail under a small change. Pin the per-config CI lower
    bound for that specific cell so a regression registers as a tight
    statistical signal, not a vague aggregate slip."""
    cells = run_primary_grid()
    stats = per_config_pass_stats(cells)
    edge = next(
        s for s in stats if s.magnitude_label == "accelerating[accel_mag=0.3]"
    )
    assert edge.n == 60
    assert edge.passed == 60
    assert edge.ci_low > CERTIFICATION_FLOOR


def test_summarize_grid_exposes_per_config_ci_fields():
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    assert summary.certification_floor == CERTIFICATION_FLOOR
    assert summary.wilson_z == WILSON_Z_95
    assert summary.min_ci_lower_bound > 0.0
    assert isinstance(summary.cells_below_certification_floor, list)
    assert len(summary.per_config) > 0
    # Each per_config entry is a PerConfigPassStat with the documented attributes.
    sample = summary.per_config[0]
    for attr in (
        "family", "magnitude_label", "family_params",
        "n", "passed", "pass_rate", "ci_low", "ci_high",
        "meets_certification_floor",
    ):
        assert hasattr(sample, attr)


def test_primary_grid_meets_certification_floor():
    """The suite's stated statistical bound: every (family, magnitude)
    config's Wilson 95% CI lower bound must clear ``CERTIFICATION_FLOOR``.

    This is the §6.1 contract a SOTIF auditor would quote: "with 95%
    confidence, the true pass rate at every primary-grid config is at
    least 0.90." If a kernel change flips a config's empirical
    pass-count below the floor (e.g. 57/60 → ci_low ~0.86), this
    assertion fires with the offending magnitude label.
    """
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    below = summary.cells_below_certification_floor
    assert below == [], (
        f"{len(below)} config(s) below floor "
        f"{summary.certification_floor}: {below}; "
        f"min_ci_lower_bound = {summary.min_ci_lower_bound:.4f}"
    )
    # Belt and suspenders: at clean-kernel 60/60 the minimum Wilson
    # lower bound across the grid sits at ~0.94 (well clear of 0.90).
    assert summary.min_ci_lower_bound >= 0.93


def test_summarize_grid_stricter_floor_can_flag_clean_kernel():
    """The bound is configurable: lifting the floor to 0.95 (a stricter
    SOTIF programme) flags every config under the current N=60 cadence,
    because the 60/60 ceiling is ~0.94. This test pins that the floor
    actually binds — i.e. it is not vacuous."""
    cells = run_primary_grid()
    summary = summarize_grid(cells, certification_floor=0.95)
    assert len(summary.cells_below_certification_floor) == 22
    assert summary.min_ci_lower_bound < 0.95


def test_summarize_grid_flags_synthetic_below_floor_cell():
    """Sabotage: mark every accelerating[accel_mag=0.3] cell as failed.
    Empirical pass rate drops from 60/60 to 0/60 on that single config;
    every other config stays at 60/60. ``cells_below_certification_floor``
    must list exactly the sabotaged label.
    """
    cells = run_primary_grid()
    label = "accelerating[accel_mag=0.3]"
    for c in cells:
        if c.family == "accelerating" and c.family_params.get("accel_mag") == 0.3:
            c.cell_pass = False
    summary = summarize_grid(cells)
    assert summary.cells_below_certification_floor == [label]
    sabotaged = next(
        s for s in summary.per_config if s.magnitude_label == label
    )
    assert sabotaged.passed == 0
    assert sabotaged.ci_low < CERTIFICATION_FLOOR


# --------------------------------------------------------------------------- #
# Report writers — CSV + Markdown frozen artifacts (DESIGN §6.2)
# --------------------------------------------------------------------------- #


def test_grid_summary_to_csv_writes_header_and_one_row_per_config(tmp_path):
    """One row per (family, magnitude) config + one header row.
    22 configs ⇒ 23 lines."""
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    out = summary.to_csv(tmp_path / "grid.csv")
    assert out.exists()
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 23
    header = lines[0].split(",")
    assert header == [
        "family", "magnitude_label", "family_params",
        "n", "passed", "pass_rate", "ci_low", "ci_high",
        "meets_certification_floor",
    ]


def test_grid_summary_to_csv_quotes_special_characters(tmp_path):
    """Magnitude labels carry ``[`` and ``=`` — the CSV must round-trip
    cleanly through stdlib csv.reader."""
    import csv as _csv
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    out = summary.to_csv(tmp_path / "grid.csv")
    with open(out, "r", encoding="utf-8", newline="") as f:
        rows = list(_csv.DictReader(f))
    assert len(rows) == 22
    assert all(r["meets_certification_floor"] == "true" for r in rows)
    assert any(r["magnitude_label"] == "accelerating[accel_mag=0.3]" for r in rows)


def test_grid_summary_to_csv_records_failed_config(tmp_path):
    """A sabotaged config writes ``meets_certification_floor=false``
    in the CSV — the auditor can grep the failure without parsing markdown."""
    import csv as _csv
    cells = run_primary_grid()
    label = "accelerating[accel_mag=0.3]"
    for c in cells:
        if c.family == "accelerating" and c.family_params.get("accel_mag") == 0.3:
            c.cell_pass = False
    summary = summarize_grid(cells)
    out = summary.to_csv(tmp_path / "grid.csv")
    with open(out, "r", encoding="utf-8", newline="") as f:
        rows = list(_csv.DictReader(f))
    sabotaged = next(r for r in rows if r["magnitude_label"] == label)
    assert sabotaged["meets_certification_floor"] == "false"
    assert sabotaged["passed"] == "0"


def test_grid_summary_to_markdown_report_has_required_sections(tmp_path):
    """A regulator-friendly markdown report must include the headline
    gate, the per-config table, the per-family roll-up, the failed-
    config section, and the methodology block."""
    from datetime import datetime, timezone
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    out = summary.to_markdown_report(
        tmp_path / "report.md",
        generated_at=datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc),
    )
    md = out.read_text(encoding="utf-8")
    for section in (
        "# BCVF Characterization Grid",
        "## Headline gate",
        "## Per-(family, magnitude) results",
        "## Per-family roll-up",
        "## Configs below the certification floor",
        "## Methodology",
    ):
        assert section in md, f"missing section: {section}"
    # Headline numbers appear in plain text.
    assert "PASS" in md
    assert "0.90" in md   # certification floor
    assert "0.9398" in md or "0.9399" in md   # min CI lower bound (~0.940)


def test_grid_summary_to_markdown_report_lists_failing_config(tmp_path):
    """The failed-config section explicitly names the offending
    magnitude — an auditor can read the failure without re-running
    the sweep."""
    cells = run_primary_grid()
    label = "accelerating[accel_mag=0.3]"
    for c in cells:
        if c.family == "accelerating" and c.family_params.get("accel_mag") == 0.3:
            c.cell_pass = False
    summary = summarize_grid(cells)
    out = summary.to_markdown_report(tmp_path / "report.md")
    md = out.read_text(encoding="utf-8")
    assert label in md
    # The headline gate flips to FAIL when at least one config is below.
    assert "FAIL" in md


def test_grid_summary_markdown_render_is_deterministic():
    """Same summary + same generated_at ⇒ byte-identical markdown."""
    from datetime import datetime, timezone
    from symbolu_robotics.bcvf_autonomous.characterization import (
        render_grid_markdown,
    )
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    ts = datetime(2026, 5, 4, 12, 0, tzinfo=timezone.utc)
    a = render_grid_markdown(summary, generated_at=ts)
    b = render_grid_markdown(summary, generated_at=ts)
    assert a == b


def test_grid_summary_to_csv_creates_parent_directories(tmp_path):
    """The writer must mkdir parents on the way down — auditors don't
    pre-create result directories before invoking the writer."""
    cells = run_primary_grid()
    summary = summarize_grid(cells)
    nested = tmp_path / "deep" / "nested" / "audit_pack"
    out = summary.to_csv(nested / "grid.csv")
    assert out.exists()

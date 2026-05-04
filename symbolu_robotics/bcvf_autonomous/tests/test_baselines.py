"""Tests for the apples-to-apples baseline shootout."""

from __future__ import annotations

import json

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous.baselines import (
    AnchorArbitrator,
    ArbitrationResult,
    BCVFArbitrator,
    EKFArbitrator,
    EKFConfig,
    MajorityVoteArbitrator,
    run_shootout,
    validate_trajectories,
)
from symbolu_robotics.bcvf_autonomous.baselines.shootout import (
    _attribution_top_half,
    _ground_truth_trajectory,
)
from symbolu_robotics.bcvf_autonomous.characterization.traces import (
    generate_trace,
)


# --------------------------------------------------------------------------- #
# validate_trajectories
# --------------------------------------------------------------------------- #


def test_validate_rejects_wrong_shape():
    with pytest.raises(ValueError):
        validate_trajectories(np.zeros((4, 10), dtype=np.float64))
    with pytest.raises(ValueError):
        validate_trajectories(np.zeros((1, 10, 3), dtype=np.float64))
    with pytest.raises(ValueError):
        validate_trajectories(np.zeros((3, 2, 3), dtype=np.float64))


# --------------------------------------------------------------------------- #
# Anchor arbitrator
# --------------------------------------------------------------------------- #


def test_anchor_returns_anchor_trajectory_unchanged():
    trajs = np.random.default_rng(0).normal(size=(3, 10, 3))
    a = AnchorArbitrator(anchor_idx=1)
    result = a.arbitrate(trajs)
    np.testing.assert_array_equal(result.consensus, trajs[1])


def test_anchor_attribution_is_all_zero():
    trajs = np.zeros((3, 10, 3))
    result = AnchorArbitrator().arbitrate(trajs)
    assert (result.attribution == 0).all()


def test_anchor_index_validation():
    trajs = np.zeros((3, 10, 3))
    with pytest.raises(IndexError):
        AnchorArbitrator(anchor_idx=5).arbitrate(trajs)


# --------------------------------------------------------------------------- #
# Majority vote arbitrator
# --------------------------------------------------------------------------- #


def test_majority_vote_finds_two_of_three():
    """Two predictors at the origin, one far away — majority is the
    pair near the origin."""
    H = 5
    trajs = np.zeros((3, H, 3))
    trajs[0] = 0.0      # nominal
    trajs[1] = 0.0      # nominal (matches predictor 0)
    trajs[2, :, 0] = 5.0  # outlier
    result = MajorityVoteArbitrator(cluster_radius=0.5).arbitrate(trajs)
    np.testing.assert_allclose(
        result.consensus[:, 0], 0.0, atol=1e-9,
    )
    # Predictor 2 should have largest attribution (5 m × H ticks).
    assert result.attribution[2] > result.attribution[0]
    assert result.attribution[2] > result.attribution[1]


def test_majority_vote_rejects_zero_radius():
    with pytest.raises(ValueError):
        MajorityVoteArbitrator(cluster_radius=0.0)


# --------------------------------------------------------------------------- #
# EKF arbitrator
# --------------------------------------------------------------------------- #


def test_ekf_consensus_is_smooth_on_nominal_data():
    """All three predictors agree → EKF consensus stays at the agreed
    pose with small Mahalanobis distances."""
    H = 20
    trajs = np.zeros((3, H, 3))
    trajs[..., 0] = (np.arange(H) * 0.5)[None, :]
    rng = np.random.default_rng(7)
    trajs += rng.normal(scale=0.01, size=trajs.shape)
    result = EKFArbitrator(EKFConfig(dt=0.1)).arbitrate(trajs)
    # EKF state should track the predictor mean closely.
    err = np.linalg.norm(
        result.consensus[:, :2] - trajs.mean(axis=0)[:, :2], axis=-1
    )
    assert err.max() < 0.5
    # Mahalanobis attribution should be small (no outlier).
    assert result.attribution.max() < 5.0


def test_ekf_flags_outlier_predictor_via_mahalanobis():
    H = 20
    trajs = np.zeros((3, H, 3))
    trajs[..., 0] = (np.arange(H) * 0.5)[None, :]
    # Predictor 2 is far off the consensus.
    trajs[2, :, 1] += 5.0
    result = EKFArbitrator(EKFConfig(dt=0.1)).arbitrate(trajs)
    assert result.attribution[2] > result.attribution[0]
    assert result.attribution[2] > result.attribution[1]


# --------------------------------------------------------------------------- #
# BCVF arbitrator
# --------------------------------------------------------------------------- #


def test_bcvf_arbitrator_consensus_shape():
    H = 20
    trajs = np.zeros((3, H, 3))
    trajs[..., 0] = (np.arange(H) * 0.5)[None, :]
    result = BCVFArbitrator().arbitrate(trajs)
    assert result.consensus.shape == (H, 3)
    assert result.attribution.shape == (3,)


def test_bcvf_arbitrator_lemma1_invariance_on_constant_bias():
    """BCVF's Lemma-1 invariance: constant offset between predictors
    produces zero per-predictor cost (and therefore uniform softmin
    weights — every predictor is equally trusted)."""
    bundle = generate_trace("constant_bias", M=3, H=50, seed=42)
    result = BCVFArbitrator().arbitrate(bundle.trajectories)
    # Attribution is per-predictor accumulated kernel cost; on
    # constant_bias under SECOND-order it must be exactly zero.
    assert result.attribution.max() < 1e-9


def test_bcvf_arbitrator_attributes_outlier_correctly():
    bundle = generate_trace("outlier", M=3, H=50, seed=42)
    result = BCVFArbitrator().arbitrate(bundle.trajectories)
    truth = bundle.truth_label
    assert truth is not None
    # Truth predictor should be in the top-half ranking.
    ranks = np.argsort(-result.attribution, kind="stable")
    pos = int(np.where(ranks == truth)[0][0]) + 1
    assert pos <= 2   # top-2 of 3


# --------------------------------------------------------------------------- #
# Shootout helpers
# --------------------------------------------------------------------------- #


def test_attribution_top_half_zero_attribution_is_miss():
    """All-zero attribution carries no information — must count as
    a miss regardless of truth_label, so AnchorArbitrator's floor
    stays at zero on every failure family."""
    assert not _attribution_top_half(np.zeros(3), truth_label=0)
    assert not _attribution_top_half(np.zeros(3), truth_label=2)


def test_attribution_top_half_top2_of_3():
    attr = np.array([1.0, 5.0, 3.0])   # ranks: 1 (5), 2 (3), 3 (1)
    assert _attribution_top_half(attr, truth_label=1)   # rank 1 ✓
    assert _attribution_top_half(attr, truth_label=2)   # rank 2 ✓
    assert not _attribution_top_half(attr, truth_label=0)  # rank 3 ✗


def test_ground_truth_trajectory_from_bundle():
    bundle = generate_trace("baseline", M=3, H=20, dt=0.1, base_velocity=5.0)
    truth = _ground_truth_trajectory(bundle)
    assert truth.shape == (20, 3)
    np.testing.assert_allclose(truth[1, 0] - truth[0, 0], 0.5, atol=1e-12)


# --------------------------------------------------------------------------- #
# Shootout end-to-end + headline gates
# --------------------------------------------------------------------------- #


def test_run_shootout_writes_artifacts(tmp_path):
    result = run_shootout(N=2, output_dir=tmp_path)
    assert (tmp_path / "shootout.csv").exists()
    assert (tmp_path / "shootout.json").exists()
    assert (tmp_path / "shootout_report.md").exists()
    payload = json.loads((tmp_path / "shootout.json").read_text())
    # 4 arbitrators × 7 families = 28 summaries
    assert payload["n_cells"] == 4 * 7 * 2
    assert len(payload["summaries"]) == 4 * 7


def test_shootout_bcvf_wins_lemma1_false_attribution(tmp_path):
    """The BD-grade headline: BCVF false-attributes essentially zero on
    constant_bias and linear_drift, while EKF and MajorityVote do not.

    This test pins the comparison the v0.7 brief promotes from the
    "negative space" (claimed but unmeasured) to a measured result."""
    result = run_shootout(N=5, output_dir=tmp_path)
    by = {(s.arbitrator, s.family): s for s in result.summaries}

    bcvf_const = by[("BCVF", "constant_bias")]
    ekf_const = by[("EKF", "constant_bias")]
    majority_const = by[("MajorityVote", "constant_bias")]
    # BCVF false-attribution on constant_bias must be <= 1e-6 (Lemma 1).
    assert bcvf_const.median_false_attribution < 1e-6
    # EKF must be materially higher.
    assert ekf_const.median_false_attribution > 0.1
    # Majority must be MUCH higher (the catastrophic case).
    assert majority_const.median_false_attribution > 1.0


def test_shootout_anchor_floor_is_zero_on_failure_families(tmp_path):
    """The null baseline must score zero on every failure family —
    that's the floor the other three must beat to earn their keep."""
    result = run_shootout(N=3, output_dir=tmp_path)
    by = {(s.arbitrator, s.family): s for s in result.summaries}
    for fam in ("outlier", "sensor_dropout", "accelerating"):
        assert by[("Anchor", fam)].attribution_hit_rate == 0.0


def test_shootout_bcvf_attributes_failure_families(tmp_path):
    """BCVF must hit on every failure family at top-2 of 3 ranking
    (the v0.7 brief's "BCVF attributes correctly" claim)."""
    result = run_shootout(N=5, output_dir=tmp_path)
    by = {(s.arbitrator, s.family): s for s in result.summaries}
    for fam in ("outlier", "sensor_dropout", "accelerating"):
        assert by[("BCVF", fam)].attribution_hit_rate >= 0.8, (
            f"BCVF hit rate on {fam} = "
            f"{by[('BCVF', fam)].attribution_hit_rate}"
        )


def test_shootout_consensus_error_finite(tmp_path):
    """No arbitrator should produce NaN/inf consensus errors on any family."""
    result = run_shootout(N=2, output_dir=tmp_path)
    for s in result.summaries:
        assert np.isfinite(s.median_consensus_error)
        assert np.isfinite(s.median_per_tick_us)

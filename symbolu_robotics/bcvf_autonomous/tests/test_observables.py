"""Tests for the BCVF Autonomous observables framework."""

from __future__ import annotations

import math

import numpy as np
import pytest

from symbolu_robotics.bcvf_autonomous import (
    BCVFConfig,
    BCVFPerStepMaxObservable,
    BCVFPredictorPerStepMaxObservable,
    CoherenceAnchoredBCVFObservable,
    CostOrder,
    EnsembleHeadingEntropyObservable,
    EnsembleSpreadObservable,
    PredictorAgreementObservable,
    UncertaintyGatedBCVFPerStepMaxObservable,
    classify_observable,
    compute_bcvf_cost,
    compute_bcvf_per_step,
    probe_observable,
)
from symbolu_robotics.bcvf_autonomous.observables.kernel_per_step import (
    stencil_align_to_signal,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _straight_traj(n_steps: int, x_offset: float = 0.0, y_offset: float = 0.0) -> np.ndarray:
    xs = np.arange(n_steps, dtype=np.float64) + x_offset
    ys = np.full(n_steps, y_offset, dtype=np.float64)
    th = np.zeros(n_steps, dtype=np.float64)
    return np.stack([xs, ys, th], axis=-1)


def _ensemble(*trajectories: np.ndarray) -> np.ndarray:
    return np.stack(trajectories, axis=0)


# --------------------------------------------------------------------------- #
# compute_bcvf_per_step
# --------------------------------------------------------------------------- #


def test_compute_bcvf_per_step_reproduces_aggregate():
    """The horizon-sum of per_step_total equals compute_bcvf_cost.total_cost."""
    np.random.seed(42)
    H = 30
    M = 3
    base = _straight_traj(H)
    trajs = np.stack(
        [base + np.random.randn(H, 3) * 0.05 for _ in range(M)], axis=0
    )
    cfg = BCVFConfig(use_anchor_pairing=False)

    breakdown = compute_bcvf_per_step(trajs, cfg)
    aggregate = compute_bcvf_cost([trajs[m] for m in range(M)], cfg)

    assert breakdown.per_step_total.sum() == pytest.approx(
        aggregate.total_cost, rel=1e-6, abs=1e-9
    )


def test_compute_bcvf_per_step_attribution_consistent():
    """per_step_per_predictor.sum(axis=1) == 2 * per_step_total (each pair attributed twice)."""
    H = 20
    base = _straight_traj(H)
    trajs = _ensemble(base, base + 0.1, base - 0.1)
    cfg = BCVFConfig(use_anchor_pairing=False)
    breakdown = compute_bcvf_per_step(trajs, cfg)

    np.testing.assert_allclose(
        breakdown.per_step_per_predictor.sum(axis=0),
        2.0 * breakdown.per_step_total,
        atol=1e-9,
    )


def test_compute_bcvf_per_step_stencil_lengths():
    H = 12
    trajs = _ensemble(_straight_traj(H), _straight_traj(H, y_offset=0.1))
    for order, expected in [
        (CostOrder.ZEROTH, H),
        (CostOrder.FIRST, H - 1),
        (CostOrder.SECOND, H - 2),
    ]:
        cfg = BCVFConfig(cost_order=order, use_anchor_pairing=False)
        breakdown = compute_bcvf_per_step(trajs, cfg)
        assert breakdown.per_step_total.shape == (expected,)


def test_stencil_align_to_signal_shapes():
    arr = np.arange(10, dtype=np.float64)
    assert stencil_align_to_signal(arr, CostOrder.ZEROTH).shape == (10,)
    assert stencil_align_to_signal(arr, CostOrder.FIRST).shape == (9,)
    assert stencil_align_to_signal(arr, CostOrder.SECOND).shape == (8,)


# --------------------------------------------------------------------------- #
# Agreement
# --------------------------------------------------------------------------- #


def test_agreement_unanimous_is_zero_disagreement():
    H = 10
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    obs = PredictorAgreementObservable()
    value = obs.observe(trajs)
    assert value.scalar == pytest.approx(0.0)
    assert value.metadata["agreement_fraction"] == pytest.approx(1.0)


def test_agreement_one_outlier_predictor_flags_disagreement():
    H = 10
    base = _straight_traj(H)
    outlier = base.copy()
    outlier[:, 0] += 5.0  # well outside any tolerance
    trajs = _ensemble(base, base.copy(), outlier)
    obs = PredictorAgreementObservable(position_tolerance=0.5)
    value = obs.observe(trajs)
    assert value.scalar > 0.9
    assert value.per_predictor[2] > value.per_predictor[0]


# --------------------------------------------------------------------------- #
# Ensemble spread / heading entropy
# --------------------------------------------------------------------------- #


def test_ensemble_spread_zero_for_identical_predictors():
    H = 10
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    value = EnsembleSpreadObservable().observe(trajs)
    assert value.scalar == pytest.approx(0.0)


def test_ensemble_spread_increases_with_outlier():
    H = 10
    base = _straight_traj(H)
    a = EnsembleSpreadObservable().observe(_ensemble(base, base + 0.1, base - 0.1))
    b = EnsembleSpreadObservable().observe(_ensemble(base, base + 1.0, base - 1.0))
    assert b.scalar > a.scalar


def test_heading_entropy_zero_when_all_aligned():
    H = 10
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    value = EnsembleHeadingEntropyObservable().observe(trajs)
    assert value.scalar == pytest.approx(0.0)


def test_heading_entropy_high_when_split():
    H = 10
    base = _straight_traj(H)
    pos = base.copy()
    pos[:, 2] = math.pi / 2
    neg = base.copy()
    neg[:, 2] = -math.pi / 2
    trajs = _ensemble(base, pos, neg)
    value = EnsembleHeadingEntropyObservable().observe(trajs)
    assert value.scalar > 0.5


# --------------------------------------------------------------------------- #
# BCVF per-step observables
# --------------------------------------------------------------------------- #


def test_bcvf_per_step_max_zero_for_aligned_predictors():
    H = 20
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    obs = BCVFPerStepMaxObservable()
    value = obs.observe(trajs)
    assert value.scalar == pytest.approx(0.0)


def test_bcvf_per_step_max_lights_up_on_acceleration():
    H = 20
    base = _straight_traj(H)
    # Inject an accelerating disagreement on one predictor.
    bad = base.copy()
    bad[:, 1] += 0.001 * np.arange(H) ** 2
    trajs = _ensemble(base, base.copy(), bad)
    cfg = BCVFConfig(use_anchor_pairing=False)
    obs = BCVFPerStepMaxObservable(cfg)
    value = obs.observe(trajs)
    assert value.scalar > 0.0
    assert value.metadata["argmax_step"] >= 0


def test_bcvf_predictor_per_step_max_attributes_to_outlier():
    H = 20
    base = _straight_traj(H)
    bad = base.copy()
    bad[:, 1] += 0.001 * np.arange(H) ** 2
    trajs = _ensemble(base, base.copy(), bad)
    cfg = BCVFConfig(use_anchor_pairing=False)

    bad_obs = BCVFPredictorPerStepMaxObservable(2, cfg)
    good_obs = BCVFPredictorPerStepMaxObservable(0, cfg)
    bad_value = bad_obs.observe(trajs)
    good_value = good_obs.observe(trajs)

    assert bad_value.scalar > good_value.scalar


def test_bcvf_predictor_per_step_max_index_validation():
    H = 10
    trajs = _ensemble(_straight_traj(H), _straight_traj(H, y_offset=0.1))
    obs = BCVFPredictorPerStepMaxObservable(5)
    with pytest.raises(IndexError):
        obs.observe(trajs)


# --------------------------------------------------------------------------- #
# Coherence-anchored
# --------------------------------------------------------------------------- #


def test_coherence_anchored_pure_stability_when_no_ground_truth():
    H = 20
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    obs = CoherenceAnchoredBCVFObservable()
    value = obs.observe(trajs)
    # No BCVF cost + no ground truth ⇒ stability = 1.0, alignment = 1.0.
    assert value.scalar == pytest.approx(1.0)
    assert value.metadata["alignment"] == pytest.approx(1.0)
    assert math.isnan(value.metadata["mean_alignment_error"])


def test_coherence_anchored_drops_when_ground_truth_diverges():
    H = 20
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy(), base.copy())
    near_gt = base + np.array([0.01, 0.01, 0.0])
    far_gt = base + np.array([5.0, 5.0, 0.0])
    obs = CoherenceAnchoredBCVFObservable(alignment_scale=1.0)
    near = obs.observe(trajs, ground_truth=near_gt)
    far = obs.observe(trajs, ground_truth=far_gt)
    assert near.scalar > far.scalar


def test_coherence_anchored_validates_ground_truth_shape():
    H = 10
    base = _straight_traj(H)
    trajs = _ensemble(base, base.copy())
    bad_gt = np.zeros((H + 1, 3))
    obs = CoherenceAnchoredBCVFObservable()
    with pytest.raises(ValueError):
        obs.observe(trajs, ground_truth=bad_gt)


# --------------------------------------------------------------------------- #
# Uncertainty-gated
# --------------------------------------------------------------------------- #


def test_uncertainty_gated_zero_when_ensemble_tight():
    H = 20
    base = _straight_traj(H)
    trajs = _ensemble(base, base + 0.001, base - 0.001)
    obs = UncertaintyGatedBCVFPerStepMaxObservable(spread_threshold=0.5)
    value = obs.observe(trajs)
    assert value.scalar == pytest.approx(0.0)
    assert value.metadata["n_uncertain_steps"] == 0


def test_uncertainty_gated_picks_up_disagreement_when_spread_exceeds_tau():
    H = 20
    base = _straight_traj(H)
    # All predictors clearly diverge
    a = base.copy()
    b = base.copy()
    b[:, 1] += np.linspace(0.0, 2.0, H)
    c = base.copy()
    c[:, 1] -= np.linspace(0.0, 2.0, H)
    trajs = _ensemble(a, b, c)
    cfg = BCVFConfig(use_anchor_pairing=False)
    obs = UncertaintyGatedBCVFPerStepMaxObservable(cfg, spread_threshold=0.3)
    value = obs.observe(trajs)
    assert value.scalar >= 0.0
    assert value.metadata["n_uncertain_steps"] > 0


# --------------------------------------------------------------------------- #
# Probe harness
# --------------------------------------------------------------------------- #


def test_probe_observable_returns_null_below_min_n():
    obs = BCVFPerStepMaxObservable()
    H = 10
    samples = []
    for _ in range(5):
        base = _straight_traj(H)
        samples.append((_ensemble(base, base, base), False, None))
    report = probe_observable(obs, samples)
    assert report.classification == "NULL"
    assert report.n_ticks == 5


def test_probe_observable_safety_correlated_on_clean_signal():
    """Construct ticks where positive label ⇔ injected disagreement.
    BCVFPerStepMaxObservable should classify as SAFETY_CORRELATED."""
    np.random.seed(0)
    H = 12
    samples = []
    for k in range(60):
        base = _straight_traj(H)
        if k % 2 == 0:
            # nominal
            trajs = _ensemble(
                base + np.random.randn(H, 3) * 0.01,
                base + np.random.randn(H, 3) * 0.01,
                base + np.random.randn(H, 3) * 0.01,
            )
            label = False
        else:
            # adversarial — accelerating disagreement
            bad = base.copy()
            bad[:, 1] += 0.005 * np.arange(H) ** 2
            trajs = _ensemble(base, base, bad)
            label = True
        samples.append((trajs, label, None))

    report = probe_observable(
        BCVFPerStepMaxObservable(BCVFConfig(use_anchor_pairing=False)),
        samples,
    )
    assert report.classification == "SAFETY_CORRELATED"
    assert report.auc > 0.6


def test_classify_observable_bands():
    assert classify_observable(0.7, 100) == "SAFETY_CORRELATED"
    assert classify_observable(0.5, 100) == "UNCORRELATED"
    assert classify_observable(0.4, 100) == "ANTI_CORRELATED"
    assert classify_observable(0.7, 10) == "NULL"


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def test_observable_rejects_too_few_predictors():
    H = 10
    trajs = _straight_traj(H).reshape(1, H, 3)
    with pytest.raises(ValueError):
        EnsembleSpreadObservable().observe(trajs)


def test_observable_rejects_too_short_horizon():
    trajs = np.zeros((2, 2, 3))
    # Stencil-using observables require H >= 3.
    with pytest.raises(ValueError):
        BCVFPerStepMaxObservable().observe(trajs)


def test_pure_ensemble_observables_accept_short_horizon():
    """Agreement / spread / heading entropy do not consume the BCVF
    stencil and must accept H=1 and H=2 horizons (a smoke-test check
    or single-frame audit should not be blocked by validation tuned
    for stencil-using observables)."""
    short_h2 = np.zeros((3, 2, 3))
    short_h1 = np.zeros((3, 1, 3))
    PredictorAgreementObservable().observe(short_h2)
    PredictorAgreementObservable().observe(short_h1)
    EnsembleSpreadObservable().observe(short_h2)
    EnsembleSpreadObservable().observe(short_h1)
    EnsembleHeadingEntropyObservable().observe(short_h2)
    EnsembleHeadingEntropyObservable().observe(short_h1)

"""Tests for the LLT-Kalman predictor-trust variant (evaluation-only).

Run: python -m pytest robotics_reliability_bench/test_llt_kalman_trust.py -q
"""
from __future__ import annotations

import numpy as np
import pytest

from robotics_reliability_bench import fault_corpus as fc
from robotics_reliability_bench.detectors import (BaselineDetector, FusionDetector,
                                                  LLTKalmanDetector)
from robotics_reliability_bench.llt_kalman_trust import (LLTKalmanConfig,
                                                         LLTKalmanTrust,
                                                         _robust_obs_noise,
                                                         llt_filter_axis)
from robotics_reliability_bench.predictor_trust_baseline import TrustState


# ---- filter primitives ------------------------------------------------------

def test_llt_innovations_white_under_linear_drift():
    """A constant slope must be absorbed by the slope state: after burn-in the
    normalized innovations of a noiseless ramp are ~0, not growing."""
    H = 60
    r = 0.05 * np.arange(H)
    fresh = np.ones(H, dtype=bool)
    tr = llt_filter_axis(r, fresh, R=0.05 ** 2, cfg=LLTKalmanConfig())
    assert np.nanmax(tr.nis[30:]) < 0.5
    # ... while the level state tracks the ramp itself
    assert abs(tr.level[-1] - r[-1]) < 0.05


def test_llt_missing_observations_predict_only():
    H = 40
    r = np.full(H, 0.3)
    fresh = np.ones(H, dtype=bool)
    fresh[10:20] = False
    tr = llt_filter_axis(r, fresh, R=0.01, cfg=LLTKalmanConfig())
    assert np.all(np.isnan(tr.nis[10:20]))
    assert np.all(np.isfinite(tr.level))
    # variance must grow while blind and shrink again after an update
    assert tr.level_var[19] > tr.level_var[9]
    assert tr.level_var[25] < tr.level_var[19]


def test_robust_noise_ignores_offset_and_drift():
    rng = np.random.default_rng(0)
    base = rng.normal(0.0, 0.05, size=200)
    fresh = np.ones(200, dtype=bool)
    s0 = _robust_obs_noise(base, fresh, floor=0.001)
    s_off = _robust_obs_noise(base + 5.0, fresh, floor=0.001)
    s_drift = _robust_obs_noise(base + 0.1 * np.arange(200), fresh, floor=0.001)
    assert abs(s0 - 0.05) < 0.015
    assert abs(s_off - s0) < 1e-9
    assert abs(s_drift - s0) < 0.015


# ---- detector behaviour on the corpus -------------------------------------

@pytest.mark.parametrize("seed", range(5))
def test_tune_benign_families_are_not_suspect(seed):
    """Asserted on TUNE benign families only. ``calibration_drift`` is a
    held-out TEST family: its false-alarm rate under the frozen config is
    reported by ``run_incremental_value``, not pinned here, so the frozen
    thresholds are never adjusted against TEST behaviour."""
    det = LLTKalmanTrust()
    for fam in ("gaussian_noise", "noisy_unbiased"):
        b = fc.generate(fam, seed=seed)
        d = det.evaluate(b.trajectories, b.valid_masks)
        assert d.flagged is None, (fam, seed, d.reason)
        assert all(r.state is not TrustState.SUSPECT for r in d.per_predictor), fam


@pytest.mark.parametrize("fam", ["constant_bias", "linear_drift", "accelerating",
                                 "abrupt_jump", "stuck_sensor", "precise_biased",
                                 "delayed_predictor"])
def test_single_culprit_faults_are_attributed(fam):
    det = LLTKalmanTrust()
    for seed in range(3):
        b = fc.generate(fam, seed=seed)
        d = det.evaluate(b.trajectories, b.valid_masks)
        assert d.flagged == b.truth_label, (fam, seed, d.reason)
        assert d.detection_tick is not None
        assert d.detection_tick >= (b.onset_tick or 0)


def test_all_wrong_is_silent():
    det = LLTKalmanTrust()
    b = fc.generate("all_wrong", seed=0)
    d = det.evaluate(b.trajectories, b.valid_masks)
    assert d.flagged is None
    assert d.system_state is TrustState.TRUSTED  # no cross-disagreement to see


def test_stale_predictor_abstains_per_predictor():
    det = LLTKalmanTrust()
    b = fc.generate("stale_predictor", seed=0)
    d = det.evaluate(b.trajectories, b.valid_masks)
    assert d.per_predictor[b.truth_label].state is TrustState.ABSTAIN
    assert b.truth_label not in d.trusted


def test_global_abstain_when_no_trusted_majority():
    det = LLTKalmanTrust()
    b = fc.generate("constant_bias", seed=0)
    trajs = b.trajectories.copy()
    trajs[0, :, 1] -= 0.6   # now two of three carry opposite biases
    d = det.evaluate(trajs)
    assert d.system_state is TrustState.ABSTAIN
    assert d.flagged is None


def test_strict_tick_never_earlier_than_accelerated():
    fast = LLTKalmanTrust(LLTKalmanConfig(cusum_accelerates_tick=True))
    strict = LLTKalmanTrust(LLTKalmanConfig(cusum_accelerates_tick=False))
    for fam in ("abrupt_jump", "accelerating", "constant_bias"):
        b = fc.generate(fam, seed=1)
        tf = fast.evaluate(b.trajectories).detection_tick
        ts = strict.evaluate(b.trajectories).detection_tick
        assert tf is not None and ts is not None
        assert tf <= ts


def test_deterministic_rerun_identity():
    det = LLTKalmanTrust()
    b = fc.generate("accelerating", seed=3)
    d1 = det.evaluate(b.trajectories)
    d2 = det.evaluate(b.trajectories)
    assert [r.suspicion for r in d1.per_predictor] == [r.suspicion for r in d2.per_predictor]
    assert d1.detection_tick == d2.detection_tick


def test_arbitrator_protocol_shape():
    det = LLTKalmanTrust()
    b = fc.generate("constant_bias", seed=0)
    res = det.arbitrate(b.trajectories)
    assert res.consensus.shape == (50, 3)
    assert res.attribution.shape == (3,)
    assert int(np.argmax(res.attribution)) == b.truth_label


# ---- adapter + fusion contract --------------------------------------------

def test_adapter_matches_baseline_output_contract():
    b = fc.generate("stale_predictor", seed=0)
    base = BaselineDetector().detect(b)
    llt = LLTKalmanDetector().detect(b)
    assert set(vars(base)) == set(vars(llt))
    assert llt.detected and llt.metadata["stale_excluded"] == [b.truth_label]


def test_fusion_over_llt_never_invents_detection():
    class _NeverBCVF:
        name = "never"
        def detect(self, b):
            from robotics_reliability_bench.detectors import DetectorOutput
            return DetectorOutput("never", detected=True, flagged=1,
                                  detection_tick=0, abstained=False, signal=9.0)
    fusion = FusionDetector(LLTKalmanDetector(), _NeverBCVF())
    b = fc.generate("gaussian_noise", seed=0)
    out = fusion.detect(b)
    assert out.detected is False and out.flagged is None

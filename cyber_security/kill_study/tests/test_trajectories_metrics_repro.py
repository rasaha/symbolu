"""Trajectory families, metric sanity, and reproducibility."""

from __future__ import annotations

import numpy as np

from cyber_security.kill_study.config import (
    ALL_FAMILIES,
    ATTACK_FAMILIES,
    LEGIT_FAMILIES,
    StudyConfig,
)
from cyber_security.kill_study.detectors import ARMS, ARM_ORDER
from cyber_security.kill_study.metrics import (
    NO_CHALLENGE,
    damage_weighted_loss,
    detected_and_delay,
)
from cyber_security.kill_study.trajectories import generate

CFG = StudyConfig()


def _gen(fam, seed=0):
    return generate(fam, seed=seed, cfg=CFG, sigma=0.3, separation=4.0,
                    ramp_duration=90.0, missing_rate=0.0)


def test_all_families_generate_expected_shapes_and_flags():
    for fam in ALL_FAMILIES:
        ev = _gen(fam)
        assert ev.z.shape == (CFG.horizon, CFG.embed_dim)
        assert ev.mask.shape == (CFG.horizon,)
        if fam in LEGIT_FAMILIES:
            assert not ev.is_attack
        if fam in ATTACK_FAMILIES:
            assert ev.is_attack


def test_legit_drift_stays_off_the_attack_axis():
    ev = _gen("F03_linear_drift")
    # benign drift is on axis 1; attack axis is axis 0 -> low axis-0 signal mean
    assert abs(np.nanmean(ev.z[:, 0])) < abs(np.nanmean(ev.z[:, 1]))


def test_sparse_family_has_missing_data():
    ev = _gen("F12_sparse_missing_evidence")
    assert ev.mask.mean() < 1.0
    assert np.isnan(ev.z[~ev.mask]).all()


def test_detector_aware_minimises_peak_second_order_vs_abrupt():
    from cyber_security.kill_study.detectors import arm_F

    aware = arm_F(_gen("F10_detector_aware_optimized"), CFG).s_raw.max()
    abrupt = arm_F(_gen("F06_abrupt_takeover"), CFG).s_raw.max()
    assert aware < abrupt


def test_damage_weighted_loss_monotone_in_delay():
    onset = 80
    fast = damage_weighted_loss(onset + 1, onset, CFG)
    slow = damage_weighted_loss(onset + 30, onset, CFG)
    never = damage_weighted_loss(NO_CHALLENGE, onset, CFG)
    assert fast < slow <= never


def test_detected_and_delay_semantics():
    assert detected_and_delay(85, 80) == (True, 5)
    assert detected_and_delay(NO_CHALLENGE, 80)[0] is False
    # a challenge before onset does not count as detection
    assert detected_and_delay(70, 80)[0] is False


def test_generation_is_reproducible():
    a = _gen("F07_slow_linear_takeover", seed=99)
    b = _gen("F07_slow_linear_takeover", seed=99)
    assert np.array_equal(np.nan_to_num(a.z), np.nan_to_num(b.z))


def test_arm_outputs_are_reproducible():
    ev = _gen("F06_abrupt_takeover", seed=5)
    for key in ARM_ORDER:
        o1 = ARMS[key](ev, CFG)
        o2 = ARMS[key](ev, CFG)
        assert np.allclose(o1.s_norm, o2.s_norm, atol=1e-12)

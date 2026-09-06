"""Tests for the A2 realistic-noise pilot corpus builder (evaluation-only).

Run: python -m pytest robotics_reliability_bench/test_a2_realistic_pilot.py -q
"""
from __future__ import annotations

import numpy as np
import pytest

from robotics_reliability_bench import a2_realistic_pilot as p
from robotics_reliability_bench import fault_corpus as fc


@pytest.mark.parametrize("fam", list(fc.FAMILIES))
def test_r1_bundle_shape_labels_determinism(fam):
    b1 = p.r1_bundle(fam, 200)
    b2 = p.r1_bundle(fam, 200)
    ref = fc.generate(fam, seed=0)
    assert b1.trajectories.shape == (p.R1_M, p.R1_T, 3)
    assert np.all(np.isfinite(b1.trajectories))
    assert np.array_equal(b1.trajectories, b2.trajectories)
    # labels are the corpus's, not re-derived
    assert (b1.truth_label, b1.onset_tick, b1.harm_class, b1.fault_active) == \
           (ref.truth_label, ref.onset_tick, ref.harm_class, ref.fault_active)
    if b1.valid_masks is not None:
        assert b1.valid_masks.shape == (p.R1_M, p.R1_T)


def test_r1_nominal_is_realistic_not_iid():
    """AR(1) alpha=0.8 must leave lag-1 autocorrelation in the noise."""
    b = p.r1_bundle("gaussian_noise", 201)
    y = b.trajectories[0, :, 1]
    y = y - y.mean()
    rho = float(np.dot(y[:-1], y[1:]) / np.dot(y, y))
    assert rho > 0.5


def test_r1_dropouts_hold_value_and_mask():
    seeds_with = [s for s in p.A2_SEEDS if p.r1_bundle("gaussian_noise", s).valid_masks is not None]
    assert seeds_with, "expected some seeds to carry dropouts at P=0.2"
    b = p.r1_bundle("gaussian_noise", seeds_with[0])
    m, t = np.argwhere(~b.valid_masks)[0]
    held = b.trajectories[m, t:t + p.DROPOUT_LEN, :]
    assert np.allclose(held, held[0])


@pytest.mark.parametrize("fam", p.R2_FAMILIES)
def test_r2_bundle_shape_and_target(fam):
    b = p.r2_bundle(fam, 200)
    assert b.trajectories.shape == (4, p.R2_STEPS, 3)
    assert np.all(np.isfinite(b.trajectories))
    if fam in p.R2_HARM:
        assert b.truth_label == 3 and b.fault_active
        assert b.onset_tick == p.R2_HARM[fam]
    if fam == "benign_native":
        assert b.truth_label is None and not b.fault_active


def test_r2_native_failure_is_on_m4_only():
    b = p.r2_bundle("constant_bias_sanity", 200)
    y = b.trajectories[:, :, 1].mean(axis=1)
    assert y[3] > 0.5 and np.all(np.abs(y[:3]) < 0.2)


def test_verdict_rule_is_mechanical():
    """A hand-built per_detector dict must yield the labels the prereg defines."""
    def agg(recall, fa, cm, delay):
        return {"fault_detection_recall": recall, "false_alarm_rate": fa,
                "common_mode_false_detection_rate": cm, "detection_delay_ticks": delay}
    def r2(attr, benign_det):
        return {f: {"attribution_acc": attr} for f in p.R2_HARM} | \
               {"benign_native": {"detected_rate": benign_det}}
    good = {"per_detector": {
        "DeterministicBaseline": {"r1_aggregate": agg(1.0, 0.1, 0.0, 17.0), "r2_per_family": r2(1.0, 0.0)},
        "LLTKalman-A1": {"r1_aggregate": agg(1.0, 0.05, 0.0, 6.0), "r2_per_family": r2(1.0, 0.0)},
        "BCVF": {"r1_aggregate": agg(0.5, 0.6, 0.0, 5.0), "r2_per_family": r2(0.0, 0.0)}}}
    assert p._verdict(good)["label"] == "A2_REPRODUCES"
    bad = {"per_detector": dict(good["per_detector"])}
    bad["per_detector"]["LLTKalman-A1"] = {"r1_aggregate": agg(1.0, 0.2, 0.2, 6.0),
                                           "r2_per_family": r2(0.4, 0.8)}
    assert p._verdict(bad)["label"] == "A2_FAILS"
    assert p._verdict(good)["header"] == "REAL_SENSOR_GATE_NOT_DISCHARGED"


def test_committed_results_carry_the_gate_label():
    import json, os
    path = os.path.join(os.path.dirname(p.__file__), "results", "a2_realistic_pilot.json")
    if not os.path.exists(path):
        pytest.skip("results not generated")
    d = json.load(open(path))
    assert d["real_sensor_gate_discharged"] is False
    assert d["verdict"]["header"] == "REAL_SENSOR_GATE_NOT_DISCHARGED"

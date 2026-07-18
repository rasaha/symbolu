"""Guard-layer invariants and the equalization guarantee (H and I share the
identical guarded template)."""

from __future__ import annotations

import numpy as np

from cyber_security.kill_study.config import StudyConfig
from cyber_security.kill_study.detectors import arm_H, arm_I
from cyber_security.kill_study.metrics import template_metrics
from cyber_security.kill_study.observers import run_observer
from cyber_security.kill_study.trajectories import generate

CFG = StudyConfig()


def _attack_event(seed=7):
    return generate("F06_abrupt_takeover", seed=seed, cfg=CFG, sigma=0.3,
                    separation=6.0, ramp_duration=90.0, missing_rate=0.0)


def test_anchor_bound_holds_under_takeover():
    ev = _attack_event()
    tr = run_observer(ev, CFG, guarded=True)
    dist = np.linalg.norm(tr.m_slow - ev.mu_u, axis=-1)
    assert dist.max() <= CFG.guard.anchor_radius + 1e-9


def test_guarded_template_moves_less_than_unguarded():
    ev = _attack_event()
    g = run_observer(ev, CFG, guarded=True)
    u = run_observer(ev, CFG, guarded=False)
    assert g.template_update_amount <= u.template_update_amount


def test_gate_freezes_updates_during_large_disagreement():
    ev = _attack_event()
    g = run_observer(ev, CFG, guarded=True)
    # After an abrupt takeover the disagreement blows past the gate, so many
    # post-onset steps must be frozen (gate closed).
    post = g.gate_open[ev.onset + 2 :]
    assert post.mean() < 0.5


def test_cumulative_displacement_limit_respected():
    ev = generate("F09_gate_aware_poisoning", seed=3, cfg=CFG, sigma=0.3,
                  separation=5.0, ramp_duration=90.0, missing_rate=0.0)
    g = run_observer(ev, CFG, guarded=True)
    assert g.template_update_amount <= CFG.guard.cumulative_disp_limit + 1e-6


def test_H_and_I_share_identical_guarded_template():
    """Equalization: H and I read the same guarded slow template, so their
    poisoning/template metrics are identical by construction."""
    ev = generate("F09_gate_aware_poisoning", seed=11, cfg=CFG, sigma=0.35,
                  separation=4.0, ramp_duration=90.0, missing_rate=0.0)
    oH, oI = arm_H(ev, CFG), arm_I(ev, CFG)
    mH = template_metrics(oH, ev)
    mI = template_metrics(oI, ev)
    assert np.isclose(mH["d_parallel"], mI["d_parallel"], atol=1e-12)
    assert np.isclose(mH["template_update_amount"],
                      mI["template_update_amount"], atol=1e-12)
    assert np.allclose(oH.trace.m_slow, oI.trace.m_slow, atol=1e-12)


def test_llt_cusum_invariant_to_linear_drift_but_fires_on_jump():
    """Arm E accumulates little on legit linear drift, a lot on an abrupt jump —
    the drift-invariant-yet-accumulating property the study credits to LLT+CUSUM."""
    from cyber_security.kill_study.detectors import llt_cusum_raw

    drift = generate("F03_linear_drift", seed=1, cfg=CFG, sigma=0.25,
                     separation=4.0, ramp_duration=90.0, missing_rate=0.0)
    jump = generate("F06_abrupt_takeover", seed=1, cfg=CFG, sigma=0.25,
                    separation=4.0, ramp_duration=90.0, missing_rate=0.0)
    s_drift = llt_cusum_raw(drift, CFG).max()
    s_jump = llt_cusum_raw(jump, CFG).max()
    assert s_jump > s_drift

"""
test_d4_d5.py — Diagnostics D4 (component collapse) + D5 (entropy-definition
correlation), torch-free. Both consume a D1 cache; here we construct synthetic caches
(no GPU/model) and assert the metrics + verdicts behave as designed.
"""

from __future__ import annotations

import numpy as np

from experiments.signal_gov.diagnostics import d4_vritti as d4
from experiments.signal_gov.diagnostics import d5_entropy_def as d5
from experiments.signal_gov.diagnostics.cache import D1Cache


def _softmax(z):
    z = np.asarray(z, float); z = z - z.max(); e = np.exp(z); return e / e.sum()


def _base_cache(n_pairs=10, conf=0.9):
    n = 2 * n_pairs
    c = D1Cache()
    c.scenario_ids = [f"s{i}" for i in range(n)]
    c.labels = list(np.tile([0, 1], n_pairs))
    c.groups = list(np.repeat([f"t{i}" for i in range(n_pairs)], 2))
    c.verbalized_conf = [conf] * n
    c.raw_entropy = [0.5] * n
    c.cg_entropy = [0.5] * n
    c.vritti_risk = [0.5] * n
    c.coherence = [0.5] * n
    c.jepa_disagreement = [0.5] * n
    c.internal_risk = [0.5] * n
    c.provenance = ["synthetic"] * n
    c.final_hidden = [np.zeros(8) for _ in range(n)]
    c.all_layer_hidden = [None] * n
    return c, n


def _state_with(*, bhava_fn, vritti_fn, rng):
    """Build a 32-D state row: bhava[0:12] softmax, kosha[12:17] sigmoid, vritti[17:22]
    softmax, guna[22:28] sigmoid, reserved[28:32] tanh."""
    s = np.zeros(32)
    s[0:12] = bhava_fn()
    s[12:17] = rng.random(5)
    s[17:22] = vritti_fn()
    s[22:28] = rng.random(6)
    s[28:32] = rng.uniform(-1, 1, 4)
    return s


# ----- D4 --------------------------------------------------------------------

def test_d4_detects_bhava_onehot_and_vritti_uniform_collapse():
    c, n = _base_cache()
    rng = np.random.default_rng(0)
    states = []
    for _ in range(n):
        states.append(_state_with(
            bhava_fn=lambda: _softmax([8.0] + [0.0] * 11),    # peaked -> one-hot
            vritti_fn=lambda: np.full(5, 0.2),                # uniform
            rng=rng))
    c.state32 = states
    r = d4.analyze(c)
    assert r.components["bhava"]["collapse"] == "one-hot"
    assert r.components["vritti"]["collapse"] == "uniform"
    assert "one-hot" in r.detail and "uniform" in r.detail


def test_d4_finds_informative_dimension_when_present():
    c, n = _base_cache()
    rng = np.random.default_rng(1)
    labels = np.array(c.labels)
    states = []
    for i in range(n):
        s = _state_with(bhava_fn=lambda: _softmax(rng.normal(size=12)),
                        vritti_fn=lambda: _softmax(rng.normal(size=5)), rng=rng)
        # Plant a clean governance axis in a guna dim (index 22), high on unsafe.
        s[22] = 0.1 + 0.8 * labels[i]
        states.append(s)
    c.state32 = states
    r = d4.analyze(c)
    assert r.best_dim == 22
    assert r.best_dim_auroc >= 0.9


def test_d4_flags_twin_blind_when_twins_share_state():
    c, n = _base_cache()
    rng = np.random.default_rng(2)
    states = []
    for g in range(n // 2):                       # identical state within each twin pair
        shared = _state_with(bhava_fn=lambda: _softmax(rng.normal(size=12)),
                             vritti_fn=lambda: _softmax(rng.normal(size=5)), rng=rng)
        states.append(shared.copy()); states.append(shared.copy())
    c.state32 = states
    r = d4.analyze(c)
    # twins are identical -> twin L1 ~ 0 -> twin-blind on every varying component
    assert any(comp.get("twin_blind") for comp in r.components.values())


# ----- D5 --------------------------------------------------------------------

def test_d5_near_zero_when_entropies_are_independent():
    c, n = _base_cache()
    rng = np.random.default_rng(3)
    c.raw_entropy = list(rng.random(n))
    c.cg_entropy = list(rng.random(n))            # independent of raw
    r = d5.analyze(c)
    assert abs(r.pearson_sub) <= d5.NEAR_ZERO
    assert r.verdict == "NEAR_ZERO_DIFFERENT_OBJECT"


def test_d5_detects_anti_correlation():
    c, n = _base_cache()
    raw = np.linspace(0.1, 0.9, n)
    c.raw_entropy = list(raw)
    c.cg_entropy = list(1.0 - raw + 0.01 * np.random.default_rng(4).normal(size=n))
    r = d5.analyze(c)
    assert r.pearson_sub < -d5.NEAR_ZERO
    assert r.verdict == "ANTI_CORRELATED"


def test_d5_detects_positive_correlation():
    c, n = _base_cache()
    raw = np.linspace(0.1, 0.9, n)
    c.raw_entropy = list(raw)
    c.cg_entropy = list(raw + 0.01 * np.random.default_rng(5).normal(size=n))
    r = d5.analyze(c)
    assert r.pearson_sub > d5.NEAR_ZERO
    assert r.verdict == "CORRELATED"


def test_d5_handles_degenerate_cg_entropy():
    c, n = _base_cache()
    c.raw_entropy = list(np.random.default_rng(6).random(n))
    c.cg_entropy = [0.5] * n                       # constant
    r = d5.analyze(c)
    assert r.verdict == "CG_ENTROPY_DEGENERATE"


# ----- both render + round-trip through a real cache --------------------------

def test_d4_d5_run_on_saved_cache(tmp_path):
    c, n = _base_cache()
    rng = np.random.default_rng(7)
    c.state32 = [_state_with(bhava_fn=lambda: _softmax(rng.normal(size=12)),
                             vritti_fn=lambda: _softmax(rng.normal(size=5)), rng=rng)
                 for _ in range(n)]
    c.raw_entropy = list(rng.random(n))
    c.cg_entropy = list(rng.random(n))
    path = c.save(tmp_path / "d1_cache.npz")
    reloaded = D1Cache.load(path)
    r4 = d4.analyze(reloaded)
    r5 = d5.analyze(reloaded)
    assert "component" in d4.render_report(r4).lower()
    assert "D5" in d5.render_report(r5)
    assert r4.n == n and r5.n == n

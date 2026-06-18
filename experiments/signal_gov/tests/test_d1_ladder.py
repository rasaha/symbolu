"""
test_d1_ladder.py — Diagnostic D1 (signal-survival ladder), torch-free.

Three layers, none needing a GPU/model:
  1. the linear probe (group-LOO dual ridge) is honest — perfect in-sample separation
     does NOT inflate the out-of-fold AUROC, and a planted linear signal IS recovered;
  2. the localization verdict fires correctly for each pre-registered branch, driven
     by synthetic caches (mirrors test_falsification's synthetic-signal approach);
  3. the mock-backend cache builds + round-trips through disk and runs the full ladder.
"""

from __future__ import annotations

import numpy as np
import pytest

from experiments.signal_gov.diagnostics.cache import D1Cache, build_cache_mock
from experiments.signal_gov.diagnostics.ladder import (
    CHANCE_BAND, V_ENTROPY_DEF, V_HIDDEN, V_NO_CEILING, V_PROJECTION, V_SURVIVES,
    V_TOO_FEW, compute_ladder, render_report,
)
from experiments.signal_gov.diagnostics.probes import (
    linear_probe_oof_scores, probe_auroc_over_alphas,
)
from experiments.signal_gov.falsification.scenarios import load_fabrication
from experiments.signal_gov.metrics import roc_auc


# ----- 1. the probe is honest -------------------------------------------------

def _groups(n_pairs):
    # one safe + one unsafe per twin group; labels alternate by twin
    g, y = [], []
    for i in range(n_pairs):
        g += [f"t{i}", f"t{i}"]
        y += [0, 1]
    return np.array(g), np.array(y)


def test_probe_does_not_overfit_pure_noise():
    rng = np.random.default_rng(0)
    g, y = _groups(10)                       # 20 items, 10 twin pairs
    x = rng.normal(size=(20, 200))           # D >> N, no signal
    oof = linear_probe_oof_scores(x, y, g, alpha=1.0)
    auc = roc_auc(y[~np.isnan(oof)], oof[~np.isnan(oof)])
    # Out-of-fold AUROC on pure noise must stay near chance (not 1.0 as in-sample would).
    assert 0.25 <= auc <= 0.75


def test_probe_recovers_a_planted_linear_signal():
    rng = np.random.default_rng(1)
    g, y = _groups(12)
    x = rng.normal(size=(24, 16))
    x[:, :4] += 4.0 * y[:, None]             # plant a clean linear signal in dims 0-3
    res = probe_auroc_over_alphas(x, y, g)
    assert res["median"] >= 0.85


# ----- 2. localization verdict branches (synthetic caches) --------------------

def _synthetic_cache(*, raw, hidden_sep, state_sep, cg, n_pairs=10, conf=0.9):
    """Build a cache with controllable separability at each rung.

    raw/cg are per-item oriented scalars; hidden_sep/state_sep are the linear
    separation strength planted into the probe matrices (0 => chance).
    """
    rng = np.random.default_rng(7)
    n = 2 * n_pairs
    y = np.tile([0, 1], n_pairs)
    groups = np.repeat([f"t{i}" for i in range(n_pairs)], 2)
    c = D1Cache()
    c.scenario_ids = [f"s{i}" for i in range(n)]
    c.labels = list(y)
    c.groups = list(groups)
    c.verbalized_conf = [conf] * n
    c.raw_entropy = list(raw)
    c.cg_entropy = list(cg)
    c.vritti_risk = [0.5] * n
    c.coherence = [0.5] * n
    c.jepa_disagreement = [0.5] * n
    c.internal_risk = [0.5] * n
    c.provenance = ["synthetic"] * n
    hid = rng.normal(size=(n, 40)); hid[:, 0] += hidden_sep * y
    st = rng.normal(size=(n, 32)); st[:, 0] += state_sep * y
    c.final_hidden = [hid[i] for i in range(n)]
    c.state32 = [st[i] for i in range(n)]
    c.all_layer_hidden = [None] * n
    return c


def _sep_scalar(strength, n_pairs=10):
    # higher on unsafe (label 1) when strength>0; flat at chance when strength==0
    base = np.tile([0.5, 0.5], n_pairs)
    return base + np.tile([0.0, strength], n_pairs)


def test_verdict_projection_when_hidden_recovers_but_state_does_not():
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=4.0, state_sep=0.0,
                         cg=_sep_scalar(0.0))
    r = compute_ladder(c, n_boot=50)
    assert r.aurocs_subset["raw_entropy"] >= 0.65
    assert r.aurocs_subset["hidden_probe"] > CHANCE_BAND
    assert r.aurocs_subset["state_probe"] <= CHANCE_BAND
    assert r.verdict == V_PROJECTION
    assert "R1" in r.r_select and "R2" in r.r_select


def test_verdict_entropy_definition_when_state_recovers_but_cg_entropy_does_not():
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=4.0, state_sep=4.0,
                         cg=_sep_scalar(0.0))
    r = compute_ladder(c, n_boot=50)
    assert r.aurocs_subset["state_probe"] > CHANCE_BAND
    assert r.aurocs_subset["cg_entropy"] <= CHANCE_BAND
    assert r.verdict == V_ENTROPY_DEF
    assert "read-out" in r.detail or "read-out" in r.r_select


def test_verdict_hidden_when_even_final_hidden_is_chance():
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=0.0, state_sep=0.0,
                         cg=_sep_scalar(0.0))
    r = compute_ladder(c, n_boot=50)
    assert r.verdict == V_HIDDEN


def test_verdict_survives_when_every_rung_holds():
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=4.0, state_sep=4.0,
                         cg=_sep_scalar(0.4))
    r = compute_ladder(c, n_boot=50)
    assert r.verdict == V_SURVIVES


def test_verdict_no_ceiling_when_raw_entropy_is_chance():
    c = _synthetic_cache(raw=_sep_scalar(0.0), hidden_sep=4.0, state_sep=4.0,
                         cg=_sep_scalar(0.4))
    r = compute_ladder(c, n_boot=50)
    assert r.verdict == V_NO_CEILING


def test_verdict_too_few_when_subset_imbalanced():
    # Only unsafe items are confident -> no confident safe item in the subset.
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=4.0, state_sep=4.0,
                         cg=_sep_scalar(0.4))
    c.verbalized_conf = list(np.tile([0.2, 0.9], 10))   # safe twins not confident
    r = compute_ladder(c, n_boot=50)
    assert r.confident_safe < 2
    assert r.verdict == V_TOO_FEW


def test_render_report_has_ladder_and_verdict():
    c = _synthetic_cache(raw=_sep_scalar(0.4), hidden_sep=4.0, state_sep=0.0,
                         cg=_sep_scalar(0.0))
    r = compute_ladder(c, n_boot=50)
    md = render_report(r, provenance="d1_mock:test")
    assert "Signal-Survival Ladder" in md
    assert "Localization verdict" in md
    assert r.headline in md


# ----- 3. mock-backend cache end to end (real bridge, real probes) ------------

def test_mock_cache_builds_and_runs_full_ladder():
    pytest.importorskip("agentic.agentic_framework.sovereign_bridge")
    scenarios = load_fabrication()
    cache = build_cache_mock(scenarios, seed=7)
    assert len(cache) == len(scenarios) == 20
    assert all(p.startswith("d1_mock") for p in cache.provenance)
    # bridge-derived scalars are populated and in range
    assert all(0.0 <= v <= 1.0 for v in cache.vritti_risk)
    r = compute_ladder(cache, n_boot=50)
    # The mock is LABEL-BLIND, so this is a plumbing check, not a result: the ladder
    # must run and produce a verdict string (any branch is acceptable here).
    assert r.verdict
    assert r.n == 20


def test_mock_cache_round_trips_through_disk(tmp_path):
    scenarios = load_fabrication()[:6]
    cache = build_cache_mock(scenarios, seed=3)
    path = cache.save(tmp_path / "d1_cache.npz")
    reloaded = D1Cache.load(path)
    assert reloaded.scenario_ids == cache.scenario_ids
    assert reloaded.labels == cache.labels
    np.testing.assert_allclose(reloaded.hidden_matrix(), cache.hidden_matrix())
    np.testing.assert_allclose(reloaded.state_matrix(), cache.state_matrix())
    np.testing.assert_allclose(reloaded.raw_entropy, cache.raw_entropy)

"""Tests for the synthetic semantic-tiering mechanism study.

These assert the *mechanism* behaves correctly (a controlled sanity harness) —
they do NOT assert anything about real models, per the module's banner.
"""
from __future__ import annotations

from ndol.sim.semantic_tiering import Config, _avg_over_seeds


def test_attention_wins_when_importance_is_attention_visible():
    r = _avg_over_seeds(Config(w_sem=0.0))
    c = r["captured"]
    assert c["attention (magnitude)"] > c["semantic (coherence)"]


def test_semantic_wins_when_importance_is_semantic():
    r = _avg_over_seeds(Config(w_sem=1.0))
    c = r["captured"]
    assert c["semantic (coherence)"] > c["attention (magnitude)"]


def test_oracle_is_upper_bound():
    r = _avg_over_seeds(Config(w_sem=0.5))
    c = r["captured"]
    for name in ("attention (magnitude)", "semantic (coherence)", "SCC (½·attn+½·coh)", "random+pins"):
        assert c["oracle (true imp.)"] >= c[name] - 1e-9


def test_scc_blend_is_robust_across_w_sem():
    # The blend should never fall far below the better single signal at either extreme.
    for w in (0.0, 1.0):
        c = _avg_over_seeds(Config(w_sem=w))["captured"]
        better = max(c["attention (magnitude)"], c["semantic (coherence)"])
        assert c["SCC (½·attn+½·coh)"] >= better - 0.02


def test_semantic_catches_needles_attention_misses():
    r = _avg_over_seeds(Config(w_sem=0.6))
    nr = r["needle_recall"]
    assert nr["semantic (coherence)"] > nr["attention (magnitude)"]


def test_random_is_near_lower_bound():
    c = _avg_over_seeds(Config(w_sem=0.5))["captured"]
    # informative selectors should not be worse than random+pins
    assert c["attention (magnitude)"] >= c["random+pins"] - 0.02
    assert c["semantic (coherence)"] >= c["random+pins"] - 0.02

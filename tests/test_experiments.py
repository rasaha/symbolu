"""Tests for the semantic-tiering experiment scaffolding (CPU-testable)."""
from __future__ import annotations

import math

import pytest

from ndol.experiments import (
    coherence_scores,
    context_centroid,
    select_by_policy,
)
from ndol.experiments.loo_importance import (
    SyntheticConfig,
    partial_spearman,
    pearson,
    run_synthetic,
    spearman,
)


# ------------------------------ coherence ---------------------------------- #
def test_context_centroid_is_unit():
    c = context_centroid([[3.0, 0.0, 0.0], [0.0, 4.0, 0.0]])
    assert abs(math.sqrt(sum(x * x for x in c)) - 1.0) < 1e-9


def test_cosine_coherence_aligned_vs_orthogonal():
    centroid = [1.0, 0.0, 0.0]
    scores = coherence_scores([[2.0, 0.0, 0.0], [0.0, 5.0, 0.0]], centroid, mode="cos_value")
    assert scores[0] > 0.99      # aligned ⇒ ~1
    assert abs(scores[1]) < 1e-9  # orthogonal ⇒ ~0


def test_value_norm_mode():
    scores = coherence_scores([[3.0, 4.0], [1.0, 0.0]], mode="value_norm")
    assert abs(scores[0] - 5.0) < 1e-9 and abs(scores[1] - 1.0) < 1e-9


# ------------------------------ selector ----------------------------------- #
def test_full_selects_everything():
    assert select_by_policy("full", 10, budget=3) == set(range(10))


def test_attention_picks_top_and_keeps_pinned():
    attn = [0.0, 9.0, 1.0, 8.0, 0.5]
    keep = select_by_policy("attention", 5, budget=3, pinned={0}, attention=attn)
    assert 0 in keep                 # pinned always kept
    assert 1 in keep and 3 in keep   # top-2 by attention fill the rest


def test_scc_blend_differs_from_either_signal():
    attn = [9.0, 0.0, 1.0, 0.0]
    coh = [0.0, 9.0, 0.0, 1.0]
    keep = select_by_policy("scc", 4, budget=2, attention=attn, coherence=coh)
    assert keep == {0, 1}            # blend surfaces the top of each


def test_random_is_reproducible():
    a = select_by_policy("random", 20, budget=5, seed=7)
    b = select_by_policy("random", 20, budget=5, seed=7)
    assert a == b


def test_missing_scores_raise():
    with pytest.raises(ValueError):
        select_by_policy("semantic", 5, budget=2)   # no coherence provided


# ------------------------------ LOO stats ---------------------------------- #
def test_spearman_monotonic():
    assert abs(spearman([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-9


def test_pearson_basic():
    assert abs(pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9


def test_partial_removes_shared_signal():
    # y is driven entirely by z; x is independent noise correlated to z only via y.
    z = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = list(z)                       # y == z
    x = [2.0, 1.0, 4.0, 3.0, 6.0, 5.0]
    # x's partial correlation with y given z should be ~0 (y adds nothing beyond z)
    assert abs(partial_spearman(x, y, z)) < 0.2


# ------------------------------ synthetic decision ------------------------- #
def _avg_partial(w_sem: float, seeds: int = 3) -> float:
    return sum(run_synthetic(SyntheticConfig(w_sem=w_sem, seed=s))["rho_partial_coh_given_attn"]
               for s in range(seeds)) / seeds


def test_decision_flips_with_w_sem():
    # w_sem=0: coherence adds no incremental power; high w_sem: it does.
    assert _avg_partial(0.0) < 0.1
    assert _avg_partial(0.7) > 0.1


def test_coherence_catches_needles_attention_misses():
    r = run_synthetic(SyntheticConfig(w_sem=0.7, seed=0))
    assert r["needle_recall_coh"] > r["needle_recall_attn"]

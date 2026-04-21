"""§6.3 scoring tests — three MC scoring functions, teacher-forcing."""

from __future__ import annotations

import math

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.benchmark.scoring import (
    score_choice_blend,
    score_choice_trust,
    score_choice_vanilla,
)
from symbolu_bcvf_llm.core import BCVFLLMConfig
from symbolu_bcvf_llm.sources.mock import MockSource


def _flat_fn(V, L=5):
    def fn(prefix):
        return np.zeros((L, V), dtype=np.float32)
    return fn


def _peaked_fn(V, top, L=5, peak=10.0):
    def fn(prefix):
        z = np.full((L, V), -peak, dtype=np.float32)
        z[:, top] = peak
        return z
    return fn


def test_vanilla_prefers_correct_choice_when_source0_agrees():
    V = 8
    bench = MockBenchmark(num_questions=3, V=V, L=5, policies=["healthy"])
    q = bench.questions[0]
    sources_correct = bench.make_sources(q)
    s_correct = score_choice_vanilla(sources_correct, q.choice_tokens[0])
    sources_distractor = bench.make_sources(q)
    s_distractor = score_choice_vanilla(sources_distractor, q.choice_tokens[1])
    assert s_correct > s_distractor


def test_vanilla_score_matches_manual_logprob():
    V = 8
    TOP = 3
    sources = [MockSource(_peaked_fn(V, TOP), L=5, V=V) for _ in range(1)]
    # Single-token score: log softmax(peaked_logits)[TOP].
    score = score_choice_vanilla(sources, [TOP])
    expected = math.log(1.0 - 1e-5)  # approximately 0
    assert abs(score - expected) < 0.01


def test_blend_score_is_log_of_equal_weighted_mean():
    V = 4
    # Source 0 peaks at token 0; sources 1, 2 peak at token 2.
    sources = [
        MockSource(_peaked_fn(V, 0), L=5, V=V),
        MockSource(_peaked_fn(V, 2), L=5, V=V),
        MockSource(_peaked_fn(V, 2), L=5, V=V),
    ]
    score_0 = score_choice_blend(sources, [0])
    sources2 = [
        MockSource(_peaked_fn(V, 0), L=5, V=V),
        MockSource(_peaked_fn(V, 2), L=5, V=V),
        MockSource(_peaked_fn(V, 2), L=5, V=V),
    ]
    score_2 = score_choice_blend(sources2, [2])
    # Token 2 should score higher because it has majority mass.
    assert score_2 > score_0


def test_trust_rejects_anchor_pairing():
    V = 4
    sources = [MockSource(_flat_fn(V), L=5, V=V) for _ in range(3)]
    bad = BCVFLLMConfig(use_anchor_pairing=True)
    with pytest.raises(ValueError, match="non-anchor"):
        score_choice_trust(sources, [0, 1], bcvf_config=bad)


def test_trust_scores_finite_and_ordered():
    V = 4
    # Source 0 outlier, sources 1 2 clean on token 2.
    def fn_outlier(prefix):
        z = np.full((5, V), -10.0, dtype=np.float32)
        z[:, 0] = 10.0
        return z

    def fn_clean(prefix):
        z = np.full((5, V), -10.0, dtype=np.float32)
        z[:, 2] = 10.0
        return z

    sources = [
        MockSource(fn_outlier, L=5, V=V),
        MockSource(fn_clean, L=5, V=V),
        MockSource(fn_clean, L=5, V=V),
    ]
    score_correct = score_choice_trust(sources, [2, 2])
    sources2 = [
        MockSource(fn_outlier, L=5, V=V),
        MockSource(fn_clean, L=5, V=V),
        MockSource(fn_clean, L=5, V=V),
    ]
    score_wrong = score_choice_trust(sources2, [0, 0])
    assert math.isfinite(score_correct)
    assert math.isfinite(score_wrong)
    # The trust-shaped decoder should prefer the majority's token even
    # when source 0 wants otherwise (after trust shifts weight to 1, 2).
    assert score_correct > score_wrong

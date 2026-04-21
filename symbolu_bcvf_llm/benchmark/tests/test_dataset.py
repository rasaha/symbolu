"""§6.2 dataset tests — MockBenchmark structural correctness."""

from __future__ import annotations

import pytest

from symbolu_bcvf_llm.benchmark.dataset import (
    Benchmark,
    MockBenchmark,
    Question,
)
from symbolu_bcvf_llm.sources.base import Source


def test_mock_benchmark_satisfies_protocol():
    bench = MockBenchmark(num_questions=4)
    assert isinstance(bench, Benchmark)


def test_mock_benchmark_produces_requested_question_count():
    bench = MockBenchmark(num_questions=12)
    assert len(bench.questions) == 12


def test_mock_benchmark_questions_have_correct_fields():
    bench = MockBenchmark(num_questions=6)
    for q in bench.questions:
        assert isinstance(q, Question)
        assert isinstance(q.prompt_tokens, list)
        assert len(q.choices) == 2
        assert len(q.choice_tokens) == 2
        assert q.correct_index == 0
        assert q.metadata["policy"] in (
            "healthy", "healthy_majority", "trust_required"
        )


def test_mock_benchmark_make_sources_returns_3_valid_sources():
    bench = MockBenchmark(num_questions=3)
    for q in bench.questions:
        srcs = bench.make_sources(q)
        assert len(srcs) == 3
        for s in srcs:
            assert isinstance(s, Source)
            assert s.vocab_size == bench.vocab_size
            assert s.L == bench.L
            # Sources are seeded with the prompt tokens as committed prefix.
            probs, mask = s.lookahead()
            assert probs.shape == (bench.L, bench.vocab_size)
            assert mask.shape == (bench.L,)


def test_mock_benchmark_validates_params():
    with pytest.raises(ValueError):
        MockBenchmark(num_questions=0)
    with pytest.raises(ValueError):
        MockBenchmark(num_questions=3, V=2)
    with pytest.raises(ValueError):
        MockBenchmark(num_questions=3, L=2)


def test_mock_benchmark_distractor_different_from_correct():
    bench = MockBenchmark(num_questions=10, V=32)
    for q in bench.questions:
        assert q.metadata["correct_token"] != q.metadata["distractor_token"]

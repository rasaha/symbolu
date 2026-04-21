"""§6.4 harness tests — end-to-end run_benchmark with MockBenchmark."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.benchmark.harness import run_benchmark


def test_run_benchmark_returns_all_three_decoders():
    bench = MockBenchmark(num_questions=6)
    bundle = run_benchmark(bench)
    assert set(bundle.results.keys()) == {
        "vanilla", "conventional_blend", "bcvf_trust"
    }
    for r in bundle.results.values():
        assert r.num_questions == 6
        assert r.per_question_correct.shape == (6,)
        assert r.per_question_latency_s.shape == (6,)
        assert 0.0 <= r.accuracy <= 1.0


def test_run_benchmark_vanilla_wrong_when_source0_distractor():
    # Only healthy_majority: vanilla (source-0) should get the distractor.
    bench = MockBenchmark(
        num_questions=9, policies=["healthy_majority"]
    )
    bundle = run_benchmark(bench)
    assert bundle.results["vanilla"].accuracy == 0.0
    # Blend should get these right (2 of 3 sources favour correct).
    assert bundle.results["conventional_blend"].accuracy == 1.0
    # Trust should match or exceed blend on this benign scenario.
    assert bundle.results["bcvf_trust"].accuracy >= 1.0


def test_run_benchmark_healthy_all_correct():
    bench = MockBenchmark(num_questions=6, policies=["healthy"])
    bundle = run_benchmark(bench)
    for r in bundle.results.values():
        assert r.accuracy == 1.0


def test_run_benchmark_trust_wins_on_trust_required():
    """Under `trust_required` policy, source 0 produces accelerating
    divergence on ALL lookahead positions toward the distractor.
    BCVF should catch this and down-weight source 0; the blend
    may also succeed because 2 of 3 sources already favour
    correct. Main check: trust accuracy >= blend accuracy (not
    strictly greater, because blend majority also handles this
    family in many cases)."""
    bench = MockBenchmark(
        num_questions=12, policies=["trust_required"]
    )
    bundle = run_benchmark(bench)
    assert bundle.results["bcvf_trust"].accuracy >= bundle.results[
        "conventional_blend"
    ].accuracy


def test_run_benchmark_max_questions_truncates():
    bench = MockBenchmark(num_questions=20)
    bundle = run_benchmark(bench, max_questions=5)
    for r in bundle.results.values():
        assert r.num_questions == 5


def test_run_benchmark_progress_callback_invoked():
    bench = MockBenchmark(num_questions=4)
    calls = []

    def cb(i, n, decoder):
        calls.append((i, n, decoder))

    run_benchmark(bench, progress_callback=cb)
    assert len(calls) == 4 * 3  # N × decoders
    assert all(n == 4 for (_, n, _) in calls)


def test_run_benchmark_metadata_carries_seed():
    bench = MockBenchmark(num_questions=3)
    bundle = run_benchmark(bench, seed=7)
    assert bundle.seed == 7
    for r in bundle.results.values():
        assert r.metadata["seed"] == 7

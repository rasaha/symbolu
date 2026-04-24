"""§12 Speculative-decoding mock benchmark tests.

Validates that:
1. The mock benchmark produces well-shaped Question objects.
2. `make_sources` returns a 2-source list (target, draft).
3. All 9 existing observables run without error on M=2 sources via
   the probe harness — the central "portability" claim.
"""

from __future__ import annotations

import pytest

from symbolu_bcvf_llm.benchmark.speculative import (
    SpeculativeDecodingBenchmark,
    SpeculativeDecodingMockBenchmark,
)
from symbolu_bcvf_llm.observables import (
    BCVFPerStepMaxObservable,
    BCVFSourceZeroCostObservable,
    BCVFSourceZeroPerStepMaxObservable,
    BCVFTotalCostObservable,
    CoherenceAnchoredBCVFObservable,
    CoherenceAnchoredBCVFPerStepObservable,
    Source0EntropyObservable,
    SourceAgreementObservable,
    UncertaintyGatedBCVFPerStepMaxObservable,
    probe_observables_parallel,
)


# --------------------------------------------------------------------------- #
# Benchmark shape
# --------------------------------------------------------------------------- #


def test_mock_questions_well_formed():
    bench = SpeculativeDecodingMockBenchmark(
        num_questions=6, num_candidates=3, K=5, V=32,
    )
    qs = list(bench.questions)
    assert len(qs) == 6
    for q in qs:
        assert len(q.choice_tokens) == 3  # num_candidates
        assert all(len(c) == 5 for c in q.choice_tokens)  # K tokens each
        assert q.correct_index == 0
        assert q.metadata["K"] == 5


def test_mock_correct_choice_has_correct_first_token():
    """By construction, choice 0's first token is the target's peak."""
    bench = SpeculativeDecodingMockBenchmark(num_questions=5, K=5, V=32)
    for q in bench.questions:
        correct_token = q.metadata["correct_token"]
        assert q.choice_tokens[0][0] == correct_token


def test_mock_distractors_avoid_correct_token():
    """Distractors' first tokens must differ from target peak."""
    bench = SpeculativeDecodingMockBenchmark(
        num_questions=10, num_candidates=3, K=5, V=32,
    )
    for q in bench.questions:
        correct_token = q.metadata["correct_token"]
        for c_idx in range(1, len(q.choice_tokens)):
            assert q.choice_tokens[c_idx][0] != correct_token


def test_mock_requires_min_candidates():
    with pytest.raises(ValueError, match="num_candidates"):
        SpeculativeDecodingMockBenchmark(num_candidates=1)


def test_mock_requires_min_vocab():
    with pytest.raises(ValueError, match="V"):
        SpeculativeDecodingMockBenchmark(V=2)


# --------------------------------------------------------------------------- #
# make_sources produces M=2 source list
# --------------------------------------------------------------------------- #


def test_make_sources_returns_two():
    bench = SpeculativeDecodingMockBenchmark(num_questions=3)
    srcs = bench.make_sources(next(iter(bench.questions)))
    assert len(srcs) == 2


def test_make_sources_fresh_per_call():
    """Each make_sources call returns fresh source instances so the
    probe harness's isolated-source semantics work correctly."""
    bench = SpeculativeDecodingMockBenchmark(num_questions=3)
    q = next(iter(bench.questions))
    srcs_a = bench.make_sources(q)
    srcs_b = bench.make_sources(q)
    assert srcs_a[0] is not srcs_b[0]
    assert srcs_a[1] is not srcs_b[1]


def test_make_sources_target_peaks_on_correct_token():
    import numpy as np
    bench = SpeculativeDecodingMockBenchmark(num_questions=1, V=16)
    q = next(iter(bench.questions))
    target, draft = bench.make_sources(q)
    # Target's lookahead at position 0 should peak sharply on correct_token
    probs, _mask = target.lookahead()
    correct_token = q.metadata["correct_token"]
    top_token = int(np.argmax(probs[0]))
    assert top_token == correct_token


# --------------------------------------------------------------------------- #
# End-to-end: probe_observables_parallel runs all 9 observables on M=2
# --------------------------------------------------------------------------- #


_ALL_OBSERVABLES = [
    BCVFTotalCostObservable(),
    BCVFSourceZeroCostObservable(),
    Source0EntropyObservable(),
    SourceAgreementObservable(),
    BCVFPerStepMaxObservable(),
    BCVFSourceZeroPerStepMaxObservable(),
    CoherenceAnchoredBCVFObservable(),
    CoherenceAnchoredBCVFPerStepObservable(),
    UncertaintyGatedBCVFPerStepMaxObservable(),
]


def test_probe_harness_runs_all_9_observables_on_m2():
    bench = SpeculativeDecodingMockBenchmark(num_questions=8)
    reports = probe_observables_parallel(
        _ALL_OBSERVABLES, bench, retain_datapoints=False,
    )
    expected_names = {o.name for o in _ALL_OBSERVABLES}
    assert set(reports.keys()) == expected_names
    # Each observable must produce N_datapoints = 8 questions × 3 candidates
    for name, r in reports.items():
        assert r.n_datapoints == 24, (
            f"{name}: expected 24 datapoints (8 q × 3 candidates), "
            f"got {r.n_datapoints}"
        )


def test_probe_reports_finite_auc_on_all_observables():
    """Sanity: no NaN / inf / crashes on M=2 sources."""
    import math
    bench = SpeculativeDecodingMockBenchmark(num_questions=15)
    reports = probe_observables_parallel(
        _ALL_OBSERVABLES, bench, retain_datapoints=False,
    )
    for name, r in reports.items():
        assert math.isfinite(r.auc), f"{name} produced non-finite AUC: {r.auc}"
        assert 0.0 <= r.auc <= 1.0


# --------------------------------------------------------------------------- #
# Real-model benchmark is stubbed
# --------------------------------------------------------------------------- #


def test_real_spec_dec_benchmark_raises_not_implemented():
    """The real-model class is deliberately a NotImplementedError stub
    until the candidate-generation + acceptance-label pipeline lands
    in a future session."""
    with pytest.raises(NotImplementedError, match="next-session"):
        SpeculativeDecodingBenchmark()

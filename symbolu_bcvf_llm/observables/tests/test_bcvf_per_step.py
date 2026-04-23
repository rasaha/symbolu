"""Tests for per-step BCVF observables."""

from __future__ import annotations

from typing import List

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.observables.bcvf_per_step import (
    BCVFPerStepMaxObservable,
    BCVFSourceZeroPerStepMaxObservable,
)
from symbolu_bcvf_llm.observables.probe import probe_observables_parallel
from symbolu_bcvf_llm.sources.mock import MockSource


def _peaked(V: int, top: int, L: int = 5, peak: float = 10.0) -> np.ndarray:
    z = np.full((L, V), -peak, dtype=np.float32)
    z[:, top] = peak
    return z


def _make_agreeing_sources(
    V: int = 8, L: int = 5, top: int = 3, prefix=None,
) -> List[MockSource]:
    return [
        MockSource(lambda p: _peaked(V, top, L), L=L, V=V,
                   initial_prefix=list(prefix or []))
        for _ in range(3)
    ]


def _make_disagreeing_sources(V: int = 8, L: int = 5, prefix=None):
    return [
        MockSource(lambda p: _peaked(V, 1, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
        MockSource(lambda p: _peaked(V, 2, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
        MockSource(lambda p: _peaked(V, 3, L), L=L, V=V,
                   initial_prefix=list(prefix or [])),
    ]


# --------------------------------------------------------------------------- #
# BCVFPerStepMaxObservable
# --------------------------------------------------------------------------- #


def test_per_step_max_returns_scalar():
    obs = BCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_sources(), [1, 2], [3, 3, 3])
    assert isinstance(v.scalar, float)


def test_per_step_max_agreeing_sources_is_zero():
    """Sources that never disagree → BCVF = 0 at every step → max = 0."""
    obs = BCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_sources(), [1, 2], [3, 3, 3])
    assert v.scalar == pytest.approx(0.0, abs=1e-10)


def test_per_step_max_metadata_shape():
    obs = BCVFPerStepMaxObservable()
    choice = [3, 3, 3]
    v = obs.observe(_make_agreeing_sources(), [1], choice)
    assert v.metadata["n_steps"] == len(choice)
    assert len(v.metadata["per_step_costs"]) == len(choice)
    assert isinstance(v.metadata["argmax_step"], int)
    assert isinstance(v.metadata["mean_cost"], float)


def test_per_step_max_polarity():
    assert BCVFPerStepMaxObservable().higher_means_more_suspicious is True


def test_per_step_max_requires_isolated_sources():
    """The probe harness relies on this flag to give fresh sources."""
    assert BCVFPerStepMaxObservable().requires_isolated_sources is True


def test_per_step_max_handles_single_token_answer():
    obs = BCVFPerStepMaxObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [3])
    assert v.metadata["n_steps"] == 1


def test_per_step_max_commits_advance_state():
    """After observe() the sources should have the answer tokens committed.

    Since `requires_isolated_sources = True` in production the probe
    gives a fresh triple, but we verify the mutation happens.
    """
    obs = BCVFPerStepMaxObservable()
    srcs = _make_agreeing_sources(prefix=[1, 2])
    choice = [3, 3]
    obs.observe(srcs, [1, 2], choice)
    # Commits happen between steps, not after the final step. For K=2
    # tokens the observable commits 1 token (choice[0]) before step 1.
    for s in srcs:
        assert list(s.committed_prefix) == [1, 2, 3]


# --------------------------------------------------------------------------- #
# BCVFSourceZeroPerStepMaxObservable
# --------------------------------------------------------------------------- #


def test_source_0_per_step_max_returns_scalar():
    obs = BCVFSourceZeroPerStepMaxObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [3, 3])
    assert isinstance(v.scalar, float)


def test_source_0_per_step_max_agreeing_sources_is_zero():
    obs = BCVFSourceZeroPerStepMaxObservable()
    v = obs.observe(_make_agreeing_sources(), [1], [3, 3])
    assert v.scalar == pytest.approx(0.0, abs=1e-10)


def test_source_0_per_step_max_disagreeing_sources_runs():
    """Disagreeing MockSources still produce BCVF=0 because each is
    constant in time (kernel measures the temporal 2nd-derivative).
    This test verifies the observable runs and returns a float; value
    semantics are covered on real models where distributions vary."""
    obs = BCVFSourceZeroPerStepMaxObservable()
    v = obs.observe(_make_disagreeing_sources(), [1], [3, 3])
    assert isinstance(v.scalar, float)


def test_source_0_per_step_max_metadata():
    obs = BCVFSourceZeroPerStepMaxObservable()
    choice = [3, 3, 3]
    v = obs.observe(_make_agreeing_sources(), [1], choice)
    assert v.metadata["n_steps"] == len(choice)
    assert len(v.metadata["per_step_source_0_costs"]) == len(choice)
    assert len(v.metadata["per_step_total_costs"]) == len(choice)


def test_source_0_per_step_max_polarity_and_isolation_flag():
    obs = BCVFSourceZeroPerStepMaxObservable()
    assert obs.higher_means_more_suspicious is True
    assert obs.requires_isolated_sources is True


# --------------------------------------------------------------------------- #
# Integration with probe harness (the isolation opt-in must actually work)
# --------------------------------------------------------------------------- #


def test_probe_harness_isolates_per_step_observables():
    """End-to-end: the probe runs per-step observables on a MockBenchmark
    without cross-contaminating state between (Q, choice) pairs. If the
    opt-in wasn't honored, the second (Q, choice) would read a source
    triple that had already been advanced by the first, and metadata
    `n_steps` would drift."""
    bench = MockBenchmark(num_questions=3)
    reports = probe_observables_parallel(
        [BCVFPerStepMaxObservable(), BCVFSourceZeroPerStepMaxObservable()],
        bench,
        retain_datapoints=True,
    )
    for name in ("bcvf_per_step_max", "bcvf_source_0_per_step_max"):
        r = reports[name]
        # 3 questions × 2 choices = 6 datapoints
        assert r.n_datapoints == 6
        for dp in r.datapoints:
            # Every choice in MockBenchmark is 3 tokens, so n_steps == 3
            # at every (Q, C). If isolation failed, later datapoints
            # would carry extra accumulated commits.
            assert dp.observable_value.metadata["n_steps"] == 3

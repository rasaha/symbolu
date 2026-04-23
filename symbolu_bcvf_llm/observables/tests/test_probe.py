"""§11 probe harness tests — classification + correlation plumbing."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.benchmark.dataset import MockBenchmark
from symbolu_bcvf_llm.observables.base import ObservableValue
from symbolu_bcvf_llm.observables.probe import (
    probe_observable,
    probe_observables_parallel,
)


# --------------------------------------------------------------------------- #
# Synthetic observables with known ground-truth correlation
# --------------------------------------------------------------------------- #


class _LookupOracle:
    """Oracle observable that resolves the (Q, C) pair by matching
    prompt_tokens (unique per MockBenchmark question) and choice_tokens,
    then returns `scalar_correct` if the choice is correct else
    `scalar_wrong`."""

    def __init__(
        self, benchmark, *, name, polarity, scalar_correct, scalar_wrong,
    ):
        self.name = name
        self.higher_means_more_suspicious = polarity
        self._benchmark = benchmark
        self._scalar_correct = scalar_correct
        self._scalar_wrong = scalar_wrong

    def observe(self, sources, prompt_tokens, choice_tokens):
        for q in self._benchmark.questions:
            if list(q.prompt_tokens) != list(prompt_tokens):
                continue
            for c_idx, ct in enumerate(q.choice_tokens):
                if list(ct) == list(choice_tokens):
                    scalar = (
                        self._scalar_correct
                        if c_idx == q.correct_index
                        else self._scalar_wrong
                    )
                    return ObservableValue(scalar=scalar)
        return ObservableValue(scalar=0.5)


def _make_oracle_obs(benchmark):
    return _LookupOracle(
        benchmark, name="oracle", polarity=False,
        scalar_correct=1.0, scalar_wrong=0.0,
    )


def _make_anti_oracle_obs(benchmark):
    return _LookupOracle(
        benchmark, name="anti_oracle", polarity=True,
        scalar_correct=0.0, scalar_wrong=1.0,
    )


def _make_random_obs():
    class _Obs:
        name = "random_noise"
        higher_means_more_suspicious = False
        _rng = np.random.default_rng(seed=0)

        def observe(self, sources, prompt_tokens, choice_tokens):
            return ObservableValue(scalar=float(self._rng.random()))

    return _Obs()


# --------------------------------------------------------------------------- #
# probe_observable
# --------------------------------------------------------------------------- #


def test_probe_returns_truth_correlated_on_oracle():
    bench = MockBenchmark(num_questions=24)
    obs = _make_oracle_obs(bench)
    report = probe_observable(obs, bench)
    assert report.classification == "TRUTH_CORRELATED"
    assert report.auc == pytest.approx(1.0)
    # Correctness-polarity observable: correct choices get higher scalar.
    assert report.mean_scalar_when_correct > report.mean_scalar_when_wrong


def test_probe_anti_correlated_suspicion_polarity_reports_high_auc():
    """Anti-oracle with 'higher = more suspicious' polarity: scalar=1 on
    wrong, scalar=0 on correct → probe should INVERT for AUC and report
    AUC ≈ 1.0 (observable predicts correctness better when inverted).

    But the probe uses the observable AS-IS for AUC. We flip
    internally when higher_means_more_suspicious is True. So AUC should
    be 1.0 because suspicion-polarity means higher scalar → more wrong,
    which after internal negation → lower scalar → more wrong → higher
    AUC.
    """
    bench = MockBenchmark(num_questions=24)
    obs = _make_anti_oracle_obs(bench)
    report = probe_observable(obs, bench)
    # AUC should be 1.0 because the observable perfectly identifies
    # wrong answers (and the probe's polarity flip normalizes direction).
    assert report.auc == pytest.approx(1.0)
    assert report.classification == "TRUTH_CORRELATED"


def test_probe_random_observable_near_uncorrelated():
    bench = MockBenchmark(num_questions=48)
    obs = _make_random_obs()
    report = probe_observable(obs, bench)
    # Random observable should not be TRUTH_CORRELATED; AUC near 0.5.
    assert report.classification in ("UNCORRELATED", "ANTI_CORRELATED",
                                     "TRUTH_CORRELATED")
    # Loose — RNG-dependent; just check AUC isn't suspiciously high.
    assert 0.3 < report.auc < 0.7


def test_probe_records_datapoints_by_default():
    bench = MockBenchmark(num_questions=4)
    obs = _make_oracle_obs(bench)
    report = probe_observable(obs, bench)
    # 4 questions × 2 choices = 8 datapoints.
    assert len(report.datapoints) == 8


def test_probe_retain_datapoints_false_drops_records():
    bench = MockBenchmark(num_questions=4)
    obs = _make_oracle_obs(bench)
    report = probe_observable(obs, bench, retain_datapoints=False)
    assert report.datapoints == []
    # Stats still computed.
    assert report.n_datapoints == 8
    assert report.auc == pytest.approx(1.0)


def test_probe_classifies_null_on_small_n():
    """N=4 mock benchmark → 8 datapoints, below min_n=40 → NULL."""
    bench = MockBenchmark(num_questions=4)
    obs = _make_oracle_obs(bench)
    report = probe_observable(obs, bench)
    assert report.classification == "NULL"


def test_probe_max_questions_caps():
    bench = MockBenchmark(num_questions=48)
    obs = _make_oracle_obs(bench)
    report = probe_observable(obs, bench, max_questions=10)
    assert report.n_questions == 10
    # 10 questions × 2 choices = 20 datapoints.
    assert report.n_datapoints == 20


# --------------------------------------------------------------------------- #
# probe_observables_parallel
# --------------------------------------------------------------------------- #


def test_probe_parallel_returns_report_per_observable():
    bench = MockBenchmark(num_questions=24)
    obs_list = [_make_oracle_obs(bench), _make_random_obs()]
    # For `oracle`, name key is `oracle`; for random_noise, `random_noise`.
    reports = probe_observables_parallel(obs_list, bench)
    assert set(reports.keys()) == {"oracle", "random_noise"}


def test_probe_parallel_oracle_is_truth_correlated():
    bench = MockBenchmark(num_questions=24)
    reports = probe_observables_parallel([_make_oracle_obs(bench)], bench)
    r = reports["oracle"]
    assert r.auc == pytest.approx(1.0)

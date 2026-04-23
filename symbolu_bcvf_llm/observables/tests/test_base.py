"""§11 observable-framework core tests — Protocol, dataclasses, correlation math."""

from __future__ import annotations

import numpy as np
import pytest

from symbolu_bcvf_llm.observables.base import (
    Observable,
    ObservableValue,
    _pearson_r,
    _rankdata,
    _roc_auc,
    _spearman_rho,
    classify_observable,
    recommendation_for,
)


# --------------------------------------------------------------------------- #
# Correlation primitives
# --------------------------------------------------------------------------- #


def test_pearson_perfect_positive():
    x = np.arange(10.0)
    y = 2.0 * x + 3.0
    assert _pearson_r(x, y) == pytest.approx(1.0, abs=1e-10)


def test_pearson_perfect_negative():
    x = np.arange(10.0)
    y = -x
    assert _pearson_r(x, y) == pytest.approx(-1.0, abs=1e-10)


def test_pearson_zero_on_constant():
    assert _pearson_r(np.arange(5.0), np.ones(5)) == 0.0
    assert _pearson_r(np.ones(5), np.arange(5.0)) == 0.0


def test_rankdata_handles_ties():
    x = np.array([10.0, 20.0, 20.0, 30.0])
    # Ties at index 1 and 2 → average rank (2+3)/2 = 2.5
    r = _rankdata(x)
    assert list(r) == [1.0, 2.5, 2.5, 4.0]


def test_spearman_monotonic_invariance():
    """Spearman is invariant under monotonic transforms; Pearson isn't."""
    x = np.arange(1.0, 11.0)
    y = np.exp(x)  # strictly monotonic but nonlinear
    assert _spearman_rho(x, y) == pytest.approx(1.0, abs=1e-10)


def test_auc_perfect_separation():
    scores = np.array([0.1, 0.2, 0.3, 0.9, 0.8, 0.7])
    labels = np.array([False, False, False, True, True, True])
    assert _roc_auc(scores, labels) == pytest.approx(1.0)


def test_auc_perfect_anti():
    scores = np.array([0.9, 0.8, 0.7, 0.1, 0.2, 0.3])
    labels = np.array([False, False, False, True, True, True])
    assert _roc_auc(scores, labels) == pytest.approx(0.0)


def test_auc_direction_sensitive():
    """AUC > 0.5 when positives have higher scores than negatives,
    and < 0.5 when reversed."""
    scores = np.array([0.1, 0.2, 0.3, 0.4])
    labels_pos_high = np.array([False, False, True, True])
    assert _roc_auc(scores, labels_pos_high) > 0.5
    labels_pos_low = np.array([True, True, False, False])
    assert _roc_auc(scores, labels_pos_low) < 0.5


def test_auc_degenerate_all_same_class():
    """If only one class is present, AUC is undefined — return 0.5."""
    assert _roc_auc(np.array([1.0, 2.0, 3.0]), np.array([True, True, True])) == 0.5


def test_auc_ties_count_as_half():
    scores = np.array([0.5, 0.5])
    labels = np.array([True, False])
    # Tie → 0.5
    assert _roc_auc(scores, labels) == pytest.approx(0.5)


# --------------------------------------------------------------------------- #
# classify_observable thresholds
# --------------------------------------------------------------------------- #


def test_classify_truth_correlated():
    assert classify_observable(0.65, n_datapoints=100) == "TRUTH_CORRELATED"
    assert classify_observable(0.60, n_datapoints=100) == "TRUTH_CORRELATED"


def test_classify_uncorrelated():
    assert classify_observable(0.55, n_datapoints=100) == "UNCORRELATED"
    assert classify_observable(0.45, n_datapoints=100) == "UNCORRELATED"
    assert classify_observable(0.50, n_datapoints=100) == "UNCORRELATED"


def test_classify_anti_correlated():
    assert classify_observable(0.40, n_datapoints=100) == "ANTI_CORRELATED"
    assert classify_observable(0.30, n_datapoints=100) == "ANTI_CORRELATED"


def test_classify_null_on_few_datapoints():
    assert classify_observable(0.95, n_datapoints=10) == "NULL"
    assert classify_observable(0.05, n_datapoints=10) == "NULL"
    assert classify_observable(0.50, n_datapoints=39) == "NULL"


def test_classify_min_n_override():
    assert classify_observable(0.8, n_datapoints=10, min_n=5) == "TRUTH_CORRELATED"


def test_recommendation_text_contains_auc():
    rec = recommendation_for("TRUTH_CORRELATED", auc=0.72)
    assert "0.72" in rec
    rec = recommendation_for("ANTI_CORRELATED", auc=0.33)
    assert "0.33" in rec
    assert "WRONG" in rec


# --------------------------------------------------------------------------- #
# ObservableValue / Observable Protocol
# --------------------------------------------------------------------------- #


def test_observable_value_defaults():
    v = ObservableValue(scalar=1.0)
    assert v.scalar == 1.0
    assert v.per_source is None
    assert v.metadata == {}


def test_observable_protocol_runtime_checkable():
    class _Dummy:
        name = "dummy"
        higher_means_more_suspicious = False

        def observe(self, sources, prompt_tokens, choice_tokens):
            return ObservableValue(scalar=0.0)

    assert isinstance(_Dummy(), Observable)


def test_object_missing_name_still_usable_but_not_protocol():
    class _NoName:
        higher_means_more_suspicious = False
        def observe(self, sources, prompt_tokens, choice_tokens):
            return ObservableValue(scalar=0.0)
    # Missing class-level `name` attribute — not a full Protocol match,
    # but the probe harness uses `getattr(name, type(obs).__name__)` so
    # it still works.
    obj = _NoName()
    assert not hasattr(obj, "name")

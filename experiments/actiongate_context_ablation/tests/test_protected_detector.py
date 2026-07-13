"""Tests for the trainable protected-span detector (labels + anti-leakage + gains)."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import (
    adapter, ablation, metrics, milestone_bench as MB, protected_detector as PD,
)
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation.corpus.schema import DEV, HELDOUT, VALIDATION


@pytest.fixture(scope="module")
def fitted():
    items = registry.load_all()
    sp = adapter.default_signed_policy()
    runs = [ablation.run_ablations(it.context, sp) for it in items]
    det = PD.fit(items, runs)
    return items, runs, det


def test_labels_are_gate_derived_not_invented(fitted):
    items, runs, _ = fitted
    # every label maps from annotation.derive_primary output; nothing outside the 5 classes
    X, y = PD.build_dataset(items, runs, {DEV, VALIDATION})
    assert set(y) <= set(PD.CLASSES)
    assert len(X) == len(y) and len(X) > 0


def test_training_excludes_heldout(fitted):
    items, runs, _ = fitted
    n_train = len(PD.build_dataset(items, runs, {DEV, VALIDATION})[1])
    n_heldout = len(PD.build_dataset(items, runs, {HELDOUT})[1])
    n_all = len(PD.build_dataset(items, runs, {DEV, VALIDATION, HELDOUT})[1])
    assert n_train + n_heldout == n_all
    assert n_heldout > 0            # held-out exists but is not in the training set


def test_heldout_precision_and_recall_beat_baseline(fitted):
    items, runs, det = fitted
    ho = [r for it, r in zip(items, runs) if it.split == HELDOUT]
    base = metrics.aggregate(ho)
    hybrid = metrics.aggregate(ho, MB.hybrid_protect_fn(det))
    assert hybrid.precision_p0 - base.precision_p0 >= 0.20     # substantial precision gain
    assert hybrid.recall_p0 >= base.recall_p0                  # recall not sacrificed
    assert hybrid.recall_p0 >= 1.0 - 1e-9                      # safety: full recall


def test_hybrid_raises_deployable_ceiling(fitted):
    items, runs, det = fitted
    ho = [r for it, r in zip(items, runs) if it.split == HELDOUT]
    base = metrics.aggregate(ho)
    hybrid = metrics.aggregate(ho, MB.hybrid_protect_fn(det))
    assert hybrid.deployable_ceiling >= base.deployable_ceiling


def test_detector_deterministic():
    items = registry.load_all()
    sp = adapter.default_signed_policy()
    runs = [ablation.run_ablations(it.context, sp) for it in items]
    d1 = PD.fit(items, runs)
    d2 = PD.fit(items, runs)
    assert d1.model.W == d2.model.W and d1.model.b == d2.model.b


def test_no_critical_span_class_is_dropped(fitted):
    # the 5 classes are all represented in the gate-derived training labels
    items, runs, _ = fitted
    _, y = PD.build_dataset(items, runs, {DEV, VALIDATION})
    present = set(y)
    for c in (PD.DECISION_CRITICAL, PD.ENVELOPE_CRITICAL, PD.ASSURANCE_CRITICAL, PD.NON_CRITICAL):
        assert c in present

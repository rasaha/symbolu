"""Tests for the learned KV-importance probe (needs numpy; skipped otherwise).

These validate that the harness correctly distinguishes the cases that decide the
whole question: a probe helps only when the importance↔feature law TRANSFERS to a
held-out model.
"""
from __future__ import annotations

import pytest

np = pytest.importorskip("numpy")

from ndol.experiments.probe import (  # noqa: E402
    evaluate,
    recall_at_budget,
    synthetic_records,
)


def test_recall_perfect_and_chanceish():
    y = np.array([5.0, 4.0, 3.0, 2.0, 1.0, 0.0, -1.0, -2.0])
    g = [("m", 0)] * len(y)
    assert recall_at_budget(y.copy(), y, g, frac=0.25) == 1.0          # scores == importance
    assert recall_at_budget(-y, y, g, frac=0.25) == 0.0                # anti-correlated


def test_probe_beats_attention_when_law_transfers():
    W = {"attn_last": 1.0, "coherence": 0.8}                            # serving-safe law, uses both
    A = synthetic_records("A", W, seed=0)
    B = synthetic_records("B", W, seed=1)                              # SAME law on held-out
    r = evaluate(A, B)
    assert r["cheap_margin"] > 0.05                                    # serving-safe probe adds over attn


def test_probe_fails_when_law_flips_across_models():
    A = synthetic_records("A", {"attn_last": 1.0, "coherence": 0.8}, seed=0)
    B = synthetic_records("B", {"attn_last": 1.0, "coherence": -0.8}, seed=2)   # FLIPPED law
    r = evaluate(A, B)
    assert r["cheap_margin"] <= 0.05                                   # no reliable held-out gain


def test_pure_attention_law_gives_no_gain():
    W = {"attn_last": 1.5}                                             # importance = attention only
    A = synthetic_records("A", W, seed=0)
    B = synthetic_records("B", W, seed=1)
    r = evaluate(A, B)
    assert r["cheap_margin"] < 0.1                                     # probe ≈ attention


def test_reports_both_cheap_and_full():
    A = synthetic_records("A", {"attn_last": 1.0, "coherence": 0.8}, seed=0)
    B = synthetic_records("B", {"attn_last": 1.0, "coherence": 0.8}, seed=1)
    r = evaluate(A, B)
    assert "cheap_margin" in r and "full_margin" in r
    assert "coherence" in r["cheap_weights"]

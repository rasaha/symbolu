"""Tests for §3.6 alignment metrics."""

from __future__ import annotations

from symbolu_bcvf_llm.characterization.alignment import (
    aggregate_alignment,
    compute_alignment_metrics,
)


def test_alignment_none_when_no_truth_label():
    m = compute_alignment_metrics({0: 1.0, 1: 2.0, 2: 3.0}, truth_label=None)
    assert m is None


def test_alignment_hit_and_rank_1():
    m = compute_alignment_metrics(
        {0: 10.0, 1: 2.0, 2: 2.0}, truth_label=0
    )
    assert m is not None
    assert m.hit == 1
    assert m.rank == 1
    assert m.margin == 5.0


def test_alignment_rank_3_for_inverted():
    m = compute_alignment_metrics(
        {0: 1.0, 1: 10.0, 2: 5.0}, truth_label=0
    )
    assert m is not None
    assert m.hit == 0
    assert m.rank == 3


def test_aggregate_empty_returns_none():
    assert aggregate_alignment([None, None]) is None


def test_aggregate_hit_rate():
    ms = [
        compute_alignment_metrics({0: 10.0, 1: 1.0, 2: 1.0}, 0),
        compute_alignment_metrics({0: 10.0, 1: 1.0, 2: 1.0}, 0),
        compute_alignment_metrics({0: 1.0, 1: 10.0, 2: 1.0}, 0),
    ]
    agg = aggregate_alignment(ms)
    assert agg is not None
    assert agg.hit_rate == 2 / 3
    assert agg.n_cells == 3

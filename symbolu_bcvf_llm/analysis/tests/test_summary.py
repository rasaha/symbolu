"""Tests for symbolu_bcvf_llm.analysis.summary."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pytest

from symbolu_bcvf_llm.analysis.summary import (
    AnalysisReport,
    DecoderSummary,
    agreement_rate,
    analyze,
    dormancy_signal,
    flip_analysis,
    load_manifest,
    load_results_csv,
    paraphrase_audit,
    render_markdown,
    score_margins,
)


def _write_csv(path: Path, rows: list) -> None:
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "benchmark", "seed", "decoder", "question_id",
                "predicted", "correct", "latency_s", "scores",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def _make_rows(
    decoder: str,
    per_question: list,
    latency_ms: float = 1.0,
) -> list:
    """Given per_question = [(predicted, correct, scores_list), ...], build rows."""
    out = []
    for qid, (pred, corr, scores) in enumerate(per_question):
        out.append({
            "benchmark": "mock",
            "seed": 0,
            "decoder": decoder,
            "question_id": qid,
            "predicted": pred,
            "correct": str(bool(corr)),
            "latency_s": latency_ms / 1000.0,
            "scores": json.dumps(scores),
        })
    return out


# --------------------------------------------------------------------------- #
# Unit tests
# --------------------------------------------------------------------------- #


def test_flip_analysis_counts_wins_losses():
    a = DecoderSummary(
        name="a", n=4, accuracy=0.5, mean_latency_s=0.001,
        median_latency_s=0.001, p95_latency_s=0.001,
        correct=np.array([True, True, False, False]),
        predicted=np.array([0, 0, 1, 1]),
        scores=[[0.0]] * 4,
    )
    b = DecoderSummary(
        name="b", n=4, accuracy=0.5, mean_latency_s=0.001,
        median_latency_s=0.001, p95_latency_s=0.001,
        correct=np.array([False, True, True, False]),
        predicted=np.array([1, 0, 0, 2]),
        scores=[[0.0]] * 4,
    )
    f = flip_analysis(a, b)
    assert f.n_disagree == 3
    assert f.a_wins_b_loses == 1   # q=0
    assert f.a_loses_b_wins == 1   # q=2
    assert f.both_wrong == 1        # q=3
    assert f.net_gain_for_a == 0


def test_flip_analysis_length_mismatch_raises():
    a = DecoderSummary(
        name="a", n=2, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.array([True, True]), predicted=np.array([0, 0]),
        scores=[[0.0]] * 2,
    )
    b = DecoderSummary(
        name="b", n=3, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.array([True, True, True]),
        predicted=np.array([0, 0, 0]),
        scores=[[0.0]] * 3,
    )
    with pytest.raises(ValueError):
        flip_analysis(a, b)


def test_agreement_rate_all_agree():
    a = DecoderSummary(
        name="a", n=3, accuracy=1.0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.array([True, True, True]),
        predicted=np.array([0, 1, 2]),
        scores=[[0.0]] * 3,
    )
    b = DecoderSummary(
        name="b", n=3, accuracy=1.0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.array([True, True, True]),
        predicted=np.array([0, 1, 2]),
        scores=[[0.0]] * 3,
    )
    assert agreement_rate(a, b) == 1.0


def test_score_margins_basic():
    d = DecoderSummary(
        name="x", n=3, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.zeros(3, dtype=bool), predicted=np.zeros(3, dtype=np.int64),
        scores=[[-1.0, -3.0], [-0.5, -0.6], [-10.0, -10.0, -11.0]],
    )
    stats = score_margins(d)
    # Top-vs-second per row: 2.0 (−1 − −3), 0.1 (−0.5 − −0.6),
    # 0.0 (tie between top two at −10). Mean = (2.0 + 0.1 + 0) / 3.
    assert stats["mean"] == pytest.approx(0.7, rel=1e-6)
    assert stats["min"] == pytest.approx(0.0, abs=1e-12)
    assert stats["max"] == pytest.approx(2.0, rel=1e-6)


def test_dormancy_signal_extreme():
    trust = DecoderSummary(
        name="bcvf_trust", n=100, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.zeros(100, dtype=bool),
        predicted=np.arange(100) % 3,
        scores=[[0.0]] * 100,
    )
    blend = DecoderSummary(
        name="conventional_blend", n=100, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.zeros(100, dtype=bool),
        predicted=np.arange(100) % 3,    # identical to trust
        scores=[[0.0]] * 100,
    )
    d = dormancy_signal(trust, blend)
    assert d["agreement_rate"] == 1.0
    assert "extreme dormancy" in d["interpretation"]


def test_dormancy_signal_low():
    trust = DecoderSummary(
        name="t", n=10, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.zeros(10, dtype=bool),
        predicted=np.zeros(10, dtype=np.int64),
        scores=[[0.0]] * 10,
    )
    blend = DecoderSummary(
        name="b", n=10, accuracy=0, mean_latency_s=0,
        median_latency_s=0, p95_latency_s=0,
        correct=np.zeros(10, dtype=bool),
        predicted=np.ones(10, dtype=np.int64),   # totally disagree
        scores=[[0.0]] * 10,
    )
    d = dormancy_signal(trust, blend)
    assert d["agreement_rate"] == 0.0
    assert "low dormancy" in d["interpretation"]


def test_paraphrase_audit_reads_cache(tmp_path: Path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({
        "model_name": "m1",
        "split": "validation",
        "entries": {
            "0__1": "paraphrase zero seed one",
            "0__2": "paraphrase zero seed two, much longer",
            "1__1": "",   # empty — bad rewrite
        },
    }))
    audit = paraphrase_audit(cache, sample_n=3)
    assert audit is not None
    assert audit["total"] == 3
    assert audit["empty_rate"] == pytest.approx(1 / 3)
    assert audit["model_name"] == "m1"
    assert len(audit["samples"]) == 3


def test_paraphrase_audit_missing_file_returns_none(tmp_path: Path):
    assert paraphrase_audit(tmp_path / "does_not_exist.json") is None
    assert paraphrase_audit(None) is None


# --------------------------------------------------------------------------- #
# Integration tests
# --------------------------------------------------------------------------- #


def test_load_results_csv_roundtrip(tmp_path: Path):
    csv_path = tmp_path / "results.csv"
    rows = []
    rows.extend(_make_rows("vanilla", [
        (0, True, [-0.1, -1.0]),
        (0, False, [-0.5, -0.4]),
        (1, True, [-2.0, -1.0]),
    ]))
    rows.extend(_make_rows("conventional_blend", [
        (0, True, [-0.1, -1.0]),
        (1, True, [-1.0, -0.5]),
        (1, True, [-2.0, -1.0]),
    ]))
    rows.extend(_make_rows("bcvf_trust", [
        (0, True, [-0.1, -1.0]),
        (1, True, [-1.0, -0.5]),
        (1, True, [-2.0, -1.0]),
    ]))
    _write_csv(csv_path, rows)

    decoders = load_results_csv(csv_path)
    assert set(decoders.keys()) == {
        "vanilla", "conventional_blend", "bcvf_trust",
    }
    assert decoders["vanilla"].n == 3
    assert decoders["vanilla"].accuracy == pytest.approx(2 / 3)
    assert decoders["conventional_blend"].accuracy == 1.0
    assert decoders["bcvf_trust"].accuracy == 1.0


def test_analyze_end_to_end(tmp_path: Path):
    csv_path = tmp_path / "results.csv"
    rows = []
    # 5 questions, all decoders agree on everything → 100% dormancy.
    for decoder in ("vanilla", "conventional_blend", "bcvf_trust"):
        rows.extend(_make_rows(decoder, [
            (0, True, [-0.1, -1.0]),
            (0, True, [-0.1, -1.0]),
            (0, True, [-0.1, -1.0]),
            (0, True, [-0.1, -1.0]),
            (0, True, [-0.1, -1.0]),
        ]))
    _write_csv(csv_path, rows)

    report = analyze(results_csv=csv_path)
    assert "vanilla" in report.decoders
    assert report.verdict is not None
    assert report.verdict["classification"] == "NULL"  # Δ = 0
    assert report.dormancy_signal["agreement_rate"] == 1.0
    assert "extreme dormancy" in report.dormancy_signal["interpretation"]


def test_render_markdown_produces_nonempty_output(tmp_path: Path):
    csv_path = tmp_path / "results.csv"
    rows = []
    for decoder in ("vanilla", "conventional_blend", "bcvf_trust"):
        rows.extend(_make_rows(decoder, [
            (0, True, [-0.1, -1.0]),
            (1, False, [-0.5, -0.4]),
        ]))
    _write_csv(csv_path, rows)
    report = analyze(results_csv=csv_path)
    md = render_markdown(report)
    assert "§6 Phase 4 benchmark analysis" in md
    assert "Per-decoder results" in md
    assert "Paired comparisons" in md
    assert "Recommended next step" in md


def test_analyze_with_manifest_and_paraphrase_cache(tmp_path: Path):
    csv_path = tmp_path / "results.csv"
    manifest_path = tmp_path / "manifest.json"
    cache_path = tmp_path / "cache.json"

    rows = []
    for decoder in ("vanilla", "conventional_blend", "bcvf_trust"):
        rows.extend(_make_rows(decoder, [
            (0, True, [-0.1, -1.0]),
            (1, True, [-0.2, -2.0]),
        ]))
    _write_csv(csv_path, rows)

    manifest_path.write_text(json.dumps({
        "args": {"benchmark": "truthfulqa"},
        "environment": {},
        "model": {
            "name": "test-model",
            "compile_status": "compiled (dynamic=True)",
            "rewrite_seed_pair": [1, 2],
            "evaluation_seed": 1,
        },
        "outcome": "OK",
    }))

    cache_path.write_text(json.dumps({
        "model_name": "test-model",
        "split": "validation",
        "entries": {"0__1": "rewrite a", "0__2": "rewrite b"},
    }))

    report = analyze(
        results_csv=csv_path,
        manifest_path=manifest_path,
        paraphrase_cache_path=cache_path,
    )
    assert report.manifest["args"]["benchmark"] == "truthfulqa"
    assert report.paraphrase_audit is not None
    assert report.paraphrase_audit["total"] == 2

    md = render_markdown(report)
    assert "test-model" in md
    assert "Paraphrase audit" in md

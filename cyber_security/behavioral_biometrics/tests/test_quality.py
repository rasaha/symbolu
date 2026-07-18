"""Timing/sync diagnostics + instrumentation verdict."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics import quality, synthetic


def _sess(**kw):
    return synthetic.generate_session(participant="p", device="d", task_id="mixed_workflow",
                                      session_id="s", trial_id="t", seed=3, **kw)


def test_clean_session_ready():
    q = quality.analyze(_sess())
    assert q["verdict"] == quality.READY, q["reasons"]


def test_drop_rate_detected():
    s = _sess()
    s["collector_stats"]["dropped"] = int(len(s["events"]) * 0.5)
    q = quality.analyze(s)
    assert q["metrics"]["drop_rate"] > 0.1
    assert q["verdict"] != quality.READY
    assert "drop_rate" in q["reasons"]


def test_reorder_detected():
    s = _sess()
    ev = s["events"]
    for i in range(0, 200, 2):
        ev[i], ev[i + 1] = ev[i + 1], ev[i]
    q = quality.analyze(s)
    assert q["metrics"]["reorder_rate"] > 0.02


def test_duplicate_detected():
    s = _sess()
    s["events"].extend([dict(s["events"][0]), dict(s["events"][1])] * 30)
    q = quality.analyze(s)
    assert q["metrics"]["duplicate_rate"] > 0.005


def test_clock_drift_detected():
    s = _sess()
    # stretch monotonic vs source by 0.5% (5000 ppm)
    for e in s["events"]:
        e["t_monotonic"] = e["t_source"] * 1.005
    q = quality.analyze(s)
    assert q["metrics"]["clock_drift_ppm"] > 2000


def test_jitter_monotonic_in_noise():
    lo = quality.analyze(_sess(jitter_s=0.005))["metrics"]["jitter_ms"]
    hi = quality.analyze(_sess(jitter_s=0.05))["metrics"]["jitter_ms"]
    assert hi > lo


def test_timestamp_quantization_detected():
    s = _sess()
    grid = 0.05
    for e in s["events"]:
        e["t_source"] = round(e["t_source"] / grid) * grid  # snap to 50ms grid
    q = quality.analyze(s)
    assert q["metrics"]["quantization_ms"] >= 40


def test_sparse_session_low_active_fraction():
    s = _sess()
    # push a big idle gap into the middle
    for e in s["events"]:
        if e["t_source"] > 16:
            e["t_source"] += 60.0
    q = quality.analyze(s)
    assert q["metrics"]["active_fraction"] < 0.6


def test_cohort_verdict_counts():
    good = [quality.analyze(_sess()) for _ in range(3)]
    summary = quality.summarize_cohort(good)
    assert summary["counts"][quality.READY] == 3

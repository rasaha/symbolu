"""Adversarial / malformed input fixtures — the pipeline must handle each gracefully
(no crash, no silent wrong result) and detect the pathology where applicable."""

from __future__ import annotations

import json

import numpy as np
import pytest

from cyber_security.behavioral_biometrics import (
    collector,
    features,
    quality,
    schema,
    storage,
    synthetic,
)


def _kbd(seq, t, typ="key_down", kc="letter", kid="k:letter:0"):
    return schema.new_event(seq=seq, modality="keyboard", type=typ, t_monotonic=t, t_source=t,
                            t_receipt=t, payload={"key_class": kc, "key_id": kid})


def test_duplicate_timestamps_no_crash():
    events = [_kbd(i + 1, 1.0) for i in range(20)]  # all identical timestamps
    f = features._keyboard_features(events, features.DEFAULT.features)
    assert f["kbd.present"] == 1.0
    q = quality.analyze({"events": events, "collector_stats": {}})
    assert q["metrics"]["duplicate_rate"] >= 0.0


def test_zero_duration_keys():
    events = []
    for i in range(10):
        events.append(_kbd(2 * i + 1, i * 0.2, "key_down", kid=f"k:letter:{i}"))
        events.append(_kbd(2 * i + 2, i * 0.2, "key_up", kid=f"k:letter:{i}"))  # dwell == 0
    f = features._keyboard_features(events, features.DEFAULT.features)
    assert f["kbd.dwell.mean"] == 0.0  # handled, not NaN


def test_missing_key_up():
    events = [_kbd(i + 1, i * 0.2, "key_down", kid=f"k:letter:{i}") for i in range(10)]
    f = features._keyboard_features(events, features.DEFAULT.features)  # no key_up at all
    assert "kbd.flight_pp.mean" in f  # still produces flight features, no crash


def test_extreme_jitter_handled():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1, jitter_s=0.5)
    q = quality.analyze(s)
    assert q["verdict"] in (quality.DEGRADED, quality.NOT_READY, quality.READY)
    assert np.isfinite(q["metrics"]["jitter_ms"])


def test_sparse_activity_not_ready():
    events = [_kbd(i + 1, i * 3.0) for i in range(5)]  # 5 events over 12s
    q = quality.analyze({"session_meta": {}, "events": events, "collector_stats": {}})
    assert q["verdict"] == quality.NOT_READY


def test_clock_reset_midstream():
    events = [_kbd(i + 1, i * 0.1) for i in range(50)]
    for e in events[25:]:
        e["t_source"] -= 100.0  # clock jumps backward
    q = quality.analyze({"events": events, "collector_stats": {}})
    assert q["metrics"]["reorder_rate"] > 0.0  # detected as reordering


def test_collector_rejects_interleaved_sessions():
    col = collector.Collector()
    col.start_session(participant_pseudonym="p1", task_id="t", trial_id="t", device_id="d")
    with pytest.raises(RuntimeError):
        col.start_session(participant_pseudonym="p2", task_id="t", trial_id="t", device_id="d")


def test_device_id_leakage_prevented():
    s = synthetic.generate_session(participant="p", device="DEVICE_LEAK_42", task_id="t",
                                   session_id="s", trial_id="t", seed=1)
    rec = features.extract(s)
    names, _ = features.vectorize([rec], namespaces=("marginal", "coupling", "quality"))
    assert not any("DEVICE_LEAK_42" in n for n in names)


def test_context_label_leakage_prevented():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    # encode participant identity into a context label
    for e in s["events"]:
        e["context"]["task_stage"] = "stage_for_participant_p_SECRET"
    rec = features.extract(s)
    names, _ = features.vectorize([rec], namespaces=("marginal", "coupling", "quality"))
    assert not any("SECRET" in n for n in names)


def test_corrupted_event_file_raises(tmp_path):
    store = storage.SessionStore(tmp_path)
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s1",
                                   trial_id="t", seed=1)
    d = store.save_session(s)
    # corrupt the telemetry file with an invalid JSON line
    (d / "telemetry.jsonl").write_text('{"seq": 1, bad json')
    with pytest.raises(json.JSONDecodeError):
        store.load_session("p", "s1")


def test_empty_session_not_ready():
    q = quality.analyze({"session_meta": {}, "events": [], "collector_stats": {}})
    assert q["verdict"] == quality.NOT_READY
    assert "no_events" in q["reasons"]

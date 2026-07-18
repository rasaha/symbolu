"""Feature extraction: keyboard dwell/flight, pointer features, alignment, determinism."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics import features, schema, synthetic


def test_keyboard_dwell_flight_computed():
    events = []
    seq = 0
    # two keys, dwell 0.1, flight (press-to-press) 0.3
    for i, t in enumerate((0.0, 0.3)):
        seq += 1
        events.append(schema.new_event(seq=seq, modality="keyboard", type="key_down",
                                        t_monotonic=t, t_source=t, t_receipt=t,
                                        payload={"key_class": "letter", "key_id": f"k:letter:{i}"}))
        seq += 1
        events.append(schema.new_event(seq=seq, modality="keyboard", type="key_up",
                                        t_monotonic=t + 0.1, t_source=t + 0.1, t_receipt=t + 0.1,
                                        payload={"key_class": "letter", "key_id": f"k:letter:{i}"}))
    f = features._keyboard_features(events, features.DEFAULT.features)
    assert abs(f["kbd.dwell.mean"] - 0.1) < 1e-6
    assert abs(f["kbd.flight_pp.mean"] - 0.3) < 1e-6


def test_pointer_velocity_and_efficiency():
    events = []
    for i in range(10):
        t = i * 0.02
        events.append(schema.new_event(seq=i + 1, modality="pointer", type="move",
                                       t_monotonic=t, t_source=t, t_receipt=t,
                                       payload={"x": 0.1 * i, "y": 0.0}))
    f = features._pointer_features(events, features.DEFAULT.features)
    # straight horizontal line -> efficiency ~1, velocity = 0.1/0.02 = 5
    assert f["ptr.path_efficiency"] > 0.99
    assert abs(f["ptr.vel.mean"] - 5.0) < 1e-6


def test_deterministic_extraction():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=42, coupling_user_gain=0.5)
    a = features.extract(s)
    b = features.extract(s)
    assert a["marginal"] == b["marginal"]
    assert a["coupling"] == b["coupling"]


def test_identifiers_never_in_feature_vector():
    s = synthetic.generate_session(participant="secretUser", device="secretDevice", task_id="t",
                                   session_id="s", trial_id="t", seed=1)
    rec = features.extract(s)
    names, X = features.vectorize([rec], namespaces=("marginal", "coupling", "quality"))
    joined = " ".join(names)
    assert "secretUser" not in joined and "secretDevice" not in joined
    for ident in ("participant", "device_id", "session_id"):
        assert ident not in joined


def test_cross_modal_alignment_present():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    rec = features.extract(s)
    assert rec["coupling"]["coupling_available"] == 1.0


def test_vectorize_zero_fills_missing():
    r1 = {"marginal": {"a": 1.0, "b": 2.0}, "coupling": {}, "quality": {}, "meta": {}}
    r2 = {"marginal": {"a": 3.0}, "coupling": {}, "quality": {}, "meta": {}}
    names, X = features.vectorize([r1, r2], namespaces=("marginal",))
    assert X.shape == (2, 2)
    assert X[1, names.index("marginal::b")] == 0.0

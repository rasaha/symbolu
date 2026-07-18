"""Schema validation, sequencing, monotonic timestamps, fail-closed vocabularies."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import schema, synthetic


def _valid_session():
    return synthetic.generate_session(participant="p", device="d", task_id="fixed_copy",
                                      session_id="s", trial_id="t", seed=1)


def test_synthetic_session_is_valid():
    assert schema.is_valid(_valid_session())


def test_missing_meta_fields_flagged():
    s = _valid_session()
    del s["session_meta"]["participant_pseudonym"]
    v = {x["check"] for x in schema.validate_session(s)}
    assert "meta_missing" in v


def test_unknown_modality_fails_closed():
    s = _valid_session()
    s["events"][0]["modality"] = "brainwave"
    v = {x["check"] for x in schema.validate_session(s)}
    assert "unknown_modality" in v


def test_unknown_event_type_fails_closed():
    s = _valid_session()
    kbd = next(e for e in s["events"] if e["modality"] == "keyboard")
    kbd["type"] = "telepathy"
    v = {x["check"] for x in schema.validate_session(s)}
    assert "unknown_event_type" in v


def test_unknown_context_field_fails_closed():
    s = _valid_session()
    s["events"][0]["context"]["secret_screen_text"] = "hello"
    v = {x["check"] for x in schema.validate_session(s)}
    assert "unknown_context_field" in v


def test_raw_keyboard_content_is_a_violation():
    s = _valid_session()
    kbd = next(e for e in s["events"] if e["modality"] == "keyboard")
    kbd["payload"]["char"] = "e"
    v = {x["check"] for x in schema.validate_session(s)}
    assert "keyboard_raw_content" in v


def test_non_monotonic_seq_flagged():
    s = _valid_session()
    s["events"][5]["seq"] = s["events"][4]["seq"]  # duplicate/non-increasing
    v = {x["check"] for x in schema.validate_session(s)}
    assert "seq_not_monotonic" in v


def test_pointer_coord_range_checked():
    s = _valid_session()
    mv = next(e for e in s["events"] if e["modality"] == "pointer")
    mv["payload"]["x"] = 5.0  # not normalized
    v = {x["check"] for x in schema.validate_session(s)}
    assert "pointer_coord_range" in v


def test_key_class_controlled_vocabulary():
    s = _valid_session()
    kbd = next(e for e in s["events"] if e["modality"] == "keyboard")
    kbd["payload"]["key_class"] = "letterish"
    v = {x["check"] for x in schema.validate_session(s)}
    assert "keyboard_key_class" in v

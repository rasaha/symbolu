"""Privacy: key-class mapping, suppression, redaction, deletion, identifier scrubbing."""

from __future__ import annotations

import time

from cyber_security.behavioral_biometrics import collector, privacy, storage, synthetic


def test_key_class_never_returns_character():
    for k in ("a", "Z", "5", " ", "Backspace", "Enter", "Shift", "ArrowLeft", "!", "F5"):
        cls = privacy.key_to_class(k)
        assert cls in (
            "letter", "digit", "space", "backspace", "enter", "modifier",
            "navigation", "punctuation", "function", "other", "tab")
        assert len(cls) > 1  # a class label, not a single character


def test_safe_key_id_carries_no_character():
    kid = privacy.safe_key_id("a", salt="s")
    assert "a" not in kid.split(":")[-1] or kid.startswith("k:letter")
    # different salts -> different ids (not portable across sessions)
    assert privacy.safe_key_id("a", "s1") != privacy.safe_key_id("a", "s2")


def test_collector_strips_raw_content():
    col = collector.Collector()
    col.start_session(participant_pseudonym="p", task_id="t", trial_id="t", device_id="d")
    ev = col.ingest(modality="keyboard", type="key_down", t_source=0.1, raw_key="e",
                    payload={"char": "e", "text": "secret"})
    assert "char" not in ev["payload"] and "text" not in ev["payload"]
    assert ev["payload"]["key_class"] == "letter"


def test_sensitive_field_suppressed():
    pol = privacy.PrivacyPolicy(suppressed_regions={"password"})
    col = collector.Collector()
    col.start_session(participant_pseudonym="p", task_id="t", trial_id="t", device_id="d",
                      policy=pol)
    ev = col.ingest(modality="keyboard", type="key_down", t_source=0.1, raw_key="s",
                    context={"active_region": "password"})
    assert "key_id" not in ev["payload"]
    assert ev["payload"]["region"] == "SUPPRESSED"


def test_redact_session_removes_ids_in_sensitive_regions():
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s",
                                   trial_id="t", seed=1)
    # mark some events sensitive
    for e in s["events"][:10]:
        e["context"]["active_region"] = "ssn"
    pol = privacy.PrivacyPolicy(suppressed_regions={"ssn"})
    red = privacy.redact_session(s, pol)
    for e in red["events"][:10]:
        if e["modality"] == "keyboard":
            assert "key_id" not in e["payload"]
    assert not privacy.find_raw_content_leaks(red)


def test_scrub_identifiers_for_model_excludes_ids():
    meta = {"participant_pseudonym": "p1", "device_id": "d1", "session_id": "s1",
            "trial_id": "t1", "task_id": "copy", "device_class": "laptop", "os": "x",
            "role": "verification", "condition": "genuine"}
    scrubbed = privacy.scrub_identifiers_for_model(meta)
    for ident in ("participant_pseudonym", "device_id", "session_id", "trial_id"):
        assert ident not in scrubbed


def test_delete_session_removes_files(tmp_path):
    store = storage.SessionStore(tmp_path)
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s1",
                                   trial_id="t", seed=1)
    store.save_session(s)
    assert store.list_sessions()
    assert store.delete_session("p", "s1")
    assert not store.list_sessions()


def test_retention_purge(tmp_path):
    store = storage.SessionStore(tmp_path)
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s1",
                                   trial_id="t", seed=1)
    store.save_session(s)
    future = time.time() + 10 * 86400
    removed = store.purge_older_than(max_age_days=1, now_epoch=future)
    assert "p/s1" in removed
    assert not store.list_sessions()


def test_encrypted_storage_roundtrip(tmp_path):
    store = storage.SessionStore(tmp_path, passphrase="correct horse")
    s = synthetic.generate_session(participant="p", device="d", task_id="t", session_id="s1",
                                   trial_id="t", seed=1)
    store.save_session(s)
    # raw file is not plaintext json
    raw = (tmp_path / "p" / "s1" / "telemetry.jsonl").read_bytes()
    assert raw[:8] == storage._MAGIC
    back = store.load_session("p", "s1")
    assert len(back["events"]) == len(s["events"])


def test_consent_admissibility():
    c = privacy.Consent(participant_pseudonym="p", granted=True, purpose="pilot")
    assert c.is_admissible()
    c.revoked = True
    assert not c.is_admissible()

"""Browser-event -> schema adapter: mapping, privacy, quarantine, origin, consent."""

from __future__ import annotations

import pytest

from cyber_security.behavioral_biometrics import privacy, schema
from cyber_security.behavioral_biometrics.collector_app import adapter, fixtures
from cyber_security.behavioral_biometrics.version import ORIGIN_DEMO, ORIGIN_REAL


def test_adapt_produces_valid_schema_session():
    out = adapter.adapt_session(fixtures.sample_browser_session())
    assert schema.is_valid(out["session"])
    assert out["session"]["session_meta"]["data_origin"] == ORIGIN_DEMO


def test_raw_content_never_persisted():
    out = adapter.adapt_session(fixtures.sample_browser_session(inject_raw_char=True))
    # the event carrying a raw char is quarantined, not stored
    assert any("raw_content_field" in q["reason"] for q in out["quarantine"])
    assert privacy.find_raw_content_leaks(out["session"]) == []


def test_bad_key_class_quarantined():
    batch = fixtures.sample_browser_session()
    kd = next(e for e in batch["events"] if e["kind"] == "keydown")
    kd["key_class"] = "letterish"
    out = adapter.adapt_session(batch)
    assert any("bad_key_class" in q["reason"] for q in out["quarantine"])


def test_unknown_kind_quarantined():
    batch = fixtures.sample_browser_session()
    batch["events"].insert(0, {"kind": "brainwave", "ts_source": 1.0})
    out = adapter.adapt_session(batch)
    assert any("unknown_kind" in q["reason"] for q in out["quarantine"])


def test_out_of_range_pointer_quarantined():
    batch = fixtures.sample_browser_session()
    batch["events"].append({"kind": "pointermove", "ts_source": 5000.0, "ts_recv": 5000.1,
                            "x": 4.0, "y": 0.5})
    out = adapter.adapt_session(batch)
    assert any("coord_out_of_range" in q["reason"] for q in out["quarantine"])


def test_sensitive_field_suppressed():
    batch = fixtures.sample_browser_session(n_keys=5)
    # mark one keyboard event's region sensitive via a suppressed policy
    for e in batch["events"]:
        if e["kind"] == "keydown":
            e["active_region"] = "password"
            break
    pol = privacy.PrivacyPolicy(suppressed_regions={"password"})
    out = adapter.adapt_session(batch, policy=pol)
    supp = [e for e in out["session"]["events"]
            if e["context"].get("active_region") == "password"]
    assert supp and all("key_id" not in e["payload"] for e in supp)


def test_real_requires_consent():
    with pytest.raises(adapter.AdapterError):
        adapter.adapt_session(fixtures.sample_browser_session(origin=ORIGIN_REAL,
                                                              with_consent=False))


def test_real_with_consent_ok():
    out = adapter.adapt_session(fixtures.sample_browser_session(origin=ORIGIN_REAL,
                                                               with_consent=True))
    assert out["session"]["session_meta"]["data_origin"] == ORIGIN_REAL


def test_invalid_origin_rejected():
    batch = fixtures.sample_browser_session()
    batch["session_meta"]["data_origin"] = "WHATEVER"
    with pytest.raises(adapter.AdapterError):
        adapter.adapt_session(batch)


def test_sequence_numbers_monotonic():
    out = adapter.adapt_session(fixtures.sample_browser_session())
    seqs = [e["seq"] for e in out["session"]["events"]]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)


def test_timing_api_recorded():
    out = adapter.adapt_session(fixtures.sample_browser_session())
    assert "performance.now" in out["session"]["session_meta"]["timing_api"]

"""Session integrity manifest + data_origin / positive-verdict locks + service ingest."""

from __future__ import annotations

from cyber_security.behavioral_biometrics import features, quality, storage, verdicts
from cyber_security.behavioral_biometrics.collector_app import adapter, fixtures, manifest, service
from cyber_security.behavioral_biometrics.version import ORIGIN_DEMO, ORIGIN_REAL, REAL_MARKER


def _session(**kw):
    return adapter.adapt_session(fixtures.sample_browser_session(**kw))["session"]


# ---- manifest / integrity ----

def test_manifest_build_and_verify_intact():
    s = _session()
    m = manifest.build(s, quality_verdict="INSTRUMENTATION_READY")
    v = manifest.verify(s, m)
    assert v["intact"] and not v["problems"]


def test_corrupted_session_detected():
    s = _session()
    m = manifest.build(s, quality_verdict="INSTRUMENTATION_READY")
    s["events"].append(dict(s["events"][0]))  # tamper after the manifest was built
    v = manifest.verify(s, m)
    assert not v["intact"]
    assert "events_digest_mismatch" in v["problems"] or "n_events_mismatch" in v["problems"]


def test_consent_tamper_detected():
    s = _session()
    m = manifest.build(s, quality_verdict="INSTRUMENTATION_READY")
    s["session_meta"]["consent"]["granted"] = False
    v = manifest.verify(s, m)
    assert "consent_digest_mismatch" in v["problems"]


# ---- data_origin locks ----

def test_demo_origin_blocks_verdict():
    recs = [features.extract(_session(session_id=f"s{i}")) for i in range(3)]
    assert not verdicts.all_real(recs)                 # DEMO is not real
    assert verdicts.data_is_synthetic(recs)            # blocked as non-real


def test_real_origin_counts_as_real():
    recs = [features.extract(_session(origin=ORIGIN_REAL, with_consent=True, session_id=f"r{i}"))
            for i in range(3)]
    assert verdicts.all_real(recs)


def test_session_is_real_helper():
    assert verdicts.session_is_real({"data_origin": ORIGIN_REAL, "data_provenance": REAL_MARKER})
    assert not verdicts.session_is_real({"data_origin": ORIGIN_DEMO, "data_provenance": REAL_MARKER})
    # legacy record without data_origin falls back to provenance
    assert verdicts.session_is_real({"data_provenance": REAL_MARKER})


# ---- service ingest ----

def test_service_ingest_stores_and_is_neutral(tmp_path):
    store = storage.SessionStore(tmp_path)
    res = service.ingest_browser_session(store, fixtures.sample_browser_session(session_id="i0"))
    assert res["ok"] and "identity" not in res["completion_message"].lower()
    assert store.has_manifest("demo_p", "i0")


def test_degraded_session_stored_with_verdict_not_dropped(tmp_path):
    store = storage.SessionStore(tmp_path)
    # a short session -> NOT_READY, but must still be stored WITH its verdict
    batch = fixtures.sample_browser_session(session_id="short", n_keys=10, duration=5.0)
    res = service.ingest_browser_session(store, batch)
    assert res["ok"]
    assert res["instrumentation_verdict"] in ("INSTRUMENTATION_DEGRADED", "INSTRUMENTATION_NOT_READY")
    assert store.has_manifest("demo_p", "short")  # not silently dropped


def test_deterministic_reanalysis(tmp_path):
    store = storage.SessionStore(tmp_path)
    batch = fixtures.sample_browser_session(session_id="det")
    service.ingest_browser_session(store, batch)
    s = store.load_session("demo_p", "det")
    q1 = quality.analyze(s)
    q2 = quality.analyze(store.load_session("demo_p", "det"))
    assert q1["metrics"] == q2["metrics"]
    assert features.extract(s)["marginal"] == features.extract(s)["marginal"]

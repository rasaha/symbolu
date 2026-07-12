"""Collector-application readiness self-check."""

from __future__ import annotations

from cyber_security.behavioral_biometrics.collector_app import readiness


def test_readiness_emits_valid_verdict():
    r = readiness.check()
    assert r["verdict"] in (readiness.READY, readiness.DEGRADED, readiness.NOT_READY)
    assert r["checks"]["assets_present"]
    assert r["checks"]["adapter_roundtrip"]["schema_valid"]
    assert r["checks"]["server_bindable"]


def test_readiness_concerns_only_the_collector():
    assert "biometric" in readiness.check()["note"].lower()

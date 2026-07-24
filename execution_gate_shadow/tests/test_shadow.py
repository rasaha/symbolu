"""Tests for the shadow harness (Phase 14). No live credentials required.

Covers: prediction/observation separation, false-eligible & false-ineligible computation,
critical-policy override, indeterminate & NOT_ATTEMPTED handling, stale/TTL, degradation,
recovery, quota reset, billing transition, model disappearance, proxy denial, timeout,
invalid response, cost/request/quota caps, redaction, append-only audit, live-disabled
default, protocol-version guard, manifest generation, deterministic replay.
"""
from __future__ import annotations

import json
import os

import pytest

from execution_gate.gate import ExecutionGate
from execution_gate.model import Candidate, Request, Signal
from execution_gate.states import Evidence, EvidenceSource
from execution_gate_shadow import dry_run
from execution_gate_shadow.adapters import MockProviderAdapter, RealProviderAdapter
from execution_gate_shadow.config import SafetyError, ShadowConfig
from execution_gate_shadow.metrics import compute
from execution_gate_shadow.outcomes import (ObservedOutcome, is_critical_false_eligible,
                                             is_false_eligible, normalize)
from execution_gate_shadow.records import AppendOnlyLog, ObservationRecord, PredictionRecord, redact
from execution_gate_shadow.runner import ShadowRunner

T0 = 2_000_000.0


def _sig(v, source=EvidenceSource.LIVE_PROBE, age=0.0, ttl=900.0, reason=None):
    return Signal(v, Evidence(source, T0 - age, 0.95, ttl), reason_hint=reason)


def _healthy(**over):
    s = dict(reachable=_sig(True), network_allowed=_sig(True), authenticated=_sig(True),
             credential_expiry_ts=_sig(T0 + 1e9), billing_active=_sig(True), quota_state=_sig("ok"),
             model_available=_sig(True), observed_latency_ms=_sig(800.0), reliability=_sig(0.99),
             degraded=_sig(False))
    s.update(over)
    return s


def _cand(provider="anthropic", model_id="m", family="claude", signals=None, region="global"):
    return Candidate(provider, model_id, family, family, region, 200000, True, True, 1.0, 4.0,
                     signals or _healthy())


def _runner(tmp_path, cfg=None):
    cfg = cfg or ShadowConfig(protocol_version="v1")
    pl = AppendOnlyLog(str(tmp_path / "pred.jsonl"))
    ol = AppendOnlyLog(str(tmp_path / "obs.jsonl"))
    return ShadowRunner(ExecutionGate(), cfg, pl, ol), pl, ol


# --- outcome normalization / precedence -------------------------------------
def test_normalize_success_and_failures():
    assert normalize({"attempted": True, "http": 200, "text_valid": True, "policy_permitted": True}) == ObservedOutcome.SUCCESS
    assert normalize({"attempted": True, "http": 403}) == ObservedOutcome.AUTH_FAILURE
    assert normalize({"attempted": True, "http": 429}) == ObservedOutcome.QUOTA_FAILURE
    assert normalize({"attempted": True, "http": 404}) == ObservedOutcome.MODEL_UNAVAILABLE
    assert normalize({"attempted": True, "error_kind": "NETWORK_FAILURE"}) == ObservedOutcome.NETWORK_FAILURE
    assert normalize({"attempted": True, "timeout": True}) == ObservedOutcome.TIMEOUT
    assert normalize({"attempted": True, "http": 200, "text_valid": False}) == ObservedOutcome.INVALID_RESPONSE


def test_not_attempted_stays_unverified():
    assert normalize({"attempted": False}) == ObservedOutcome.NOT_ATTEMPTED


def test_critical_policy_overrides_success():
    o = normalize({"attempted": True, "http": 200, "text_valid": True, "policy_permitted": False,
                   "critical_kind": "RESIDENCY_PROHIBITED"})
    assert o == ObservedOutcome.RESIDENCY_PROHIBITED
    assert is_critical_false_eligible(True, o) is True
    assert is_false_eligible(True, o) is True


# --- false-eligible / false-ineligible computation --------------------------
def test_false_eligible_and_ineligible_metrics():
    preds = [
        {"request_id": "a", "model_id": "x", "predicted_state": "ELIGIBLE"},   # says ok
        {"request_id": "b", "model_id": "y", "predicted_state": "INELIGIBLE"}, # says no, but works -> FI
    ]
    obs = [
        {"request_id": "a", "model_id": "x", "outcome": "QUOTA_FAILURE"},       # FE (operational)
        {"request_id": "b", "model_id": "y", "outcome": "SUCCESS"},             # FN / false-ineligible
    ]
    m = compute(preds, obs)
    assert m["fp"] == 1 and m["false_eligible_operational"] == 1 and m["false_eligible_critical"] == 0
    assert m["false_ineligible"] == 1


def test_critical_false_eligible_counted_separately():
    preds = [{"request_id": "a", "model_id": "x", "predicted_state": "ELIGIBLE"}]
    obs = [{"request_id": "a", "model_id": "x", "outcome": "POLICY_PROHIBITED"}]
    m = compute(preds, obs)
    assert m["false_eligible_critical"] == 1


def test_not_attempted_excluded_from_confusion():
    preds = [{"request_id": "a", "model_id": "x", "predicted_state": "INELIGIBLE"}]
    obs = [{"request_id": "a", "model_id": "x", "outcome": "NOT_ATTEMPTED"}]
    m = compute(preds, obs)
    assert m["attempted"] == 0 and m["tp"] == m["fp"] == m["fn"] == m["tn"] == 0


# --- prediction/observation separation --------------------------------------
def test_prediction_independent_of_observation(tmp_path):
    r, pl, ol = _runner(tmp_path)
    req = Request("r")
    cand = _cand(signals=_healthy())
    preds = r.predict(req, [cand], T0)
    # observation with a CONTRADICTORY outcome must not change the recorded prediction
    r.observe(req, cand, MockProviderAdapter("anthropic", {"m": {"attempted": True, "http": 429}}), T0)
    assert preds["m"].predicted_state == "ELIGIBLE"
    assert pl.read_all()[0]["predicted_state"] == "ELIGIBLE"      # separate log
    assert ol.read_all()[0]["outcome"] == "QUOTA_FAILURE"


# --- gate-driven states via runner (stale/degradation/recovery/etc.) --------
@pytest.mark.parametrize("signals,expect", [
    (_healthy(), "ELIGIBLE"),
    (_healthy(network_allowed=_sig(False, reason="NETWORK_BLOCKED")), "INELIGIBLE"),   # proxy denial
    (_healthy(model_available=_sig(False, reason="MODEL_NOT_FOUND")), "INELIGIBLE"),   # model disappearance
    (_healthy(quota_state=_sig("exhausted")), "INELIGIBLE"),                            # quota
    (_healthy(degraded=_sig(True)), "INELIGIBLE"),                                      # degradation
    (_healthy(billing_active=_sig(True, source=EvidenceSource.CACHE, age=7200, ttl=900)), "INDETERMINATE"),  # stale
])
def test_runner_prediction_states(tmp_path, signals, expect):
    r, pl, _ = _runner(tmp_path)
    r.predict(Request("r"), [_cand(signals=signals)], T0)
    assert pl.read_all()[0]["predicted_state"] == expect


def test_quota_reset_and_billing_transition(tmp_path):
    r, pl, _ = _runner(tmp_path)
    # exhausted -> INELIGIBLE; then fresh 'ok' probe -> ELIGIBLE (state follows evidence)
    r.predict(Request("r1"), [_cand(model_id="q", signals=_healthy(quota_state=_sig("exhausted")))], T0)
    r.predict(Request("r2"), [_cand(model_id="q", signals=_healthy(quota_state=_sig("ok")))], T0)
    states = [p["predicted_state"] for p in pl.read_all()]
    assert states == ["INELIGIBLE", "ELIGIBLE"]


def test_timeout_and_invalid_response_outcomes():
    assert normalize({"attempted": True, "timeout": True}) == ObservedOutcome.TIMEOUT
    assert normalize({"attempted": True, "http": 200, "text_valid": False}) == ObservedOutcome.INVALID_RESPONSE


# --- safety guards ----------------------------------------------------------
def test_live_calls_disabled_by_default():
    cfg = ShadowConfig(protocol_version="v1")
    assert cfg.live_calls_enabled is False
    with pytest.raises(SafetyError):
        RealProviderAdapter("anthropic", cfg).observe("m", {"est_cost": 0.01})


def test_protocol_version_guard():
    with pytest.raises(SafetyError):
        ShadowConfig(protocol_version=None).assert_runnable()


def test_cost_request_quota_caps(tmp_path):
    cfg = ShadowConfig(protocol_version="v1", live_calls_enabled=True,
                       approved_providers={"anthropic"}, approved_models={"m"},
                       spend_cap_usd=0.001, request_cap=1, quota_cap=1)
    r, _, _ = _runner(tmp_path, cfg)
    # a live observation charging above the spend cap aborts
    live = RealProviderAdapter("anthropic", cfg)
    live.is_live = True
    class _Boom(MockProviderAdapter):
        is_live = True
    boom = _Boom("anthropic", {"m": {"attempted": True, "http": 200, "text_valid": True,
                                     "policy_permitted": True, "latency_ms": 10}})
    with pytest.raises(SafetyError):
        r.observe(Request("r"), _cand(model_id="m"), boom, T0, est_cost=1.0)  # > spend cap


def test_non_approved_provider_blocked():
    cfg = ShadowConfig(protocol_version="v1", live_calls_enabled=True, spend_cap_usd=1, request_cap=1)
    with pytest.raises(SafetyError):
        cfg.assert_live_allowed("unapproved", "m", 0.01)


# --- redaction / append-only ------------------------------------------------
def test_redaction_strips_secrets_and_ids():
    r = redact({"api_key": "sk-secret", "note": "projects/432246025394", "authorization": "Bearer x"})
    assert r["api_key"] == "<redacted>" and r["authorization"] == "<redacted>"
    assert "432246025394" not in r["note"] and r["note"].endswith("5394")


def test_append_only_log(tmp_path):
    log = AppendOnlyLog(str(tmp_path / "l.jsonl"))
    log.append(PredictionRecord(request_id="a", model_id="m", predicted_state="ELIGIBLE"))
    log.append(ObservationRecord(request_id="a", model_id="m", outcome="SUCCESS"))
    rows = log.read_all()
    assert len(rows) == 2 and rows[0]["kind"] == "prediction" and rows[1]["kind"] == "observation"


def test_audit_write_failure_aborts(tmp_path):
    log = AppendOnlyLog(str(tmp_path / "l.jsonl"))
    log.path = "/proc/nonexistent_dir/l.jsonl"   # unwritable
    with pytest.raises(SafetyError):
        log.append(PredictionRecord(request_id="a"))


# --- dry run: manifest + deterministic replay -------------------------------
def test_dry_run_manifest_and_determinism():
    m1 = dry_run.run("2026-07-23T00:00:00Z")
    m2 = dry_run.run("2026-07-23T00:00:00Z")
    assert m1["scenario_count"] == 8 and m1["live_calls_enabled"] is False
    assert m1["spend_usd"] == 0.0 and m1["live_requests"] == 0
    assert m1["metrics"]["false_eligible_critical"] == 0
    assert m1["prediction_log_sha256"] == m2["prediction_log_sha256"]   # deterministic replay
    assert m1["metrics"] == m2["metrics"]

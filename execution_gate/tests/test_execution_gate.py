"""Deterministic tests for the Execution Eligibility engine (Phase 12).

Covers every eligibility state, reason-code categories, fail-closed critical conditions,
configurable operational conditions, staleness, conflicting evidence, TTL expiry, the
ModelPolicy integration invariant, audit serialization, and deterministic replay.

Run: python3 -m pytest execution_gate/tests -q
"""
from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
if PKG not in sys.path:
    sys.path.insert(0, PKG)

import baselines as bl  # noqa: E402
import harness as H  # noqa: E402
from gate import ExecutionGate  # noqa: E402
from model import Candidate, GateConfig, Request, Signal  # noqa: E402
from policy import select as policy_select, PolicyWeights  # noqa: E402
from reason_codes import ReasonCode, normalize_raw  # noqa: E402
from registry import ExecutableRegistry, ExecStatus, ModelRecord  # noqa: E402
from states import (Evidence, EvidenceSource, EligibilityState, Verdict)  # noqa: E402

NOW = 1_000_000.0


def _ev(source=EvidenceSource.LIVE_PROBE, age=0.0, ttl=900.0, conf=0.95, raw=None):
    return Evidence(source, NOW - age, conf, ttl, raw)


def _sig(v, **kw):
    reason = kw.pop("reason", None)
    return Signal(v, _ev(**kw), reason_hint=reason)


def _healthy_signals():
    return dict(reachable=_sig(True), network_allowed=_sig(True), authenticated=_sig(True),
                credential_expiry_ts=_sig(NOW + 1e9), billing_active=_sig(True),
                quota_state=_sig("ok"), model_available=_sig(True),
                observed_latency_ms=_sig(500.0), reliability=_sig(0.99), degraded=_sig(False))


def _cand(**over):
    sigs = _healthy_signals()
    sigs.update(over.pop("signals", {}))
    base = dict(provider="anthropic", model_id="m1", family="claude", developer="anthropic",
                region="global", context_limit=200000, structured_output=True, tool_use=True,
                price_in_per_mtok=1.0, price_out_per_mtok=4.0)
    base.update(over)
    return Candidate(signals=sigs, **base)


def _req(**kw):
    return Request(kw.pop("request_id", "r"), **kw)


GATE = ExecutionGate()


# --- eligibility states -------------------------------------------------------
def test_state_eligible():
    d = GATE.evaluate(_cand(), _req(), NOW)
    assert d.state == EligibilityState.ELIGIBLE and d.selectable


def test_state_ineligible_on_critical_op_fail():
    d = GATE.evaluate(_cand(signals={"model_available": _sig(False, reason="MODEL_NOT_FOUND")}), _req(), NOW)
    assert d.state == EligibilityState.INELIGIBLE
    assert ReasonCode.MODEL_NOT_FOUND in d.reasons and not d.selectable


def test_state_conditionally_eligible_operational_unknown():
    # unknown reliability (operational) -> CONDITIONALLY_ELIGIBLE when allow_conditional
    c = _cand(signals={"reliability": Signal(None, _ev())})
    d = GATE.evaluate(c, _req(), NOW)
    assert d.state == EligibilityState.CONDITIONALLY_ELIGIBLE and d.selectable


def test_state_indeterminate_billing_unknown():
    c = _cand(signals={"billing_active": Signal(None, _ev())})
    d = GATE.evaluate(c, _req(), NOW)
    assert d.state == EligibilityState.INDETERMINATE and not d.selectable


# --- reason-code categories ---------------------------------------------------
@pytest.mark.parametrize("signals,req_kw,expect", [
    ({"network_allowed": _sig(False, reason="NETWORK_BLOCKED")}, {}, ReasonCode.NETWORK_BLOCKED),
    ({"authenticated": _sig(False, reason="AUTH_INVALID")}, {}, ReasonCode.AUTH_INVALID),
    ({"billing_active": _sig(False, reason="FREE_TIER_ONLY")}, {}, ReasonCode.FREE_TIER_ONLY),
    ({"quota_state": _sig("exhausted")}, {}, ReasonCode.QUOTA_EXHAUSTED),
    ({"quota_state": _sig("rate_limited")}, {}, ReasonCode.RATE_LIMITED),
    ({"model_available": _sig(False, reason="MODEL_NOT_FOUND")}, {}, ReasonCode.MODEL_NOT_FOUND),
])
def test_reason_codes(signals, req_kw, expect):
    d = GATE.evaluate(_cand(signals=signals), _req(**req_kw), NOW)
    assert expect in d.reasons


def test_reason_region_residency_enterprise_feature_context_cost():
    assert ReasonCode.REGION_UNAVAILABLE in GATE.evaluate(_cand(region="us"), _req(region_allowed={"eu"}), NOW).reasons
    assert ReasonCode.DATA_RESIDENCY_VIOLATION in GATE.evaluate(_cand(region="us"), _req(residency_required="eu"), NOW).reasons
    assert ReasonCode.PROVIDER_NOT_APPROVED in GATE.evaluate(_cand(provider="x"), _req(approved_providers={"anthropic"}), NOW).reasons
    assert ReasonCode.FEATURE_UNSUPPORTED in GATE.evaluate(_cand(tool_use=False), _req(features_required={"tool_use"}), NOW).reasons
    assert ReasonCode.CONTEXT_TOO_SMALL in GATE.evaluate(_cand(context_limit=1000), _req(context_tokens=5000), NOW).reasons
    assert ReasonCode.COST_LIMIT_EXCEEDED in GATE.evaluate(_cand(price_in_per_mtok=1000), _req(context_tokens=100000, cost_cap_usd=0.001), NOW).reasons


# --- fail-closed critical governance -----------------------------------------
def test_gov_unknown_fails_closed():
    # unknown network policy (governance) must NOT be eligible
    c = _cand(signals={"network_allowed": Signal(None, _ev())})
    d = GATE.evaluate(c, _req(), NOW)
    assert d.state == EligibilityState.INELIGIBLE


def test_require_billing_makes_unknown_ineligible():
    cfg = GateConfig(require_billing=True)
    c = _cand(signals={"billing_active": Signal(None, _ev())})
    d = ExecutionGate(cfg).evaluate(c, _req(), NOW)
    assert d.state == EligibilityState.INELIGIBLE   # not INDETERMINATE under require_billing


# --- staleness / TTL / conflict ----------------------------------------------
def test_stale_evidence_degrades_to_unknown():
    # billing evidence past TTL -> INDETERMINATE (not retained as PASS)
    c = _cand(signals={"billing_active": _sig(True, source=EvidenceSource.CACHE, age=7200, ttl=900)})
    d = GATE.evaluate(c, _req(), NOW)
    assert d.state == EligibilityState.INDETERMINATE
    billing = next(x for x in d.conditions if x.condition == "billing_active")
    assert billing.verdict == Verdict.UNKNOWN and billing.reason == ReasonCode.TELEMETRY_STALE


def test_ttl_boundary_fresh_vs_stale():
    fresh = _cand(signals={"reliability": _sig(0.99, age=800, ttl=900)})
    stale = _cand(signals={"reliability": _sig(0.99, age=1000, ttl=900)})
    assert GATE.evaluate(fresh, _req(), NOW).state == EligibilityState.ELIGIBLE
    assert GATE.evaluate(stale, _req(), NOW).state == EligibilityState.CONDITIONALLY_ELIGIBLE


def test_normalize_raw_maps_provider_strings():
    assert normalize_raw("Tunnel connection failed: 403 Forbidden") == ReasonCode.NETWORK_BLOCKED
    assert normalize_raw("InvalidClientTokenId") == ReasonCode.AUTH_INVALID
    assert normalize_raw("429 RESOURCE_EXHAUSTED free_tier") == ReasonCode.FREE_TIER_ONLY
    assert normalize_raw("404 model_not_found") == ReasonCode.MODEL_NOT_FOUND


# --- ModelPolicy integration invariant ---------------------------------------
def test_model_policy_never_selects_ineligible():
    reg = ExecutableRegistry(GATE)
    reg.upsert(ModelRecord("bad", _cand(model_id="bad", signals={"model_available": _sig(False)}), ExecStatus.ENUMERATED))
    reg.upsert(ModelRecord("good", _cand(model_id="good"), ExecStatus.ENUMERATED, observed_latency_ms=500))
    selectable, excluded = reg.evaluate(_req(), NOW)
    sel = policy_select(selectable, _req(), lambda rec: 0.8, PolicyWeights())
    assert sel.selected.internal_id == "good"
    assert all(rec.internal_id != "bad" for rec, _ in sel.ranked)


def test_model_policy_abstains_when_no_eligible():
    reg = ExecutableRegistry(GATE)
    reg.upsert(ModelRecord("bad", _cand(model_id="bad", signals={"network_allowed": _sig(False)}), ExecStatus.ENUMERATED))
    selectable, _ = reg.evaluate(_req(), NOW)
    sel = policy_select(selectable, _req(), lambda rec: 0.8)
    assert sel.abstained and sel.selected is None


# --- determinism / audit ------------------------------------------------------
def test_determinism_identical_decision():
    a = GATE.evaluate(_cand(), _req(), NOW).to_dict()
    b = GATE.evaluate(_cand(), _req(), NOW).to_dict()
    assert a == b


def test_audit_serialization_complete():
    d = GATE.evaluate(_cand(signals={"model_available": _sig(False)}), _req(), NOW).to_dict()
    assert d["state"] and d["reasons"] and d["conditions"]
    for c in d["conditions"]:
        assert "verdict" in c and "reason" in c and "criticality" in c and "evidence" in c


# --- harness end-to-end -------------------------------------------------------
def test_harness_runs_and_gate_beats_retry_on_violations():
    res = H.run()
    agg = res["aggregate"]
    # gate eliminates policy violations that retry-only commits
    assert agg["execution_gate_policy"]["policy_violation_rate"] == 0.0
    assert agg["retry_only"]["policy_violation_rate"] > 0.0
    # gate reduces failed calls to zero (never attempts an ineligible model)
    assert agg["execution_gate_policy"]["mean_failed_calls"] == 0.0
    # no false-eligible on critical (compliance) constraints
    assert agg["execution_gate_policy"]["false_eligible_critical"] == 0

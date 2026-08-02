"""Deterministic acceptance-scenario harness (design §30).

Loads the MERGED machine-readable scenario matrices and executes every scenario
applicable to the package core. Non-core scenarios are classified explicitly and
are NOT faked as passing.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ac_helpers import (
    ACTFP, T0, action, authorization, happy_signals, policy, request, signal, ts,
)
from ugence_action_clearance import (
    ClearanceStatus, ConstraintKind, ConsumptionStatus, EffectiveConstraint,
    SignalStatus, SignalTrustLevel, SignalType,
)

_REPO = Path(__file__).resolve().parents[4]
_CORE_JSON = _REPO / "docs/design/action_clearance/acceptance_scenarios.json"
_PREREQ_JSON = _REPO / "docs/design/action_clearance_prerequisites/acceptance_scenarios.json"

CORE_IMPLEMENTED = "CORE_IMPLEMENTED"
FUTURE_ADAPTER = "FUTURE_ADAPTER"
FUTURE_WORKFLOW = "FUTURE_WORKFLOW"
FUTURE_EXECUTION_LEDGER = "FUTURE_EXECUTION_LEDGER"
FUTURE_PRODUCT_INTEGRATION = "FUTURE_PRODUCT_INTEGRATION"

S = ClearanceStatus


def _b_clear(ev):
    return ev.evaluate(request(happy_signals()), policy()).status


def _b_denied(ev):
    return ev.evaluate(request(happy_signals(), auth=authorization(outcome="DENIED")), policy()).status


def _b_expired(ev):
    return ev.evaluate(request(happy_signals(), auth=authorization(expires=ts(hours=-1), issued=ts(hours=-3))), policy()).status


def _b_action_mismatch(ev):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": "OTHER"})]
    return ev.evaluate(request(sigs), policy()).status


def _b_target_mismatch(ev):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP, "target_ref": "other"})]
    return ev.evaluate(request(sigs), policy()).status


def _b_freeze(ev):
    return ev.evaluate(request(happy_signals() + [signal(SignalType.CHANGE_FREEZE, {"active": True})]), policy()).status


def _b_incident(ev):
    return ev.evaluate(request(happy_signals() + [signal(SignalType.ACTIVE_INCIDENT, {"active": True})]), policy()).status


def _b_actor_disabled(ev):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    return ev.evaluate(request(sigs), policy()).status


def _b_actor_unknown(ev):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "UNKNOWN"}),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    return ev.evaluate(request(sigs), policy()).status


def _b_signal_missing(ev):
    return ev.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"})]), policy()).status


def _b_signal_stale(ev):
    old = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP}, valid_until=ts(hours=-1))
    return ev.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), old]), policy()).status


def _b_untrusted(ev):
    pol = policy(trust_required_signal_types=(SignalType.ARTIFACT_IDENTITY,))
    art = signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})  # no provenance
    return ev.evaluate(request([signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}), art]), pol).status


def _b_policy_rejected(ev):
    sigs = happy_signals() + [signal(SignalType.POLICY_VALIDITY, {"accepted": False})]
    return ev.evaluate(request(sigs), policy()).status


def _b_consumed(ev):
    sigs = happy_signals() + [signal(SignalType.PRIOR_CONSUMPTION, {"state": ConsumptionStatus.CONSUMED.value})]
    return ev.evaluate(request(sigs), policy()).status


def _b_target_unavailable(ev):
    sigs = happy_signals() + [signal(SignalType.TARGET_AVAILABILITY, {"available": False})]
    return ev.evaluate(request(sigs), policy()).status


def _b_conflict(ev):
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, signal_id="a1"),
            signal(SignalType.ACTOR_STATUS, {"state": "DISABLED"}, signal_id="a2"),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    return ev.evaluate(request(sigs), policy()).status


def _b_shortened(ev):
    early = ts(minutes=5)
    sigs = [signal(SignalType.ACTOR_STATUS, {"state": "ACTIVE"}, valid_until=early),
            signal(SignalType.ARTIFACT_IDENTITY, {"action_fingerprint": ACTFP})]
    r = ev.evaluate(request(sigs), policy())
    assert r.valid_until <= early
    return r.status


def _b_idempotent(ev):
    r1 = ev.evaluate(request(happy_signals()), policy())
    r2 = ev.evaluate(request(list(reversed(happy_signals()))), policy())
    assert r1.result_fingerprint == r2.result_fingerprint
    return r1.status


def _b_constraint_conflict(ev):
    auth = authorization(structured=(EffectiveConstraint("amount", ConstraintKind.MAX, 100),))
    pol = policy(clearance_constraints=(EffectiveConstraint("amount", ConstraintKind.MAX, 200),))
    return ev.evaluate(request(happy_signals(), auth=auth), pol).status


# scenario_id -> (classification, builder|None, allowed statuses)
_CORE_MAP = {
    1: (CORE_IMPLEMENTED, _b_clear, {S.CLEAR}),
    2: (CORE_IMPLEMENTED, _b_denied, {S.BLOCK}),          # ineligible -> fail-closed BLOCK
    3: (CORE_IMPLEMENTED, _b_expired, {S.BLOCK}),
    4: (CORE_IMPLEMENTED, _b_action_mismatch, {S.BLOCK}),
    5: (CORE_IMPLEMENTED, _b_target_mismatch, {S.BLOCK}),
    6: (CORE_IMPLEMENTED, _b_freeze, {S.HOLD}),
    7: (CORE_IMPLEMENTED, _b_incident, {S.HOLD, S.ESCALATE}),
    8: (CORE_IMPLEMENTED, _b_actor_disabled, {S.BLOCK}),
    9: (CORE_IMPLEMENTED, _b_actor_unknown, {S.HOLD}),
    10: (CORE_IMPLEMENTED, _b_signal_missing, {S.HOLD}),
    11: (CORE_IMPLEMENTED, _b_signal_stale, {S.HOLD, S.BLOCK}),
    12: (CORE_IMPLEMENTED, _b_untrusted, {S.BLOCK}),
    13: (CORE_IMPLEMENTED, _b_policy_rejected, {S.BLOCK}),
    14: (CORE_IMPLEMENTED, _b_consumed, {S.BLOCK}),
    15: (CORE_IMPLEMENTED, _b_target_unavailable, {S.HOLD}),
    16: (CORE_IMPLEMENTED, _b_conflict, {S.ESCALATE, S.BLOCK}),
    17: (CORE_IMPLEMENTED, _b_shortened, {S.CLEAR}),
    18: (CORE_IMPLEMENTED, _b_idempotent, {S.CLEAR}),
    19: (CORE_IMPLEMENTED, _b_idempotent, {S.CLEAR}),
    20: (CORE_IMPLEMENTED, _b_constraint_conflict, {S.ESCALATE, S.BLOCK}),
    21: (FUTURE_ADAPTER, None, None),        # GitHub head-SHA change (profile)
    22: (FUTURE_ADAPTER, None, None),        # GitHub merge-group (profile)
    23: (FUTURE_WORKFLOW, None, None),       # dispatch-prohibited / receipt EXPIRED
    24: (FUTURE_EXECUTION_LEDGER, None, None),  # concurrent dispatch reservation
    25: (FUTURE_WORKFLOW, None, None),       # receipt REVOKED_BY_UPSTREAM_CHANGE
}


def _load(path):
    return json.loads(path.read_text())["scenarios"]


def test_core_json_present():
    assert _CORE_JSON.exists() and _PREREQ_JSON.exists()


@pytest.mark.parametrize("scenario", _load(_CORE_JSON), ids=lambda s: f"core-{s['id']}")
def test_core_scenarios(evaluator, scenario):
    sid = scenario["id"]
    assert sid in _CORE_MAP, f"scenario {sid} not classified"
    classification, builder, allowed = _CORE_MAP[sid]
    if classification != CORE_IMPLEMENTED:
        pytest.skip(f"scenario {sid} classified {classification} (not evaluator core)")
    status = builder(evaluator)
    assert status in allowed, f"scenario {sid}: got {status}, expected {allowed}"


def test_every_core_scenario_classified():
    ids = {s["id"] for s in _load(_CORE_JSON)}
    assert ids == set(_CORE_MAP)


def test_coverage_counts():
    counts = {}
    for classification, _, _ in _CORE_MAP.values():
        counts[classification] = counts.get(classification, 0) + 1
    # 20 core-implemented (incl. the fail-closed ActionGate-denied boundary)
    assert counts[CORE_IMPLEMENTED] == 20
    assert counts[FUTURE_ADAPTER] == 2
    assert counts[FUTURE_WORKFLOW] == 2
    assert counts[FUTURE_EXECUTION_LEDGER] == 1

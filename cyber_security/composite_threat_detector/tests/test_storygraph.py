"""Story-graph engine: structural assembly, gates, forward completion, dual-story."""

from __future__ import annotations

import pytest

from composite_threat_detector import (
    ACCOUNT_TAKEOVER_TRANSFER as ATO, BY_CASE, BenignSummary, FINANCIAL_ONTOLOGY,
    ObservedEvent, SequenceRiskAnalyzer, StoryGraph, financial, signals,
    story_bridge, story_evaluate, storygraph, storyverdict, story_match,
    would_complete,
)
from composite_threat_detector.storygraph import StoryNode, order, same_entity

V = storyverdict


def ev(op, seq, eid, **kw):
    d = {"tenant_id": "bank", "workflow_id": kw.pop("account", "acct-1"), "actor": "u1",
         "correlation_id": "s", "sequence_id": seq, "event_id": eid, "operation": op,
         "credential_scope": {"principal": "u1"}, "arguments": {}}
    d["account"] = d["workflow_id"]
    d.update(kw)
    return d


def _run(events, providers=None):
    az = SequenceRiskAnalyzer(FINANCIAL_ONTOLOGY, specs=(BY_CASE,), providers=providers)
    for e in events:
        az.observe(e)
    key = list(az.ledger._by_tenant["bank"].keys())[0]
    return az, key


GOOD = [
    ev("PASSWORD_RESET", "s:1", "1"),
    ev("DEVICE_REGISTER", "s:2", "2", device="dev-x"),
    ev("BENEFICIARY_ADD", "s:3", "3", beneficiary="bob"),
    ev("LIMIT_INCREASE", "s:4", "4"),
    ev("TRANSFER", "s:5", "5", beneficiary="bob", device="dev-x", amount="9000"),
]


def _events(az, key):
    return story_bridge.observed_events(az, "bank", key)


# --- structural assembly (not counting) -----------------------------------
def test_true_ato_is_threat_consistent():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key))
    assert v.category == V.THREAT_CONSISTENT_WITHOUT_BENIGN
    assert v.signal == signals.ESCALATE
    assert v.risk["entity_consistency"] == 1.0 and v.risk["ordering_consistency"] == 1.0


def test_wrong_beneficiary_does_not_escalate_despite_full_coverage():
    bad = GOOD[:-1] + [ev("TRANSFER", "s:5", "5", beneficiary="mallory",
                          device="dev-x", amount="9000")]
    az, key = _run(bad)
    v = story_evaluate(ATO, _events(az, key))
    assert v.risk["coverage"] == 1.0                 # all five events present
    assert v.risk["entity_consistency"] < 1.0        # but the beneficiary differs
    assert v.risk["gate_triggered"] is True
    assert v.category == V.PARTIAL_HARMFUL_MATCH
    assert v.signal == signals.OBSERVE               # NOT escalated on nouns alone


def test_out_of_order_does_not_escalate():
    # transfer occurs (position 2) before the beneficiary is added (position 5)
    reordered = [
        ev("PASSWORD_RESET", "s:1", "1"),
        ev("TRANSFER", "s:2", "2", beneficiary="bob", device="dev-x"),
        ev("DEVICE_REGISTER", "s:3", "3", device="dev-x"),
        ev("BENEFICIARY_ADD", "s:5", "5", beneficiary="bob"),
    ]
    az, key = _run(reordered)
    v = story_evaluate(ATO, _events(az, key))
    assert v.risk["ordering_consistency"] < 1.0
    assert v.signal == signals.OBSERVE


def test_outside_time_window_does_not_escalate():
    # reset far in the past relative to the transfer (gap >> max_gap)
    slow = [
        ev("PASSWORD_RESET", "s:1", "1"),
        ev("DEVICE_REGISTER", "s:2", "2", device="dev-x"),
        ev("BENEFICIARY_ADD", "s:3", "3", beneficiary="bob"),
        ev("TRANSFER", "s:99999", "5", beneficiary="bob", device="dev-x"),
    ]
    az, key = _run(slow)
    v = story_evaluate(ATO, _events(az, key))
    assert v.risk["timing_consistency"] < 1.0
    assert v.signal == signals.OBSERVE               # low-and-slow != one attack


# --- forward completion-gating --------------------------------------------
def test_forward_completion_gate():
    az, key = _run(GOOD[:4])                           # everything but the transfer
    events = _events(az, key)
    ok = story_bridge.proposed_event(
        financial.TRANSFER, entities={"account": "acct-1", "beneficiary": "bob",
                                      "device": "dev-x"})
    bad = story_bridge.proposed_event(
        financial.TRANSFER, entities={"account": "acct-1", "beneficiary": "mallory",
                                      "device": "dev-x"})
    assert would_complete(ATO, events, ok).completes is True
    assert would_complete(ATO, events, bad).completes is False
    v = story_evaluate(ATO, events, proposed=ok)
    assert v.category == V.WOULD_COMPLETE_PROHIBITED and v.signal == signals.ESCALATE


# --- dual-story (verified benign counter-story) ---------------------------
def test_verified_legitimate_fully_covers():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key),
                       benign=BenignSummary(status="VERIFIED_CONSISTENT"))
    assert v.category == V.VERIFIED_LEGITIMATE and v.signal == signals.OBSERVE


def test_legitimate_partially_covers_escalates_on_uncovered():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key),
                       benign=BenignSummary(status="PARTIALLY_CONSISTENT"))
    assert v.category == V.LEGITIMATE_PARTIALLY_COVERS and v.signal == signals.ESCALATE


def test_provider_unavailable_is_ambiguous_not_neutralized():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key),
                       benign=BenignSummary(status="PROVIDER_UNAVAILABLE",
                                            provider_unavailable=True))
    assert v.category == V.AMBIGUOUS_COMPETING and v.signal == signals.ESCALATE


def test_verified_but_contradicted_is_ambiguous():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key),
                       benign=BenignSummary(status="VERIFIED_CONSISTENT"),
                       facts={"destination_authorized": False})
    assert v.category == V.AMBIGUOUS_COMPETING
    assert any(c["name"] == "unauthorized_destination" for c in v.contradictions)


def test_confirmed_violation_overrides_claimed_purpose():
    az, key = _run(GOOD)
    v = story_evaluate(ATO, _events(az, key),
                       benign=BenignSummary(status="VERIFIED_CONSISTENT"),
                       facts={"confirmed_violation": True})
    assert v.category == V.CONFIRMED_VIOLATION and v.signal == signals.ESCALATE


# --- pentest "pretending to be bad" example -------------------------------
def test_pentest_within_scope_then_exceeds():
    az, key = _run(GOOD)
    events = _events(az, key)
    within_scope = story_evaluate(
        ATO, events, benign=BenignSummary(status="VERIFIED_CONSISTENT"))
    assert within_scope.category == V.VERIFIED_LEGITIMATE       # continue under monitoring
    exceeds = story_evaluate(
        ATO, events, benign=BenignSummary(
            status="PARTIALLY_CONSISTENT", scope_mismatch_fields=["destination"]))
    assert exceeds.category == V.LEGITIMATE_PARTIALLY_COVERS    # escalate on the excess


# --- engine invariants ----------------------------------------------------
def test_no_material_pattern_below_floor():
    az, key = _run([GOOD[0]])                           # single event
    v = story_evaluate(ATO, _events(az, key))
    assert v.category == V.NO_MATERIAL_PATTERN


def test_determinism_digests_stable():
    az, key = _run(GOOD)
    e = _events(az, key)
    a = story_match(ATO, e)
    b = story_match(ATO, e)
    assert a.match_digest == b.match_digest
    v1 = story_evaluate(ATO, e)
    v2 = story_evaluate(ATO, e)
    assert v1.verdict_digest == v2.verdict_digest


def test_all_verdict_signals_are_advisory_only():
    az, key = _run(GOOD)
    for benign in (None, BenignSummary(status="VERIFIED_CONSISTENT"),
                   BenignSummary(status="PARTIALLY_CONSISTENT")):
        v = story_evaluate(ATO, _events(az, key), benign=benign)
        assert v.signal in (signals.OBSERVE, signals.ESCALATE)
        assert v.signal not in signals.FORBIDDEN_SIGNALS


def test_storygraph_validation():
    with pytest.raises(ValueError):   # unknown node in edge
        StoryGraph("x", "1", "x",
                   nodes=(StoryNode("a", "F", is_completion=True),),
                   edges=(order("a", "nope"),))
    with pytest.raises(ValueError):   # no completion node
        StoryGraph("x", "1", "x", nodes=(StoryNode("a", "F"),))


def test_risk_vector_decomposition_direct():
    # two events, one edge satisfied, one entity edge failing
    events = [
        ObservedEvent("A", "1", 1, None, "u", {"k": "same"}),
        ObservedEvent("B", "2", 2, None, "u", {"k": "diff"}),
    ]
    g = StoryGraph("g", "1", "g",
                   nodes=(StoryNode("na", "A"), StoryNode("nb", "B", is_completion=True)),
                   edges=(order("na", "nb"), same_entity("na", "nb", "k")),
                   entity_gate=0.999)
    m = story_match(g, events)
    assert m.risk.coverage == 1.0
    assert m.risk.ordering_consistency == 1.0
    assert m.risk.entity_consistency == 0.0        # k differs
    assert m.risk.gate_triggered is True

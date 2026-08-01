"""Story-graph v2: dual-story per-node coverage, typed contradictions, minimal
completion witness/certificate, flat-recipe compilation, matcher UNAVAILABLE.
"""

from __future__ import annotations

from composite_threat_detector import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO,
    BANK_ASSISTED_TRANSFER_STORY, BY_CASE, DIGITAL_ONTOLOGY, FINANCIAL_ONTOLOGY,
    Authorization, ObservedEvent, SequenceRiskAnalyzer, completion_witness,
    contradictions, evaluate_proposed_action, financial, signals, story_bridge,
    story_from_recipe, story_match, storygraph, storyverdict,
)
from composite_threat_detector import recipes as R
from composite_threat_detector.storygraph import StoryGraph, StoryNode, before, same_account

V = storyverdict


def ev(op, seq, eid, **kw):
    d = {"tenant_id": "bank", "workflow_id": "acct-1", "actor": "u1",
         "correlation_id": "s", "sequence_id": seq, "event_id": eid, "operation": op,
         "account": "acct-1", "credential_scope": {"principal": "u1"}, "arguments": {}}
    d.update(kw)
    return d


SETUP = [ev("PASSWORD_RESET", "s:1", "1"),
         ev("DEVICE_REGISTER", "s:2", "2", device="dev-x"),
         ev("BENEFICIARY_ADD", "s:3", "3", beneficiary="bob")]


def _events(events):
    az = SequenceRiskAnalyzer(FINANCIAL_ONTOLOGY, specs=(BY_CASE,))
    for e in events:
        az.observe(e)
    key = list(az.ledger._by_tenant["bank"].keys())[0]
    return story_bridge.observed_events(az, "bank", key)


def _recovery():
    return Authorization(tag="customer_account_recovery", valid=True,
                         covered_operations=frozenset({"PASSWORD_RESET",
                                                       "DEVICE_REGISTER"}),
                         account="acct-1")


def _transfer(**ent):
    e = {"account": "acct-1", "beneficiary": "bob", "device": "dev-x", "amount": "9000"}
    e.update(ent)
    return story_bridge.proposed_event(financial.TRANSFER, entities=e)


# --- dual-story per-node coverage (the key finding) -----------------------
def test_recovery_partial_coverage_and_would_complete():
    r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.signal == signals.ESCALATE
    cov = r.legitimate_coverage
    assert cov["status"] == "PARTIAL"
    assert set(cov["covered_nodes"]) == {"reset", "device"}
    assert set(cov["uncovered_nodes"]) == {"benef", "xfer"}
    assert cov["per_node"]["reset"]["status"] == "COVERED"
    assert cov["per_node"]["benef"]["status"] == "UNCOVERED"


def test_bank_assisted_covers_completion():
    bank = Authorization(tag="bank_assisted_transaction", valid=True,
                         covered_operations=frozenset({"TRANSFER"}),
                         account="acct-1", beneficiary="bob", amount_cap=10000.0)
    r = evaluate_proposed_action(
        _events(SETUP), _transfer(), ATO,
        legitimate_stories=[ACCOUNT_RECOVERY_STORY, BANK_ASSISTED_TRANSFER_STORY],
        authorizations=[_recovery(), bank])
    assert r.legitimate_coverage["completion_covered"] is True
    assert r.category != V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


def test_self_declared_authorization_covers_nothing():
    unverified = Authorization(tag="customer_account_recovery", valid=False,
                               covered_operations=frozenset({"PASSWORD_RESET",
                                                             "DEVICE_REGISTER"}),
                               account="acct-1")
    r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[unverified])
    assert r.legitimate_coverage["status"] == "NONE"
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


# --- minimal completion witness / certificate -----------------------------
def test_completion_witness_is_minimal_and_necessary():
    w = completion_witness(ATO, _events(SETUP), _transfer())
    assert w is not None and w.completes is True
    assert w.completion_node == "xfer"
    assert w.proposed_is_necessary is True
    assert w.removal_breaks_completion is True
    # one witness event per required node
    assert set(w.witness_events) >= {"reset", "device", "benef", "xfer"}
    assert w.certificate_digest.startswith("sha-256:")
    # removing the proposed action -> story incomplete
    assert story_match(ATO, _events(SETUP)).is_complete() is False


def test_no_witness_when_proposed_does_not_complete():
    # wrong beneficiary -> entity gate fails -> not a completion
    w = completion_witness(ATO, _events(SETUP), _transfer(beneficiary="mallory"))
    assert w is None


# --- typed contradictions -------------------------------------------------
def test_typed_contradiction_device_binding_mismatch():
    # proposed transfer uses a different device than the enrolled one
    r = evaluate_proposed_action(_events(SETUP), _transfer(device="other-dev"), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    types = {c["type"] for c in r.contradictions}
    assert contradictions.DEVICE_BINDING_MISMATCH in types
    assert any(c["decisive"] and c["weakens"] == "HARMFUL"
               for c in r.contradictions if c["type"] == contradictions.DEVICE_BINDING_MISMATCH)


def test_typed_contradiction_destination_and_amount_from_facts():
    r = evaluate_proposed_action(
        _events(SETUP), _transfer(), ATO,
        legitimate_stories=[ACCOUNT_RECOVERY_STORY], authorizations=[_recovery()],
        facts={"destination_authorized": False, "amount_within_cap": False})
    types = {c["type"] for c in r.contradictions}
    assert contradictions.APPROVAL_DESTINATION_MISMATCH in types
    assert contradictions.APPROVAL_AMOUNT_EXCEEDED in types


def test_hard_policy_violation_overrides():
    r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()],
                                 facts={"confirmed_violation": True})
    assert r.category == V.HARD_POLICY_VIOLATION and r.signal == signals.ESCALATE


# --- flat-recipe -> graph compilation (backward compat) -------------------
def test_flat_recipe_compiles_to_graph_and_matches():
    exfil = next(r for r in R.DIGITAL_ONTOLOGY.recipes
                 if r.recipe_id == "DATA_EXFILTRATION_ASSEMBLY")
    g = story_from_recipe(exfil, completion_fragments={"EGRESS_PATH"})
    assert any(n.is_completion for n in g.nodes)
    # feed the exfil events through the analyzer, then match the compiled graph
    from demos import scenarios
    az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=(BY_CASE,))
    for e in scenarios.exfiltration_events:
        az.observe(e)
    key = list(az.ledger._by_tenant["acme"].keys())[0]
    m = story_match(g, story_bridge.observed_events(az, "acme", key))
    assert m.risk.coverage == 1.0 and m.completion_present


# --- matcher UNAVAILABLE / determinism ------------------------------------
def test_matcher_unavailable_on_limit_breach():
    # many candidate events per node blows the combination cap -> UNAVAILABLE
    events = [ObservedEvent("A", f"a{i}", i, None, "u", {}) for i in range(6)]
    events += [ObservedEvent("B", f"b{i}", 100 + i, None, "u", {}) for i in range(6)]
    events += [ObservedEvent("C", f"c{i}", 200 + i, None, "u", {}) for i in range(6)]
    events += [ObservedEvent("D", f"d{i}", 300 + i, None, "u", {}) for i in range(6)]
    events += [ObservedEvent("E", f"e{i}", 400 + i, None, "u", {}) for i in range(6)]
    g = StoryGraph("g", "1", "g",
                   nodes=tuple(StoryNode(n, n, is_completion=(n == "E"))
                               for n in "ABCDE"))
    m = story_match(g, events)
    assert m.unavailable is True


def test_determinism_witness_and_verdict_digests():
    e = _events(SETUP)
    a = evaluate_proposed_action(e, _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    b = evaluate_proposed_action(e, _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    assert a.verdict_digest == b.verdict_digest
    assert a.completion_witness["certificate_digest"] == b.completion_witness["certificate_digest"]


def test_advisory_signals_only():
    for facts in ({}, {"confirmed_violation": True}, {"destination_authorized": False}):
        r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                     legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                     authorizations=[_recovery()], facts=facts)
        assert r.signal in (signals.OBSERVE, signals.ESCALATE, signals.UNAVAILABLE)

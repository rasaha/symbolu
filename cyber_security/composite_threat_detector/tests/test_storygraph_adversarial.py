"""Adversarial validation of the StoryGraph vertical slice.

Focused adversarial + implementation audit of the existing account-takeover
slice (no new domains, no learned scoring). Each section maps to the phase spec:

* §4  non-mutation during hypothetical evaluation
* §5  witness minimality — per-event removal proofs + versioned tie-break
* §6  exact entity binding (wrong / competing beneficiary·device·account)
* §7  ordering + timing discrimination
* §8  CONTRADICTS explicit-incompatibility semantics
* §9  non-compensatory structural gates (coverage cannot buy back a failed gate)
* §10 verified legitimate-context stress (partial / self-declared / full)
* §13 multiplicity / competing optimal bindings
* §14 evaluation binding + stale detection
"""

from __future__ import annotations

import pytest

from composite_threat_detector import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO, BY_CASE,
    FINANCIAL_ONTOLOGY, Authorization, ObservedEvent, SequenceRiskAnalyzer,
    evaluate_proposed_action, financial, story_bridge, story_match, storyverdict,
)
from composite_threat_detector import financial as F
from composite_threat_detector.storygraph import (
    StoryGraph, StoryNode, contradicts, order,
)

V = storyverdict


# ---------------------------------------------------------------------------
# builders (engine-level ObservedEvent views, for precise control)
# ---------------------------------------------------------------------------
def oe(frag, eid, pos, **ent):
    return ObservedEvent(fragment_id=frag, event_id=eid, position=pos, epoch=None,
                         actor="u1", entities=dict(ent))


def _assembly(**over):
    """A clean, complete pre-commit assembly (reset·device·benef), account acct-1."""
    return [
        oe(F.CRED_RESET, "e-reset", 1, account="acct-1"),
        oe(F.DEVICE_NEW, "e-device", 2, account="acct-1", device="dev-x"),
        oe(F.BENEFICIARY_ADD, "e-benef", 3, account="acct-1", beneficiary="bob"),
    ]


def _transfer(**over):
    ent = {"account": "acct-1", "beneficiary": "bob", "device": "dev-x", "amount": "9000"}
    ent.update(over)
    return oe(F.TRANSFER, "e-xfer", 99, **ent)


# ===========================================================================
# §4  NON-MUTATION during hypothetical evaluation
# ===========================================================================
def _ev(op, seq, eid, **kw):
    d = {"tenant_id": "bank", "workflow_id": "acct-1", "actor": "u1",
         "correlation_id": "s", "sequence_id": seq, "event_id": eid, "operation": op,
         "account": "acct-1", "credential_scope": {"principal": "u1"}, "arguments": {}}
    d.update(kw)
    return d


def _live_analyzer():
    az = SequenceRiskAnalyzer(FINANCIAL_ONTOLOGY, specs=(BY_CASE,))
    for e in [_ev("PASSWORD_RESET", "s:1", "1"),
              _ev("DEVICE_REGISTER", "s:2", "2", device="dev-x"),
              _ev("BENEFICIARY_ADD", "s:3", "3", beneficiary="bob")]:
        az.observe(e)
    key = list(az.ledger._by_tenant["bank"].keys())[0]
    return az, key


def test_evaluate_does_not_record_into_ledger():
    az, key = _live_analyzer()
    asm = az.ledger.get("bank", key)
    before_ids = set(asm.seen_event_ids)
    before_n = len(asm.instances)

    events = story_bridge.observed_events(az, "bank", key)
    proposed = story_bridge.proposed_event(financial.TRANSFER, entities={
        "account": "acct-1", "beneficiary": "bob", "device": "dev-x", "amount": "9000"})
    r = evaluate_proposed_action(events, proposed, ATO)

    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY  # it *would* complete...
    # ...but the ledger is unchanged: the proposed action was never recorded.
    assert asm.seen_event_ids == before_ids
    assert len(asm.instances) == before_n
    assert "e-xfer" not in asm.seen_event_ids and "proposed" not in asm.seen_event_ids


def test_evaluation_is_deterministic_and_input_list_unmodified():
    events = _assembly()
    original = list(events)
    proposed = _transfer()
    r1 = evaluate_proposed_action(events, proposed, ATO)
    r2 = evaluate_proposed_action(events, proposed, ATO)
    assert r1.verdict_digest == r2.verdict_digest            # deterministic
    assert r1.completion_witness["certificate_digest"] == \
        r2.completion_witness["certificate_digest"]
    assert events == original and len(events) == 3           # caller list untouched


def test_observed_events_stable_across_repeated_reads():
    az, key = _live_analyzer()
    a = [e.to_tuple() if hasattr(e, "to_tuple") else
         (e.fragment_id, e.event_id, e.position) for e in
         story_bridge.observed_events(az, "bank", key)]
    b = [(e.fragment_id, e.event_id, e.position) for e in
         story_bridge.observed_events(az, "bank", key)]
    assert a == b


# ===========================================================================
# §5  WITNESS MINIMALITY — per-event removal proofs + versioned tie-break
# ===========================================================================
def test_witness_minimality_every_element_necessary():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO)
    w = r.completion_witness
    assert w["minimality_verified"] is True
    assert w["tie_break_rule_version"] == V.TIE_BREAK_RULE_VERSION
    # one removal proof per witness element (incl. the proposed action)
    removed = {p["removed_event"] for p in w["removal_proofs"]}
    assert "e-xfer" in removed and "e-reset" in removed
    for p in w["removal_proofs"]:
        assert p["broke_completion"] is True and p["still_complete"] is False
        assert p["unsatisfied"] != "none"


def test_removing_proposed_breaks_completion():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO)
    w = r.completion_witness
    assert w["removal_breaks_completion"] is True
    assert w["proposed_is_necessary"] is True
    prop_proof = next(p for p in w["removal_proofs"] if p["removed_event"] == "e-xfer")
    assert prop_proof["broke_completion"] is True


# ===========================================================================
# §6  EXACT ENTITY BINDING
# ===========================================================================
@pytest.mark.parametrize("field,bad", [
    ("beneficiary", "eve"), ("device", "dev-evil"), ("account", "acct-2")])
def test_wrong_single_entity_trips_gate_and_blocks_completion(field, bad):
    r = evaluate_proposed_action(_assembly(), _transfer(**{field: bad}), ATO)
    assert r.category != V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.completion_witness is None
    assert r.risk_after["gate_triggered"] is True


def test_correct_binding_completes():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO)
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.risk_after["entity_consistency"] == 1.0


def test_competing_beneficiary_binds_the_matching_event():
    # two beneficiary-add events; only "bob" matches the transfer beneficiary.
    events = _assembly() + [
        oe(F.BENEFICIARY_ADD, "e-benef2", 4, account="acct-1", beneficiary="eve")]
    r = evaluate_proposed_action(events, _transfer(beneficiary="bob"), ATO)
    # the matcher must pick the bob event to satisfy SAME_ENTITY(beneficiary).
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.completion_witness["witness_events"]["benef"] == "e-benef"


# ===========================================================================
# §7  ORDERING + TIMING
# ===========================================================================
def _full(order_ok=True, gap=3):
    # a fully-present assembly incl. transfer, for match-level order/timing tests.
    xfer_pos = 10 if order_ok else 0
    return [
        oe(F.CRED_RESET, "e-reset", 1, account="acct-1"),
        oe(F.DEVICE_NEW, "e-device", 2, account="acct-1", device="dev-x"),
        oe(F.BENEFICIARY_ADD, "e-benef", 3, account="acct-1", beneficiary="bob"),
        oe(F.TRANSFER, "e-xfer", 1 + gap if order_ok else xfer_pos,
           account="acct-1", beneficiary="bob", device="dev-x", amount="9000"),
    ]


def test_out_of_order_trips_ordering_gate():
    m = story_match(ATO, _full(order_ok=False))
    assert m.risk.ordering_consistency < 0.999
    assert m.risk.gate_triggered and not m.is_complete()


def test_outside_time_window_trips_timing_gate():
    m = story_match(ATO, _full(order_ok=True, gap=5000))   # > within max_gap 1000
    assert m.risk.timing_consistency < 0.999
    assert m.risk.gate_triggered and not m.is_complete()


def test_equal_coordinate_flagged_ordering_ambiguous():
    events = [
        oe(F.CRED_RESET, "e-reset", 5, account="acct-1"),
        oe(F.DEVICE_NEW, "e-device", 5, account="acct-1", device="dev-x"),
        oe(F.BENEFICIARY_ADD, "e-benef", 5, account="acct-1", beneficiary="bob"),
        oe(F.TRANSFER, "e-xfer", 5, account="acct-1", beneficiary="bob",
           device="dev-x", amount="9000"),
    ]
    m = story_match(ATO, events)
    assert m.ordering_ambiguous is True
    assert not m.is_complete()


# ===========================================================================
# §8  CONTRADICTS explicit-incompatibility semantics
# ===========================================================================
def _contra_graph(condition):
    return StoryGraph("c", "1", "c",
                      nodes=(StoryNode("a", "A"),
                             StoryNode("b", "B", is_completion=True),
                             StoryNode("conf", "CONF")),
                      edges=(order("a", "b"), contradicts("b", "conf", condition)))


def test_contradicts_requires_explicit_condition():
    with pytest.raises(ValueError):
        contradicts("b", "conf", "")


def test_contradicts_same_entity_only_fires_when_entities_match():
    g = _contra_graph("SAME_ENTITY:account")
    same = [oe("A", "1", 1, account="x"), oe("B", "2", 2, account="x"),
            oe("CONF", "3", 3, account="x")]
    diff = [oe("A", "1", 1, account="x"), oe("B", "2", 2, account="x"),
            oe("CONF", "3", 3, account="y")]
    assert story_match(g, same).contradicts_triggered          # same account => fires
    assert not story_match(g, diff).contradicts_triggered      # different => inert


def test_contradicts_both_present_always_fires():
    g = _contra_graph("BOTH_PRESENT")
    ev = [oe("A", "1", 1), oe("B", "2", 2), oe("CONF", "3", 3)]
    m = story_match(g, ev)
    assert m.contradicts_triggered and m.is_complete() is False
    rec = m.contradicts_triggered[0]
    assert rec["weakens"] == "HARMFUL" and rec["severity"] == "decisive"


def test_contradicts_graph_rejects_missing_condition_at_construction():
    from composite_threat_detector.storygraph import Edge, CONTRADICTS
    with pytest.raises(ValueError):
        StoryGraph("c", "1", "c",
                   nodes=(StoryNode("b", "B", is_completion=True),
                          StoryNode("conf", "CONF")),
                   edges=(Edge(CONTRADICTS, "b", "conf"),))   # empty incompatible_when


# ===========================================================================
# §9  NON-COMPENSATORY gates — coverage cannot buy back a failed gate
# ===========================================================================
def test_full_coverage_cannot_compensate_failed_entity_gate():
    m = story_match(ATO, _full(order_ok=True))          # complete + correct
    assert m.risk.coverage == 1.0 and not m.risk.gate_triggered
    # now break the entity binding while keeping full coverage
    bad = _full(order_ok=True)
    bad[-1] = oe(F.TRANSFER, "e-xfer", 4, account="acct-1", beneficiary="eve",
                 device="dev-x", amount="9000")
    mb = story_match(ATO, bad)
    assert mb.risk.coverage == 1.0                       # coverage still maximal
    assert mb.risk.entity_consistency < 0.999            # but a gate fails
    assert mb.risk.gate_triggered
    assert mb.risk.harmful_score < ATO.threat_threshold  # capped below threat


# ===========================================================================
# §10  VERIFIED LEGITIMATE-CONTEXT stress
# ===========================================================================
def _recovery(valid=True, account="acct-1"):
    return Authorization(tag="customer_account_recovery", valid=valid,
                         covered_operations=frozenset({"PASSWORD_RESET",
                                                       "DEVICE_REGISTER"}),
                         account=account)


def test_partial_recovery_leaves_transfer_uncovered():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    # recovery covers reset+device only => transfer completes uncovered.
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY
    assert r.legitimate_coverage["status"] == "PARTIAL"
    assert "xfer" in r.legitimate_coverage["uncovered_nodes"]


def test_self_declared_authorization_covers_nothing():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery(valid=False)])
    assert r.legitimate_coverage["status"] == "NONE"
    assert r.category == V.WOULD_COMPLETE_PROHIBITED_CAPABILITY


def test_wrong_account_authorization_does_not_cover():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery(account="acct-999")])
    assert r.legitimate_coverage["status"] == "NONE"


# ===========================================================================
# §13  MULTIPLICITY / competing optimal bindings
# ===========================================================================
def test_duplicate_equivalent_candidates_report_multiple_optimal():
    # two identical beneficiary-add events (both "bob") => two optimal bindings.
    events = _full(order_ok=True) + [
        oe(F.BENEFICIARY_ADD, "e-benef-dup", 3, account="acct-1", beneficiary="bob")]
    m = story_match(ATO, events)
    assert m.multiple_optimal_bindings >= 2
    assert m.is_complete()   # still complete; either binding satisfies the edges


# ===========================================================================
# §14  EVALUATION BINDING + stale detection
# ===========================================================================
def test_result_carries_evaluation_binding():
    r = evaluate_proposed_action(_assembly(), _transfer(), ATO, policy_version="p1")
    b = r.evaluation_binding
    assert b["graph_id_version"] == ATO.ref and b["policy_version"] == "p1"
    for k in ("proposed_action_identity", "payload_digest",
              "trusted_context_snapshot_digest", "assembly_state_digest"):
        assert b[k]


def test_stale_detected_on_assembly_change():
    events = _assembly()
    r = evaluate_proposed_action(events, _transfer(), ATO, policy_version="p1")
    b = r.evaluation_binding
    # unchanged inputs => not stale
    assert V.is_stale(b, events, current_policy_version="p1")["stale"] is False
    # a new assembly event => stale
    changed = events + [oe(F.LIMIT_UP, "e-limit", 4, account="acct-1")]
    s = V.is_stale(b, changed, current_policy_version="p1")
    assert s["stale"] is True and "assembly_state_changed" in s["reasons"]


def test_stale_detected_on_policy_and_context_change():
    events = _assembly()
    r = evaluate_proposed_action(events, _transfer(), ATO, policy_version="p1",
                                 authorizations=[_recovery()],
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY])
    b = r.evaluation_binding
    s_pol = V.is_stale(b, events, current_policy_version="p2",
                       current_authorizations=[_recovery()])
    assert "policy_version_changed" in s_pol["reasons"]
    s_ctx = V.is_stale(b, events, current_policy_version="p1",
                       current_authorizations=[])   # authorization removed
    assert "trusted_context_changed" in s_ctx["reasons"]

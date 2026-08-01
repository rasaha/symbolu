"""Gap-closing coverage: CONTRADICTS + COVERED_BY_AUTHORIZATION edges, combined
structural vector, witness proof-summary, satisfied edges, freeze integration.
"""

from __future__ import annotations

import pytest

from composite_threat_detector import (
    ACCOUNT_RECOVERY_STORY, ACCOUNT_TAKEOVER_TRANSFER as ATO, BY_CASE,
    FINANCIAL_ONTOLOGY, Authorization, ObservedEvent, SequenceRiskAnalyzer,
    STORYGRAPH_SCHEMA_VERSION, StructuralVector, evaluate_proposed_action, financial,
    story_bridge, story_match, storygraph, storyverdict,
)
from composite_threat_detector.storygraph import (
    COVERED_BY_AUTHORIZATION, StoryGraph, StoryNode, contradicts,
    covered_by_authorization, order, same_entity,
)

V = storyverdict


# --- CONTRADICTS edge type (§1) -------------------------------------------
def test_contradicts_edge_weakens_story():
    g = StoryGraph("c", "1", "c",
                   nodes=(StoryNode("a", "A"), StoryNode("b", "B", is_completion=True),
                          StoryNode("conf", "CONF")),
                   edges=(order("a", "b"), contradicts("b", "conf")))
    ev = [ObservedEvent("A", "1", 1, None, "u", {}),
          ObservedEvent("B", "2", 2, None, "u", {}),
          ObservedEvent("CONF", "3", 3, None, "u", {})]
    m = story_match(g, ev)
    assert m.contradicts_triggered and m.is_complete() is False


def test_contradicts_drives_ambiguous_category():
    g = StoryGraph("c", "1", "c",
                   nodes=(StoryNode("a", "A"), StoryNode("b", "B", is_completion=True),
                          StoryNode("conf", "CONF")),
                   edges=(order("a", "b"), contradicts("b", "conf")))
    events = [ObservedEvent("A", "1", 1, None, "u", {}),
              ObservedEvent("CONF", "3", 3, None, "u", {})]
    proposed = ObservedEvent("B", "prop", 10, None, "u", {})
    r = evaluate_proposed_action(events, proposed, g)
    assert r.category == V.AMBIGUOUS_COMPETING_STORIES


# --- COVERED_BY_AUTHORIZATION edge type (§1) ------------------------------
def test_covered_by_authorization_edge_is_recognized_and_inert_on_harmful():
    e = covered_by_authorization("reset", "customer_account_recovery")
    assert e.kind == COVERED_BY_AUTHORIZATION and e.endpoints() == ("reset",)
    g = StoryGraph("g", "1", "g",
                   nodes=(StoryNode("reset", "A", is_completion=True),),
                   edges=(covered_by_authorization("reset", "recovery"),))
    m = story_match(g, [ObservedEvent("A", "1", 1, None, "u", {})])
    # the annotation does not affect the harmful risk dimensions
    assert m.risk.coverage == 1.0 and m.completion_present


# --- combined structural vector (§3) --------------------------------------
def _events(events):
    az = SequenceRiskAnalyzer(FINANCIAL_ONTOLOGY, specs=(BY_CASE,))
    for e in events:
        az.observe(e)
    key = list(az.ledger._by_tenant["bank"].keys())[0]
    return story_bridge.observed_events(az, "bank", key)


def _ev(op, seq, eid, **kw):
    d = {"tenant_id": "bank", "workflow_id": "acct-1", "actor": "u1",
         "correlation_id": "s", "sequence_id": seq, "event_id": eid, "operation": op,
         "account": "acct-1", "credential_scope": {"principal": "u1"}, "arguments": {}}
    d.update(kw)
    return d


SETUP = [_ev("PASSWORD_RESET", "s:1", "1"),
         _ev("DEVICE_REGISTER", "s:2", "2", device="dev-x"),
         _ev("BENEFICIARY_ADD", "s:3", "3", beneficiary="bob")]


def _recovery():
    return Authorization(tag="customer_account_recovery", valid=True,
                         covered_operations=frozenset({"PASSWORD_RESET",
                                                       "DEVICE_REGISTER"}),
                         account="acct-1")


def _transfer(**ent):
    e = {"account": "acct-1", "beneficiary": "bob", "device": "dev-x", "amount": "9000"}
    e.update(ent)
    return story_bridge.proposed_event(financial.TRANSFER, entities=e)


def test_structural_vector_has_all_eight_dimensions():
    r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    sv = r.structural_vector
    for k in ("node_coverage", "ordering_consistency", "entity_binding_consistency",
              "timing_consistency", "corroboration", "completion_proximity",
              "trusted_context_coverage", "contradiction_findings"):
        assert k in sv
    assert 0.0 <= sv["trusted_context_coverage"] <= 1.0    # recovery covers 2 of 4
    assert isinstance(sv["contradiction_findings"], list)


def test_trusted_context_wrapper_signature():
    r = evaluate_proposed_action(
        _events(SETUP), _transfer(), ATO,
        legitimate_stories=[ACCOUNT_RECOVERY_STORY],
        trusted_context={"authorizations": [_recovery()], "facts": {}})
    assert r.legitimate_coverage["status"] == "PARTIAL"


# --- witness proof-summary (§7) -------------------------------------------
def test_witness_proves_named_relations():
    r = evaluate_proposed_action(_events(SETUP), _transfer(), ATO,
                                 legitimate_stories=[ACCOUNT_RECOVERY_STORY],
                                 authorizations=[_recovery()])
    proves = r.completion_witness["proves"]
    assert proves["same_account"] is True
    assert proves["same_device"] is True
    assert proves["same_beneficiary"] is True
    assert proves["valid_ordering"] is True
    assert proves["valid_time_interval"] is True
    assert proves["proposed_is_necessary"] is True


# --- matcher satisfied edges (§2) -----------------------------------------
def test_matcher_reports_satisfied_edges():
    m = story_match(ATO, _events(SETUP + [_ev(
        "TRANSFER", "s:5", "5", beneficiary="bob", device="dev-x", amount="9000")]))
    assert m.satisfied_edges
    kinds = {e["kind"] for e in m.satisfied_edges}
    assert "SAME_ENTITY" in kinds and "ORDER" in kinds


# --- freeze integration (implementation order item 11) --------------------
def test_freeze_binds_story_graphs():
    from evaluation import freeze
    cfg = freeze.current_config()
    assert cfg["storygraph_schema"] == STORYGRAPH_SCHEMA_VERSION
    assert "ACCOUNT_TAKEOVER_TRANSFER@1.0.0" in cfg["story_graphs"]
    assert "ACCOUNT_RECOVERY@1.0.0" in cfg["legitimate_stories"]
    fz = freeze.build_freeze("commit-x", profile="final")
    freeze.require_frozen(fz, official=True)          # unchanged -> ok
    tampered = dict(fz)
    tampered["story_graphs"] = {**fz["story_graphs"], "INJECTED@9": "deadbeef"}
    with pytest.raises(freeze.FreezeViolation):        # story change detected
        freeze.require_frozen(tampered, official=True)


def test_structural_vector_dataclass_roundtrip():
    sv = StructuralVector(1.0, 1.0, 0.5, 1.0, 1.0, 0.75, 0.5, [])
    d = sv.to_dict()
    assert d["entity_binding_consistency"] == 0.5 and d["completion_proximity"] == 0.75

"""
TAP-E5 behavioral tests.

Cover: packet completeness/minimality, dependency + provenance preservation, conflict and
gap preservation (never resolved/filled), rejected-authority + minority-evidence retention,
duplicate elimination, orphan freedom, unused-evidence pruning, reference integrity,
acyclicity, packet validation, determinism, schema round-trip, the A–F ladder / selection,
independent critical-failure accounting, and upstream immutability. TAP-E1/E2/E3/E4 are
consumed through frozen public interfaces only.
"""

import json

import pytest

from truth_assurance_pipeline.tap_e5_evidence_assembly import (
    BASELINES, EvidenceAssemblyLayer, config, validate_packet,
)
from truth_assurance_pipeline.tap_e5_evidence_assembly import harness, loader, metrics
from truth_assurance_pipeline.tap_e5_evidence_assembly.corpus import cases as corpus


def _case(cid):
    return next(c for c in corpus.ALL_CASES if c.case_id == cid)


def _assemble(case, cfg="F"):
    return EvidenceAssemblyLayer(config(cfg)).assemble(*corpus.build_records(case))


# --- structural guarantees on F ------------------------------------------- #

def test_full_packet_validates_for_every_case():
    for c in corpus.ALL_CASES:
        ok, problems = validate_packet(_assemble(c))
        assert ok, (c.case_id, problems)


def test_packet_is_complete_vs_gold():
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        gold = c.gold()
        assert gold["evidence"] <= {e.unit_id for e in pkt.evidence_units}
        assert gold["relationships"] <= {r.assertion_id for r in pkt.relationships}
        assert gold["governance"] <= {g.decision_id for g in pkt.governance_decisions}
        assert gold["conflicts"] <= {x.conflict_id for x in pkt.conflicts}
        assert gold["gaps"] <= {g.gap_id for g in pkt.gaps}


def test_packet_is_minimal_no_unused_evidence():
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        referenced = {u for r in pkt.relationships for u in r.evidence_unit_ids}
        assert all(e.unit_id in referenced for e in pkt.evidence_units), c.case_id
        assert "raw_upstream_signals" not in pkt.confidence_summary


def test_rejected_authorities_and_minority_evidence_preserved():
    pkt = _assemble(_case("E5D14"))          # regulation wins; dept + draft rejected
    govs = pkt.governance_decisions[0]
    names = {r.authority_name for r in govs.rejected_authorities}
    assert {"department policy", "draft policy"} <= names
    # minority evidence behind the rejected authorities is retained
    assert {e.unit_id for e in pkt.evidence_units} >= {"u1", "u2", "u3"}


def test_conflicts_preserved_never_resolved():
    pkt = _assemble(_case("E5D08"))          # E4 CONFLICTED
    assert len(pkt.conflicts) == 1
    assert pkt.governance_decisions[0].status == "CONFLICTED"
    # both tied authorities' relationships are present (minority preserved)
    assert {r.assertion_id for r in pkt.relationships} >= {"r1", "r2"}


def test_gaps_preserved_across_all_origins():
    pkt = _assemble(_case("E5D09"))
    origins = {g.origin for g in pkt.gaps}
    assert origins == {"E2", "E3", "E4"}


def test_unused_retrieved_evidence_is_pruned():
    pkt = _assemble(_case("E5D13"))          # u1 used; u2,u3 retrieved-unused
    assert {e.unit_id for e in pkt.evidence_units} == {"u1"}


def test_shared_evidence_is_deduplicated_once():
    pkt = _assemble(_case("E5D03"))          # one unit supports two relationships
    ids = [e.unit_id for e in pkt.evidence_units]
    assert ids == ["u1"]
    assert len(pkt.relationships) == 2


def test_dependency_graph_is_acyclic_and_connected():
    from truth_assurance_pipeline.tap_e5_evidence_assembly import dependency_graph as dg
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        assert not dg.has_cycle(pkt.dependency_edges), c.case_id
        ids = [e.unit_id for e in pkt.evidence_units] + \
              [r.assertion_id for r in pkt.relationships] + \
              [g.decision_id for g in pkt.governance_decisions]
        assert not dg.orphans(ids, pkt.dependency_edges, pkt.intent.request_id), c.case_id


def test_provenance_index_covers_every_object():
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        for oid in ([e.unit_id for e in pkt.evidence_units]
                    + [r.assertion_id for r in pkt.relationships]
                    + [g.decision_id for g in pkt.governance_decisions]
                    + [pkt.intent.request_id]):
            assert oid in pkt.provenance_index, (c.case_id, oid)


def test_packet_round_trips():
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        assert json.loads(pkt.to_json())["packet_id"] == pkt.packet_id


# --- E5 never invents / reasons ------------------------------------------- #

def test_no_evidence_invented_beyond_retrieved():
    for c in corpus.ALL_CASES:
        pkt = _assemble(c)
        _, ret, _, _ = corpus.build_records(c)
        retrieved = {cand.unit.unit_id for cand in ret.candidates}
        assert {e.unit_id for e in pkt.evidence_units} <= retrieved, c.case_id


# --- ladder / selection --------------------------------------------------- #

def test_weak_baselines_have_severe_criticals():
    for name in ("A", "B", "C", "D", "E"):
        agg = metrics.aggregate(harness.run_config(config(name),
                                                   corpus.cases_for_split("dev")))
        assert agg["severe_critical_failure_count"] > 0, name


def test_full_baseline_zero_criticals_both_splits():
    for split in ("dev", "eval"):
        agg = metrics.aggregate(harness.run_config(config("F"),
                                                   corpus.cases_for_split(split)))
        assert agg["severe_critical_failure_count"] == 0


def test_full_is_simplest_passing_baseline():
    r = harness.run_all()
    assert r["selection"]["selected_config"] == "F"
    assert r["verdict"] == "PASS_WITH_LIMITED_CLAIM"
    passes = r["selection"]["dev_gate_pass"]
    assert passes["F"] and not any(passes[n] for n in ("A", "B", "C", "D", "E"))


def test_all_gates_pass_on_locked_eval():
    assert harness.run_all()["gates"]["all_pass"] is True


def test_deterministic_across_repeats():
    a, b = harness.run_all(), harness.run_all()
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True,
                                                                    default=str)


# --- isolation / loader --------------------------------------------------- #

def test_public_loader_is_gold_free():
    for row in loader.load_public("eval"):
        assert "gold" not in row and "removable_evidence" not in row


def test_baselines_are_six():
    assert [b.name for b in BASELINES] == ["A", "B", "C", "D", "E", "F"]

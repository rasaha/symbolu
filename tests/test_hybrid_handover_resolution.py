#!/usr/bin/env python3
"""Tests for the relationship-resolution evaluation layer.

Analysis/infrastructure only — SEEB, validators, metrics, routing, baselines and
the handover protocol are unmodified. These tests lock the discrimination between
deterministic resolvers and the single-stage failure attribution.
"""

from __future__ import annotations

import json

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution import (
    ALL_RESOLVERS, EDGE_TYPES, GOLD, NODE_TYPES, RESOLVER_ORDER,
)
from agentic.hybrid_handover.resolution.graph import ResolutionResult
from agentic.hybrid_handover.resolution.harness import evaluate_resolver, run_all


def _mk(name):
    return ALL_RESOLVERS[name]()


def test_resolvers_conform_and_produce_typed_graphs():
    case = all_cases()[0]
    from agentic.hybrid_handover.resolution.modes import mode_oracle
    ev = mode_oracle(case)
    for name in RESOLVER_ORDER:
        res = _mk(name).resolve(case.question, ev)
        assert isinstance(res, ResolutionResult)
        for n in res.graph.nodes:
            assert n.type in NODE_TYPES
        for e in res.graph.edges:
            assert e.type in EDGE_TYPES


def test_gold_nodes_exist_in_seeb_corpora():
    cases = {c.case_id: c for c in all_cases()}
    for cid, gold in GOLD.items():
        cites = {d.citation for d in cases[cid].corpus.documents}
        for cite in gold.nodes:
            assert cite in cites, f"{cid}: gold node {cite!r} not a corpus citation"
        node_keys = set(gold.nodes)
        for src, _t, dst in gold.edges:
            assert src in node_keys, f"{cid}: edge src {src!r} not a gold node"
            # dst may be a dangling reference (not a node) by design
            assert dst in node_keys or any(ch.isdigit() for ch in dst)


def test_resolvers_are_discriminated():
    # the whole point: better resolvers score strictly higher, deterministically
    n = {r: evaluate_resolver(_mk(r), "A_oracle")["n_correct"] for r in RESOLVER_ORDER}
    assert n["frozen"] < n["rule"] < n["graph_traversal"]
    assert n["frozen"] == 6 and n["rule"] == 9 and n["graph_traversal"] == 13


def test_component_metric_signatures():
    out = run_all()
    fr = out["resolvers"]["frozen"]["A_oracle"]["metrics"]
    gt = out["resolvers"]["graph_traversal"]["A_oracle"]["metrics"]
    # frozen recovers almost no typed edges; rule/graph recover most
    assert fr["relationship_edge_recall"] < 0.1
    assert gt["relationship_edge_recall"] > 0.9
    # capabilities only graph_traversal has
    assert gt["cycle_detection_accuracy"] == 1.0
    assert gt["version_selection_accuracy"] == 1.0
    assert gt["abstention_accuracy"] == 1.0
    assert fr["negation_interpretation_accuracy"] == 0.0
    assert gt["negation_interpretation_accuracy"] == 1.0


def test_graph_traversal_residual_is_packet_and_extraction_only():
    # graph_traversal's remaining failures are cleanly attributed — NOT to
    # relationship or governance (those it solves)
    fa = evaluate_resolver(_mk("graph_traversal"), "A_oracle")["failure_attribution"]
    assert "relationship" not in fa
    assert "governance" not in fa
    assert fa.get("packet_construction", 0) == 2
    assert fa.get("extraction", 0) == 1


def test_evidence_mode_invariance():
    # on SEEB v1's short corpora retrieval is saturated: mode A == mode B outcomes
    for r in RESOLVER_ORDER:
        a = evaluate_resolver(_mk(r), "A_oracle")["n_correct"]
        b = evaluate_resolver(_mk(r), "B_bm25")["n_correct"]
        assert a == b


def test_resolution_is_deterministic():
    a = json.dumps(run_all(), sort_keys=True, default=str)
    b = json.dumps(run_all(), sort_keys=True, default=str)
    assert a == b

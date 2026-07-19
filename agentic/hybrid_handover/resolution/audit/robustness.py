#!/usr/bin/env python3
"""
Benchmark robustness — feed the reference governance deliberately awkward graph
structures (not present in the 16 gold cases) and record whether it behaves
sensibly. This probes the governance/scoring for structures a future resolver
might legitimately produce.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import Edge, Node, ResolvedEvidenceGraph
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

_G = GraphTraversalResolver()


def _clause(k, order=0):
    return Node(key=k, type="Clause", attrs={"order": order})


def _graph(nodes, edges):
    return ResolvedEvidenceGraph(nodes=nodes, edges=[Edge(src=s, type=t, dst=d) for s, t, d in edges])


def _gov(nodes, edges):
    g = _G.resolve_governance("", _graph(nodes, edges))
    return {"abstain": g.abstain, "governing": sorted(g.governing), "discarded": sorted(g.discarded)}


def run_robustness():
    A, B, C, D = _clause("A", 0), _clause("B", 1), _clause("C", 2), _clause("D", 3)
    P1 = Node(key="P1", type="Policy"); P2 = Node(key="P2", type="Policy")
    cases = {}

    # redundant duplicate edge
    cases["redundant_edges"] = _gov([A, B], [("A", "supersedes", "B"), ("A", "supersedes", "B")])
    # irrelevant extra node D (unconnected)
    cases["irrelevant_node"] = _gov([A, B, D], [("A", "supersedes", "B")])
    # multiple valid paths to discard C
    cases["multiple_paths"] = _gov([A, B, C], [("A", "supersedes", "C"), ("B", "supersedes", "C")])
    # parallel overrides of the same clause
    cases["parallel_overrides"] = _gov([A, P1, P2], [("P1", "overrides", "A"), ("P2", "overrides", "A")])
    # nested exceptions (exception to an exception)
    E1 = Node(key="E1", type="Exception"); E2 = Node(key="E2", type="Exception")
    cases["nested_exceptions"] = _gov([A, E1, E2], [("E1", "exception_to", "A"), ("E2", "exception_to", "E1")])
    # multi-hop governance chain A>B>C
    cases["multi_hop_chain"] = _gov([A, B, C], [("A", "supersedes", "B"), ("B", "supersedes", "C")])
    # dangling reference
    cases["dangling_reference"] = _gov([A], [("A", "references", "GhostDoc 1")])

    # annotate each with a plain-English expectation / observation
    notes = {
        "redundant_edges": "duplicate edge should be idempotent (B discarded once, A governs)",
        "irrelevant_node": "D is unrelated; governance has NO relevance filter -> D pollutes the governing set",
        "multiple_paths": "C discarded via either path; A,B both govern",
        "parallel_overrides": "A discarded by both; P1,P2 both govern -> ambiguous, no tie-break",
        "nested_exceptions": "nesting (E2->E1) is not modelled; only top-level exception recognised",
        "multi_hop_chain": "B and C both discarded (each is a supersede dst); A governs (works WITHOUT transitive reasoning)",
        "dangling_reference": "abstains on the dangling reference",
    }
    return {k: {"result": cases[k], "expectation": notes[k]} for k in cases}

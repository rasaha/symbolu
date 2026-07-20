#!/usr/bin/env python3
"""
Ground-truth (gold graph) structural audit + governance-necessity analysis.

Structural checks per gold case: no duplicate/self edges, valid edge types, src
is a node, dst is a node or an intentional dangling reference.

Necessity: build the gold graph and run the reference GraphTraversal governance;
remove each edge and re-check. An edge whose removal does not change the
governance decision is "not necessary for governance" — it may still be
justificatory (documents the reasoning) or packet-relevant (supplies a value).
This separates governance-necessary edges from justificatory/packet edges.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import Edge, Node, ResolvedEvidenceGraph
from agentic.hybrid_handover.resolution.gold import GOLD
from agentic.hybrid_handover.resolution.graph import EDGE_TYPES
from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

_G = GraphTraversalResolver()


def _gold_graph(gold, drop=None) -> ResolvedEvidenceGraph:
    nodes = [Node(key=k, type=t) for k, t in gold.nodes.items()]
    edges = [Edge(src=s, type=t, dst=d) for (s, t, d) in gold.edges if (s, t, d) != drop]
    return ResolvedEvidenceGraph(nodes=nodes, edges=edges)


def _gov_key(gov):
    return (gov.abstain, tuple(sorted(gov.governing)))


def structural_checks():
    issues = []
    for cid, gold in GOLD.items():
        seen = set()
        node_keys = set(gold.nodes)
        for (s, t, d) in gold.edges:
            if (s, t, d) in seen:
                issues.append((cid, "duplicate_edge", f"{s} -{t}-> {d}"))
            seen.add((s, t, d))
            if s == d:
                issues.append((cid, "self_loop", f"{s}"))
            if t not in EDGE_TYPES:
                issues.append((cid, "bad_edge_type", t))
            if s not in node_keys:
                issues.append((cid, "src_not_node", s))
            if d not in node_keys:
                # tolerated only as an intentional dangling reference
                if not ("reference" in gold.capabilities or "coverage" in gold.capabilities):
                    issues.append((cid, "dst_not_node", d))
    return issues


def necessity():
    rows = []
    for cid, gold in GOLD.items():
        if not gold.edges:
            continue
        base = _gov_key(_G.resolve_governance("", _gold_graph(gold)))
        for e in gold.edges:
            after = _gov_key(_G.resolve_governance("", _gold_graph(gold, drop=e)))
            rows.append({
                "case_id": cid, "edge": f"{e[0]} -{e[1]}-> {e[2]}",
                "governance_necessary": after != base,
            })
    return rows


def run_groundtruth():
    return {"structural_issues": structural_checks(), "necessity": necessity()}

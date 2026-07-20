#!/usr/bin/env python3
"""
Edge Prioritization Layer — deterministic. Given multiple VALID relationship
proposals, it decides which governance-bearing relationships should DOMINATE, and
realizes that decision by ordering the nodes of the graph handed to the FROZEN
governance in the full pipeline. It never adds, removes, or retypes an edge, and it
never runs in Mode G / Mode P — so discovery, governance Mode G, and packet Mode P
are structurally unchanged. Only the full-pipeline governance decision (hence
selective accuracy / coverage / unsafe) can move.

Priority is a decomposable VECTOR, never a single opaque scalar. Competing governance
sources are ranked lexicographically over the enabled components (fixed order), so
each winner is explainable ("beat the competitor on <component>").
"""

from __future__ import annotations

import re

# governance-source relationship types: their SOURCE node can become packet `primary`
GOVERNANCE_SOURCE_TYPES = ("supersedes", "overrides", "governs_over")
_YEAR = re.compile(r"(19|20)\d{2}")

# priority component order (lexicographic; a later component only breaks ties)
COMPONENT_ORDER = ("authority", "temporal", "specificity", "reference", "structural",
                   "confidence", "support")


class PriorityConfig:
    """Ablation switches. P4 (full) enables every component."""
    def __init__(self, authority=True, temporal=True, specificity=True,
                 reference=True, structural=True, confidence=True, support=True):
        self.enabled = {
            "authority": authority, "temporal": temporal, "specificity": specificity,
            "reference": reference, "structural": structural,
            "confidence": confidence, "support": support,
        }


def _year(node):
    m = _YEAR.search(node.key + " " + (node.text or ""))
    return int(m.group(0)) if m else 0


def priority_vector(node, graph, conf):
    """Decomposable priority vector for a governance-source node. Each component in
    [0,1]; higher = should dominate. Pure function of parsed structure + confidence."""
    out_edges = [e for e in graph.edges if e.src == node.key]
    gov_out = [e for e in out_edges if e.type in GOVERNANCE_SOURCE_TYPES]
    in_edges = [e for e in graph.edges if e.dst == node.key]
    orders = [n.attrs.get("order", 0) for n in graph.nodes]
    max_order = max(orders) if orders else 0
    years = [_year(n) for n in graph.nodes]
    max_year, min_year = (max(years), min(y for y in years if y) if any(years) else 0) \
        if any(years) else (0, 0)

    # authority — later instrument (higher parsed order) is more authoritative
    authority = (node.attrs.get("order", 0) / max_order) if max_order else 0.0
    # temporal — more recent effective year dominates
    y = _year(node)
    temporal = ((y - min_year) / (max_year - min_year)) if (max_year > min_year and y) else \
        (1.0 if y and y == max_year else 0.0)
    # specificity — a named-section governance target is more specific than a default
    specificity = 1.0 if node.attrs.get("supersede_target") else \
        (0.75 if any(e.type == "governs_over" for e in gov_out) else 0.5)
    # reference — inverse reference distance: a directly-governing node scores high,
    # one reached only through references scores lower
    ref_in = sum(1 for e in in_edges if e.type == "references")
    reference = 1.0 / (1.0 + ref_in)
    # structural — out-degree centrality among governance edges
    structural = min(1.0, len(gov_out) / 3.0)
    # confidence — strongest supporting lexical confidence on this node's gov edges
    confidence = max((conf.get(e.triple(), 0.0) for e in gov_out), default=0.0)
    # support — corroborating edges sourced at this node
    support = min(1.0, len(out_edges) / 4.0)

    return {"authority": round(authority, 4), "temporal": round(temporal, 4),
            "specificity": round(specificity, 4), "reference": round(reference, 4),
            "structural": round(structural, 4), "confidence": round(confidence, 4),
            "support": round(support, 4)}


def _key(vec, config: PriorityConfig):
    return tuple(vec[c] if config.enabled[c] else 0.0 for c in COMPONENT_ORDER)


def prioritize(graph, conf, config: PriorityConfig):
    """
    Reorder graph.nodes so competing governance sources appear in descending priority
    (dominant first). Returns (reordered_graph, competition_records). Edges are
    unchanged; when fewer than two governance sources compete, the order (and thus the
    frozen governance/packet outcome) is unchanged.
    """
    from agentic.hybrid_handover.resolution.graph import ResolvedEvidenceGraph

    src_keys = {e.src for e in graph.edges if e.type in GOVERNANCE_SOURCE_TYPES}
    sources = [n for n in graph.nodes if n.key in src_keys]
    records = []

    if config is None or len(sources) < 2:
        # no competition to resolve → identical to v0.2
        return graph, records

    vecs = {n.key: priority_vector(n, graph, conf) for n in sources}
    ranked = sorted(sources, key=lambda n: _key(vecs[n.key], config), reverse=True)
    winner = ranked[0]
    for loser in ranked[1:]:
        wk, lk = _key(vecs[winner.key], config), _key(vecs[loser.key], config)
        decisive = next((c for c in COMPONENT_ORDER
                         if config.enabled[c] and vecs[winner.key][c] != vecs[loser.key][c]), None)
        records.append({
            "winner": winner.key, "competing_edge": loser.key,
            "retained": winner.key, "rejected_primary": loser.key,
            "decisive_component": decisive,
            "winner_vector": vecs[winner.key], "loser_vector": vecs[loser.key],
            "reason": (f"'{winner.key}' outranks '{loser.key}' on {decisive}"
                       if decisive else f"'{winner.key}' ties '{loser.key}'; stable order kept"),
        })

    # reorder: ranked governance sources first (dominant → primary), then the rest in
    # their original relative order
    ranked_keys = [n.key for n in ranked]
    rest = [n for n in graph.nodes if n.key not in ranked_keys]
    new_nodes = ranked + rest
    return ResolvedEvidenceGraph(nodes=new_nodes, edges=list(graph.edges)), records


# preregistered ablations
ABLATIONS = {
    "P0_none": None,
    "P1_authority": PriorityConfig(authority=True, temporal=False, specificity=False,
                                   reference=False, structural=False, confidence=False, support=False),
    "P2_authority_temporal": PriorityConfig(authority=True, temporal=True, specificity=False,
                                            reference=False, structural=False, confidence=False, support=False),
    "P3_auth_temporal_specificity": PriorityConfig(authority=True, temporal=True, specificity=True,
                                                   reference=False, structural=False, confidence=False, support=False),
    "P4_full": PriorityConfig(),
}

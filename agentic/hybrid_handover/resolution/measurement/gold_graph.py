#!/usr/bin/env python3
"""
Build a perfect ("gold") relationship graph for a case, with REAL node attributes
parsed from the evidence but AUTHORITATIVE gold nodes/types/edges. Used by the
governance-isolation (Mode G) and packet-isolation (Mode P) evaluations so that
discovery and classification are held perfect and only the stage under test
varies.

This is measurement-side construction — it does not modify any resolver. It sets
`dangling`/`unusable` attributes structurally so the existing governance logic is
exercised faithfully on gold input.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import Edge, Node, ResolvedEvidenceGraph
from agentic.hybrid_handover.resolution.modes import mode_oracle
from agentic.hybrid_handover.resolution.parse import parse_nodes


def build_gold_graph(case, gold) -> ResolvedEvidenceGraph:
    parsed = {n.key: n for n in parse_nodes(mode_oracle(case))}
    node_keys = set(gold.nodes)
    nodes = []
    for cite, gtype in gold.nodes.items():
        p = parsed.get(cite)
        attrs = dict(p.attrs) if p else {}
        # coverage/unusable documents
        if gtype == "Document" and ("scanned" in (cite + (p.text if p else "")).lower()
                                    or "not ocr" in (p.text.lower() if p else "")):
            attrs["unusable"] = True
        nodes.append(Node(key=cite, type=gtype, doc_id=(p.doc_id if p else ""),
                          text=(p.text if p else ""), section=(p.section if p else None),
                          attrs=attrs))
    edges = []
    for (s, t, d) in gold.edges:
        attrs = {}
        if d not in node_keys:            # structural dangling reference
            attrs["dangling"] = True
        edges.append(Edge(src=s, type=t, dst=d, attrs=attrs))
    return ResolvedEvidenceGraph(nodes=nodes, edges=edges)

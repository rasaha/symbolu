#!/usr/bin/env python3
"""
Deterministic difficulty rubric (Levels 1–5), scored by required OPERATIONS, not
prose complexity. Authors never assign the final difficulty; it is computed here
from adjudicated factors.
"""

from __future__ import annotations

FACTOR_KEYS = (
    "n_docs", "n_relationships", "hop_depth", "competing_authorities",
    "exception_nesting", "temporal", "cross_format", "ambiguity",
    "distractor_paths", "must_abstain",
)


def rubric_score(f: dict) -> int:
    s = 0
    s += max(0, f.get("n_relationships", 0) - 1)          # relationships beyond the first
    s += f.get("hop_depth", 0)                             # reasoning hops
    s += max(0, f.get("competing_authorities", 0) - 1)     # authorities beyond one
    s += f.get("exception_nesting", 0)                     # exception nesting depth
    s += 1 if f.get("temporal") else 0                     # temporal reasoning
    s += 1 if f.get("cross_format") else 0                 # table/prose cross-format
    s += 1 if f.get("ambiguity") else 0                    # ambiguity present
    s += f.get("distractor_paths", 0)                      # plausible distractor paths
    s += 1 if f.get("must_abstain") else 0                 # requirement to abstain
    return s


def rubric_level(f: dict) -> int:
    s = rubric_score(f)
    if s <= 0:
        return 1
    if s == 1:
        return 2
    if s <= 3:
        return 3
    if s <= 5:
        return 4
    return 5


def factors_from_graph(graph: dict, ambiguity: str, abstain: bool) -> dict:
    """Proxy factors derived from a gold graph — used for RETROSPECTIVE
    calibration of the seed cases (which recorded a difficulty label but not
    factors). Not used to relabel the seed."""
    nodes = graph.get("nodes", {})
    edges = graph.get("edges", [])
    etypes = [t for (_s, t, _d) in edges]
    # longest reference chain (hop depth)
    ref = {}
    for (s, t, d) in edges:
        if t == "references":
            ref.setdefault(s, []).append(d)

    def depth(u, seen):
        if u in seen:
            return 0
        seen = seen | {u}
        return 1 + max((depth(v, seen) for v in ref.get(u, [])), default=0) if ref.get(u) else 0
    hop = max((depth(u, set()) for u in ref), default=0)
    exc = etypes.count("exception_to")
    return {
        "n_docs": len(nodes),
        "n_relationships": len(edges),
        "hop_depth": hop,
        "competing_authorities": etypes.count("overrides") + etypes.count("governs_over"),
        "exception_nesting": max(0, exc - 1) if exc else 0,
        "temporal": "effective_after" in etypes,
        "cross_format": any(v == "Table" for v in nodes.values()),
        "ambiguity": ambiguity != "none",
        "distractor_paths": 0,
        "must_abstain": abstain,
    }

"""
Deterministic dependency-graph helpers for TAP-E5.

The packet dependency graph is a directed acyclic graph over intent / evidence /
relationship / governance nodes. Edges point from a dependent object to the object it
depends on:

    governance --answers_intent-->            intent
    governance --supported_by_relationship--> relationship
    relationship --supported_by_evidence-->   evidence

These helpers only *analyse* a set of edges (adjacency, reachability, orphans, cycles).
They neither create evidence nor decide inclusion — that is the assembler's job.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Set, Tuple

from truth_assurance_pipeline.tap_e5_evidence_assembly.schema import DependencyEdge


def adjacency(edges: Iterable[DependencyEdge]) -> Dict[str, List[str]]:
    adj: Dict[str, List[str]] = {}
    for e in edges:
        adj.setdefault(e.src_id, []).append(e.dst_id)
    for k in adj:
        adj[k].sort()
    return adj


def reachable(roots: Iterable[str], edges: Iterable[DependencyEdge]) -> Set[str]:
    adj = adjacency(edges)
    seen: Set[str] = set()
    stack = sorted(roots)
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(sorted(adj.get(n, [])))
    return seen


def orphans(object_ids: Iterable[str], edges: Iterable[DependencyEdge],
            intent_id: str) -> Tuple[str, ...]:
    """Object ids that touch no edge (no in- or out-edge). The intent node is a legitimate
    sink and is never an orphan."""
    touched: Set[str] = set()
    for e in edges:
        touched.add(e.src_id)
        touched.add(e.dst_id)
    return tuple(sorted(o for o in set(object_ids) if o != intent_id and o not in touched))


def has_cycle(edges: Iterable[DependencyEdge]) -> bool:
    adj = adjacency(edges)
    color: Dict[str, int] = {}          # 0 = visiting, 1 = done

    def visit(n: str) -> bool:
        color[n] = 0
        for m in adj.get(n, []):
            c = color.get(m)
            if c == 0:
                return True
            if c is None and visit(m):
                return True
        color[n] = 1
        return False

    return any(color.get(n) is None and visit(n) for n in sorted(adj))


def dangling_edges(edges: Iterable[DependencyEdge],
                   known_ids: Iterable[str]) -> Tuple[DependencyEdge, ...]:
    known = set(known_ids)
    return tuple(e for e in edges if e.src_id not in known or e.dst_id not in known)

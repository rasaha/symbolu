#!/usr/bin/env python3
"""
Synthetic conflict fixtures for calibration gates C8/C9 and the conflict-category unit
checks. These graphs are hand-built to exercise each conflict category deterministically.
They are NOT derived from any hidden-case text or annotation — they use invented,
neutral instrument names and the standard termination-for-convenience matter.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import Edge, Node, ResolvedEvidenceGraph

from . import competing_operative as CO


def _clause(key, allows=None, negation=None, policy=False, order=0, text="", ntype="Clause"):
    attrs = {"order": order, "terminates": True}
    if allows is not None:
        attrs["allows"] = allows
    if negation is not None:
        attrs["negation"] = negation
    if policy:
        attrs["policy_override"] = True
    return Node(key=key, type=ntype, text=text, attrs=attrs)


def _graph(nodes, edges):
    return ResolvedEvidenceGraph(nodes=nodes, edges=[Edge(src=s, type=t, dst=d) for (s, t, d) in edges])


def fixtures():
    """Return {name: (graph, governing_keys, expected_category, expect_abstain)}."""
    out = {}

    # 1. co-occurrence, different authority domains → NOT a conflict (co-occurrence safety, C8)
    g = _graph([_clause("Corporate Policy P-1", negation=True, order=1, text="corporate policy prohibits"),
                _clause("Order Form O-1", allows=True, order=0, text="order form permits")], [])
    out["scoped_non_conflict_diff_domain"] = (g, ["Corporate Policy P-1", "Order Form O-1"],
                                              CO.DIFFERENT_AUTHORITY_DOMAIN, False)

    # 2. temporal non-overlap (dated supersession) → resolved, not conflict
    g = _graph([_clause("MSA §1 (2019)", negation=True, order=0, text="msa 2019 prohibits"),
                _clause("Amendment A-2 (2023)", allows=True, order=1, text="amendment 2023 permits")],
               [("Amendment A-2 (2023)", "supersedes", "MSA §1 (2019)")])
    out["temporal_supersession"] = (g, ["MSA §1 (2019)", "Amendment A-2 (2023)"],
                                    CO.RESOLVED_BY_SUPERSESSION, False)

    # 3. exception → resolved by exception
    g = _graph([_clause("MSA §2", negation=True, order=0, text="msa prohibits"),
                _clause("Exception E-1", allows=True, order=1, text="except where", ntype="Exception")],
               [("Exception E-1", "exception_to", "MSA §2")])
    out["conditional_exception"] = (g, ["MSA §2", "Exception E-1"], CO.RESOLVED_BY_EXCEPTION, False)

    # 4. override → resolved by override
    g = _graph([_clause("MSA §3", allows=True, order=0, text="msa permits"),
                _clause("MSA §4", negation=True, policy=True, order=1, text="notwithstanding, prohibited")],
               [("MSA §4", "overrides", "MSA §3")])
    out["scoped_override"] = (g, ["MSA §3", "MSA §4"], CO.RESOLVED_BY_OVERRIDE, False)

    # 5. compatible (same polarity) → compatible, not conflict
    g = _graph([_clause("MSA §5", negation=True, order=0, text="prohibited"),
                _clause("MSA §6", negation=True, order=1, text="also prohibited")], [])
    out["compatible_operatives"] = (g, ["MSA §5", "MSA §6"], CO.COMPATIBLE_OPERATIVES, False)

    # 6. GENUINE UNRESOLVED CONFLICT — same domain, incompatible, undated, no resolving edge (C9)
    g = _graph([_clause("MSA §7", negation=True, order=0, text="the agreement prohibits termination"),
                _clause("MSA §8", allows=True, order=0, text="the agreement permits termination")], [])
    out["genuine_unresolved_conflict"] = (g, ["MSA §7", "MSA §8"],
                                          CO.GENUINE_UNRESOLVED_CONFLICT, True)

    return out


def check():
    """Return a list of failed fixture names (empty == all pass)."""
    failures = []
    for name, (graph, gov, expected_cat, expect_abstain) in fixtures().items():
        operative = gov[0]
        opset = CO.resolve(graph, gov, operative, {}, CO.ABLATIONS["C4_full"])
        cats = [c["category"] for c in opset.competitions]
        if expected_cat not in cats:
            failures.append(f"{name}: expected {expected_cat}, got {cats}")
        if opset.operative_abstention != expect_abstain:
            failures.append(f"{name}: abstain expected {expect_abstain}, got {opset.operative_abstention}")
    return failures


if __name__ == "__main__":
    f = check()
    print("fixture failures:", f or "none")

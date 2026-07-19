#!/usr/bin/env python3
"""
Single-stage failure attribution. When a case's end-to-end outcome is wrong, the
failure is attributed to exactly ONE stage, in pipeline order (no double
counting):

  Extraction failure  → a gold-required node's span is absent from the evidence
  Relationship failure → evidence present, but a gold edge is missing/wrong
  Governance failure  → edges correct, but governing/abstain decision wrong
  Packet construction failure → governance correct, but derived answer wrong
  Safety gate failure → (reserved for pipeline-gate interactions)
  Unknown             → none of the above explains it
"""

from __future__ import annotations

from .gold import GOLD

STAGES = ["extraction", "relationship", "governance", "packet_construction", "safety_gate", "unknown"]


def _answer_correct(result, expected, gold) -> bool:
    if gold.abstain:
        return result.governance.abstain
    if result.governance.abstain:
        return False
    return (result.tfc, result.notice_days, result.penalty) == (
        expected.termination_for_convenience, expected.notice_days, expected.penalty
    )


def attribute(case_id, evidence, result, expected) -> str:
    """Return the single stage responsible, or 'none' if the case is correct."""
    gold = GOLD[case_id]
    if _answer_correct(result, expected, gold):
        return "none"

    # 0. pure-coverage cases (e.g. OCR corruption) are an upstream Extraction /
    #    coverage matter handled by SEEB's safety gate, not the resolver.
    if gold.abstain and "coverage" in gold.capabilities and "reference" not in gold.capabilities:
        return "extraction"

    # 1. extraction: any gold node's citation absent from the evidence?
    present = {s.citation for s in evidence}
    gold_node_cites = set(gold.nodes.keys())
    if gold_node_cites and not gold_node_cites.issubset(present | {""}):
        # a required node was never retrieved (only counts if it is a real corpus node)
        missing = [c for c in gold_node_cites if c not in present]
        # dangling/phantom refs (e.g. "Appendix 1") are not extraction failures
        real_missing = [c for c in missing if "§" in c or "p." in c]
        if real_missing:
            return "extraction"

    # 2. relationship: a gold edge missing from the predicted graph?
    pred = result.graph.edge_triples()
    goldset = {tuple(e) for e in gold.edges}
    if goldset - pred:
        return "relationship"

    # 3. governance: edges ok but abstain/governing decision wrong?
    if result.governance.abstain != gold.abstain:
        return "governance"
    if not gold.abstain and set(result.governance.governing) != set(gold.governing):
        return "governance"

    # 4. packet construction: governance ok but derived answer still wrong
    return "packet_construction"

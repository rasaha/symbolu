#!/usr/bin/env python3
"""
Hidden-corpus integrity validation (structural; does NOT run any resolver).

Checks each case's authored ground truth is well-formed and internally
consistent. A clean validation is a precondition for trusting the corpus.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.graph import EDGE_TYPES, NODE_TYPES

from ._authored import AUTHORED
from .corpus import opaque_id

CAPABILITIES = [
    "multiple_authorities", "parallel_overrides", "nested_exceptions",
    "cross_document_reference", "conflicting_amendments", "effective_date_precedence",
    "version_supersession", "hierarchical_governance", "definition_inheritance",
    "implicit_references", "partial_overrides", "table_vs_text", "appendix_precedence",
    "circular_reference", "multi_hop", "conditional_applicability", "scoped_exceptions",
    "entity_renaming", "policy_migration", "transitive_authority",
    # negative-control capabilities
    "no_relationship", "multiple_valid_interpretations", "insufficient_evidence",
    "unresolvable_conflict",
]

VARIATIONS = [
    "wording", "sentence_structure", "doc_order", "clause_numbering", "entity_names",
    "date_format", "policy_naming", "section_reference", "voice", "explicit_implicit",
    "table_prose", "number_format", "doc_granularity",
]


def validate():
    issues = []
    for a in AUTHORED:
        cid = opaque_id(a)
        cites = {d["citation"] for d in a["documents"]}
        node_keys = set(a["gold_nodes"])

        for cite, ntype in a["gold_nodes"].items():
            if cite not in cites:
                issues.append((cid, "gold_node_not_in_docs", cite))
            if ntype not in NODE_TYPES:
                issues.append((cid, "bad_node_type", ntype))
        for (s, t, d) in a["gold_edges"]:
            if t not in EDGE_TYPES:
                issues.append((cid, "bad_edge_type", t))
            if s not in node_keys:
                issues.append((cid, "edge_src_not_node", s))
            if d not in node_keys:
                # tolerated only for intentional dangling references
                if "insufficient_evidence" not in a["capability"]:
                    issues.append((cid, "edge_dst_not_node", d))
        # abstain consistency
        if a["abstain"] != ("abstain" in a["expectation"]):
            issues.append((cid, "abstain_expectation_mismatch", str(a["expectation"])))
        if a["abstain"] and a["governing"]:
            issues.append((cid, "abstain_with_governing", str(a["governing"])))
        if not a["abstain"] and not a["governing"]:
            issues.append((cid, "no_governing_no_abstain", cid))
        # ranges / vocab
        if not (1 <= a["difficulty"] <= 5):
            issues.append((cid, "bad_difficulty", a["difficulty"]))
        if not (0.0 <= a["confidence"] <= 1.0):
            issues.append((cid, "bad_confidence", a["confidence"]))
        for c in a["capability"]:
            if c not in CAPABILITIES:
                issues.append((cid, "unknown_capability", c))
        for v in a["variation"]:
            if v not in VARIATIONS:
                issues.append((cid, "unknown_variation", v))
    return issues

#!/usr/bin/env python3
"""
Gold relationship ground truth for the SEEB v1.0.0 cases.

Authored HERE, in the resolution layer — SEEB is not modified. Each SEEB case is
annotated with the typed relationship graph, the governing evidence, whether the
correct outcome is abstention, and the capability tags it exercises. Resolvers
are scored against this gold.

Keys are source citations (Node.key). Edge = (src_citation, edge_type,
dst_citation). A dst that is not a corpus citation (e.g. "Appendix 1") is a
deliberately dangling reference.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GoldCase(BaseModel):
    nodes: dict[str, str] = Field(default_factory=dict)          # citation -> NodeType
    edges: list[tuple[str, str, str]] = Field(default_factory=list)  # (src, type, dst)
    governing: list[str] = Field(default_factory=list)          # citations that govern
    abstain: bool = False
    abstain_reason: str = ""
    capabilities: list[str] = Field(default_factory=list)       # metric buckets


GOLD: dict[str, GoldCase] = {
    "later_amendment_override": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "Amendment 4 §3 p.204": "Clause",
               "Amendment 6 §2 p.331": "Clause"},
        edges=[("Amendment 4 §3 p.204", "supersedes", "MSA §7.1 p.12"),
               ("Amendment 6 §2 p.331", "amends", "MSA §7.1 p.12")],
        governing=["Amendment 4 §3 p.204", "Amendment 6 §2 p.331"],
        capabilities=["precedence"],
    ),
    "buried_exception": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "Schedule D §4 p.88": "Exception"},
        edges=[("Schedule D §4 p.88", "exception_to", "MSA §7.1 p.12")],
        governing=["MSA §7.1 p.12"],
        capabilities=["exception"],
    ),
    "conflicting_definitions": GoldCase(
        nodes={"MSA §1 p.3": "Definition", "DPA §1 p.51": "Definition",
               "MSA §7.1 p.12": "Clause"},
        edges=[("DPA §1 p.51", "conflicts_with", "MSA §1 p.3")],
        governing=["MSA §7.1 p.12"],
        capabilities=["definition"],
    ),
    "order_of_precedence": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "Order Form §2 p.1": "Clause"},
        edges=[("Order Form §2 p.1", "governs_over", "MSA §7.1 p.12")],
        governing=["Order Form §2 p.1"],
        capabilities=["precedence", "override"],
    ),
    "conflicting_versions": GoldCase(
        nodes={"Amendment 3 (v1) p.150": "Version", "Amendment 3 (v2) p.150": "Version"},
        edges=[("Amendment 3 (v1) p.150", "same_as", "Amendment 3 (v2) p.150"),
               ("Amendment 3 (v1) p.150", "conflicts_with", "Amendment 3 (v2) p.150")],
        governing=[], abstain=True, abstain_reason="unresolvable version conflict",
        capabilities=["version", "conflict", "abstention"],
    ),
    "duplicate_amendment": GoldCase(
        nodes={"Amendment 4 p.204": "Clause", "Amendment 4 (dup) p.204": "Version"},
        edges=[("Amendment 4 p.204", "same_as", "Amendment 4 (dup) p.204")],
        governing=["Amendment 4 p.204"],
        capabilities=["version"],
    ),
    "ocr_corruption": GoldCase(
        nodes={"MSA §7.1 p.12 (scanned)": "Document"},
        edges=[], governing=[], abstain=True, abstain_reason="unusable OCR source",
        capabilities=["coverage"],
    ),
    "scanned_annex": GoldCase(
        nodes={"MSA §7 p.12": "Clause", "Annex A p.400": "Document"},
        edges=[("MSA §7 p.12", "references", "Annex A p.400")],
        governing=[], abstain=True, abstain_reason="referenced annex not machine-readable",
        capabilities=["coverage", "reference"],
    ),
    "hidden_negation": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause"},
        edges=[], governing=["MSA §7.1 p.12"],
        capabilities=["negation"],
    ),
    "conflicting_tables": GoldCase(
        nodes={"MSA §7.3 p.12": "Clause", "Fee Table Exhibit B p.60": "Table"},
        edges=[("MSA §7.3 p.12", "conflicts_with", "Fee Table Exhibit B p.60")],
        governing=["MSA §7.3 p.12"],
        capabilities=["conflict"],
    ),
    "cross_document_reference": GoldCase(
        nodes={"MSA §7.3 p.12": "Clause", "Schedule C p.70": "Clause"},
        edges=[("MSA §7.3 p.12", "references", "Schedule C p.70")],
        governing=["MSA §7.3 p.12", "Schedule C p.70"],
        capabilities=["reference", "cross_doc"],
    ),
    "circular_reference": GoldCase(
        nodes={"MSA §7 p.12": "Clause", "Schedule C p.70": "Clause"},
        edges=[("MSA §7 p.12", "references", "Schedule C p.70"),
               ("Schedule C p.70", "references", "MSA §7 p.12")],
        governing=[], abstain=True, abstain_reason="circular reference; no ground term",
        capabilities=["cycle", "reference", "abstention"],
    ),
    "missing_appendix": GoldCase(
        nodes={"MSA §7.3 p.12": "Clause"},
        edges=[("MSA §7.3 p.12", "references", "Appendix 1")],  # dangling dst
        governing=[], abstain=True, abstain_reason="referenced appendix absent",
        capabilities=["reference", "coverage", "abstention"],
    ),
    "irrelevant_distractors": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "NDA p.1": "Document", "Invoice 2043 p.1": "Document"},
        edges=[], governing=["MSA §7.1 p.12"],
        capabilities=["pure"],
    ),
    "inconsistent_numbering": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "Amendment 5 §7.01 p.250": "Clause"},
        edges=[("Amendment 5 §7.01 p.250", "same_as", "MSA §7.1 p.12"),
               ("Amendment 5 §7.01 p.250", "supersedes", "MSA §7.1 p.12")],
        governing=["Amendment 5 §7.01 p.250"],
        capabilities=["precedence", "alias"],
    ),
    "policy_override": GoldCase(
        nodes={"MSA §7.1 p.12": "Clause", "Corporate Policy GOV-12 p.2": "Policy"},
        edges=[("Corporate Policy GOV-12 p.2", "overrides", "MSA §7.1 p.12")],
        governing=["Corporate Policy GOV-12 p.2"],
        capabilities=["override"],
    ),
}

# capability -> cases that exercise it (for per-capability metrics)
CAPABILITIES = [
    "precedence", "override", "exception", "definition", "version", "conflict",
    "negation", "cycle", "reference", "cross_doc", "alias", "abstention", "coverage",
]

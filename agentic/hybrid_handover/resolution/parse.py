#!/usr/bin/env python3
"""
Deterministic cue parsing shared by the baseline resolvers. Pure string rules —
no ML. Converts evidence spans (grouped by citation) into typed nodes with
attributes, and exposes the textual cues the resolvers turn into typed edges.
"""

from __future__ import annotations

import re
from collections import OrderedDict

from agentic.hybrid_handover.schema import EvidenceSpan

from .graph import Node


def norm_section(s: str) -> str:
    parts = []
    for p in s.split("."):
        p = p.strip()
        if p.isdigit():
            parts.append(str(int(p)))  # 7.01 -> 7.1
        elif p:
            parts.append(p)
    return ".".join(parts)


def section_of(citation: str, text: str) -> str | None:
    m = re.search(r"§\s*([0-9.]+)", citation) or re.search(r"[Ss]ection\s+([0-9.]+)", text)
    return norm_section(m.group(1)) if m else None


def _int_in_parens_before(text: str, kw: str) -> int | None:
    m = re.search(r"\((\d+)\)\s*" + kw, text) or re.search(r"(\d+)\s*" + kw, text)
    return int(m.group(1)) if m else None


def notice_days(text: str) -> int | None:
    return _int_in_parens_before(text, "days")


def penalty_months(text: str) -> int | None:
    return _int_in_parens_before(text, "month")


def has_negation(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in (
        "in no event", "neither party may terminate", "shall not terminate",
        "no termination for convenience",
    ))


def allows_terminate(text: str) -> bool:
    low = text.lower()
    return "either party may terminate for convenience" in low or \
           "any party may terminate for convenience" in low


def references(text: str) -> list[str]:
    return re.findall(r"(Schedule [A-Z]|Appendix \d+|Annex [A-Z]|Exhibit [A-Z]|MSA §[0-9.]+)", text)


def supersede_target(text: str) -> str | None:
    low = text.lower()
    if any(c in low for c in ("deleted and replaced", "is amended", "supersede")):
        m = re.search(r"section\s+([0-9.]+)", low)
        return norm_section(m.group(1)) if m else None
    return None


def governs_over_target(text: str) -> str | None:
    m = re.search(r"(?:governs over|takes precedence over|prevails over)\s+the\s+(\w+)", text.lower())
    return m.group(1) if m else None


def is_policy_override(text: str) -> bool:
    low = text.lower()
    return "notwithstanding any contract" in low or "policy prohibits" in low


def is_exception(text: str) -> bool:
    low = text.lower()
    return ("except that" in low) or ("exception" in low)


def introduces_fee(text: str) -> bool:
    low = text.lower()
    return "termination fee" in low or ("fee" in low and "month" in low)


def definition_term(text: str) -> str | None:
    m = re.search(r"([A-Z][A-Za-z ]+?)\s+means\b", text)
    return m.group(1).strip() if m else None


def _node_type(citation: str, text: str) -> str:
    c, t = citation.lower(), text.lower()
    if "(scanned" in c or "[scanned" in t or "parser failure" in t or "not ocr" in t:
        return "Document"
    if is_policy_override(text) or "policy" in c:
        return "Policy"
    if "exhibit" in c or "fee schedule" in t or ("table" in t and "fee" in t):
        return "Table"
    if "(v1)" in c or "(v2)" in c or "(dup)" in c:
        return "Version"
    if definition_term(text):
        return "Definition"
    if is_exception(text) and not allows_terminate(text) and not has_negation(text):
        return "Exception"
    if "nda" in c or "invoice" in c:
        return "Document"
    if "annex" in c and ("scanned" in t or "not ocr" in t or not t.strip()):
        return "Document"
    return "Clause"


def parse_nodes(evidence: list[EvidenceSpan]) -> list[Node]:
    """Group spans by citation → one typed node per source, with attributes."""
    by_cite: "OrderedDict[str, list[EvidenceSpan]]" = OrderedDict()
    for s in evidence:
        by_cite.setdefault(s.citation, []).append(s)

    nodes: list[Node] = []
    for order, (cite, spans) in enumerate(by_cite.items()):
        text = " ".join(sp.quote for sp in spans)
        doc_id = spans[0].doc_id
        ntype = _node_type(cite, text)
        attrs = {
            "order": order,
            "notice_days": notice_days(text),
            "penalty_months": penalty_months(text),
            "negation": has_negation(text),
            "allows": allows_terminate(text),
            "references": references(text),
            "supersede_target": supersede_target(text),
            "governs_over_target": governs_over_target(text),
            "policy_override": is_policy_override(text),
            "introduces_fee": introduces_fee(text),
            "definition_term": definition_term(text),
            "unusable": ntype == "Document" and ("scanned" in (cite + text).lower()
                        or "not ocr" in text.lower() or "parser failure" in text.lower()),
            "version_base": re.match(r"(Amendment \d+)", cite).group(1) if re.match(r"(Amendment \d+)", cite) else None,
            "terminates": ("terminate for convenience" in text.lower()) or ("termination for convenience" in text.lower()),
        }
        nodes.append(Node(key=cite, type=ntype, doc_id=doc_id, text=text,
                          section=section_of(cite, text), attrs=attrs))
    return nodes

#!/usr/bin/env python3
"""
Hidden evaluation layer (AUDIT ONLY — never used for tuning or benchmark scores).

Extends the audit mirrors with additional variation categories: effective dates,
section numbering, nested exceptions, parallel authorities, multi-hop references —
on top of the existing entity/order and wording/override-phrasing mirrors. Scores
relationship-endpoint DISCOVERY per resolver to test generalisation.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.schema import Corpus, Document, EvidenceSpan

from agentic.hybrid_handover.resolution.audit.mirrors import MIRRORS as _BASE_MIRRORS

Q = "Can we terminate for convenience, and what notice and penalty apply?"


def _corpus(docs):
    return Corpus(documents=[Document(doc_id=d[0], citation=d[1], order=d[2], text=d[3], approx_tokens=1000) for d in docs])


def _sentences(corpus):
    out = []
    for doc in corpus.documents:
        for chunk in re.split(r"(?<=[.;])\s+", doc.text):
            s = chunk.strip()
            if s:
                i = doc.text.find(s)
                out.append(EvidenceSpan(quote=s, doc_id=doc.doc_id, citation=doc.citation,
                                        char_span=(i, i + len(s)), confidence=1.0))
    return out


# additional hidden mirrors: (id, capability, family, corpus, gold_edge)
_EXTRA = [
    ("date_supersede", "supersede", "date", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Effective 2019: neither party may terminate for convenience."),
        ("r", "Amendment 4 §3 p.204", 1, "Effective 2023: Section 7.1 is deleted and replaced: either party may terminate for convenience upon sixty (60) days notice."),
    ]), ("Amendment 4 §3 p.204", "supersedes", "MSA §7.1 p.12")),
    ("numbering_supersede", "supersede", "numbering", _corpus([
        ("b", "MSA §12.04 p.12", 0, "Neither party may terminate for convenience."),
        ("r", "Amendment 4 §3 p.204", 1, "Section 12.4 is deleted and replaced: either party may terminate for convenience upon sixty (60) days notice."),
    ]), ("Amendment 4 §3 p.204", "supersedes", "MSA §12.04 p.12")),
    ("nested_exception", "exception", "nested", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Either party may terminate for convenience upon sixty (60) days notice."),
        ("s1", "Schedule D §4 p.88", 1, "This applies generally, except that during the Initial Term the customer is locked in."),
        ("s2", "Schedule D §5 p.89", 2, "The foregoing exception does not apply to affiliates."),
    ]), ("Schedule D §4 p.88", "exception_to", "MSA §7.1 p.12")),
    ("parallel_authority", "override", "parallel", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Either party may terminate for convenience upon ninety (90) days notice."),
        ("p1", "Corporate Policy GOV-12 p.2", 1, "Company policy prohibits termination for convenience, notwithstanding any contract term."),
        ("p2", "Regulatory Directive R-9 p.1", 2, "Termination is barred, notwithstanding any contract term to the contrary."),
    ]), ("Corporate Policy GOV-12 p.2", "overrides", "MSA §7.1 p.12")),
    ("multi_hop_reference", "reference", "multihop", _corpus([
        ("a", "MSA §7.3 p.12", 0, "The penalty is as set out in Schedule C."),
        ("c", "Schedule C p.70", 1, "The penalty is as set out in Exhibit F."),
        ("f", "Exhibit F p.99", 2, "The early-termination penalty is four (4) months of fees."),
    ]), ("MSA §7.3 p.12", "references", "Schedule C p.70")),
]

HIDDEN = [(m[0], m[1], m[2], m[3], m[4]) for m in _BASE_MIRRORS] + _EXTRA


def run_hidden(resolver):
    rows = []
    for mid, cap, family, corpus, gold_edge in HIDDEN:
        graph = resolver.resolve_relationships(Q, _sentences(corpus))
        pairs = {(e.src, e.dst) for e in graph.edges}
        rows.append({"id": mid, "capability": cap, "family": family,
                     "endpoint_discovered": (gold_edge[0], gold_edge[2]) in pairs})
    return rows

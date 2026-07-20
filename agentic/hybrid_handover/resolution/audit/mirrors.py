#!/usr/bin/env python3
"""
Hidden mirror cases (AUDIT ONLY — never scored in the benchmark).

Each mirror preserves a capability but alters the surface. Two families per
capability:
  * entity/order/number mirror — changes entities, ordering, section numbers;
    KEEPS the relationship cue vocabulary. Tests generalisation across surface.
  * wording mirror — KEEPS entities; changes only the relationship cue phrase
    ("deleted and replaced" → "struck out and substituted", etc.). Tests whether
    the resolver depends on a fixed cue vocabulary shared with the gold.

Mirror scoring is EDGE-DETECTION only (relationship discovery): does the resolver
produce the gold relationship edge? This isolates discovery generalisation from
packet construction.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.schema import Corpus, Document

Q = "Can we terminate for convenience, and what notice and penalty apply?"


def _corpus(docs):
    return Corpus(documents=[Document(doc_id=d[0], citation=d[1], order=d[2], text=d[3],
                                      approx_tokens=1000) for d in docs])


def _sentences(corpus):
    from agentic.hybrid_handover.schema import EvidenceSpan
    out = []
    for doc in corpus.documents:
        for chunk in re.split(r"(?<=[.;])\s+", doc.text):
            s = chunk.strip()
            if s:
                i = doc.text.find(s)
                out.append(EvidenceSpan(quote=s, doc_id=doc.doc_id, citation=doc.citation,
                                        char_span=(i, i + len(s)), confidence=1.0))
    return out


# (id, capability, family, corpus, gold_edge)
MIRRORS = [
    # ---- supersede ----
    ("supersede_entity", "supersede", "entity", _corpus([
        ("b", "MSA-2 §12.4 p.9", 0, "Neither party may terminate for convenience."),
        ("r", "Rider 9 §2 p.88", 1, "Section 12.4 is deleted and replaced: either party may terminate for convenience upon sixty (60) days notice."),
    ]), ("Rider 9 §2 p.88", "supersedes", "MSA-2 §12.4 p.9")),
    ("supersede_wording", "supersede", "wording", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Neither party may terminate for convenience."),
        ("r", "Amendment 4 §3 p.204", 1, "Section 7.1 is struck out and substituted: either party may terminate for convenience upon sixty (60) days notice."),
    ]), ("Amendment 4 §3 p.204", "supersedes", "MSA §7.1 p.12")),

    # ---- governs_over ----
    ("governs_entity", "governs_over", "entity", _corpus([
        ("b", "MSA-2 §12.4 p.9", 0, "Either party may terminate for convenience upon ninety (90) days notice."),
        ("o", "Purchase Order §5 p.1", 1, "Termination for convenience is allowed. In the event of any conflict, the Purchase Order governs over the MSA-2."),
    ]), ("Purchase Order §5 p.1", "governs_over", "MSA-2 §12.4 p.9")),
    ("governs_wording", "governs_over", "wording", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Either party may terminate for convenience upon ninety (90) days notice."),
        ("o", "Order Form §2 p.1", 1, "Termination for convenience is allowed. In the event of any conflict, the Order Form shall control against the MSA."),
    ]), ("Order Form §2 p.1", "governs_over", "MSA §7.1 p.12")),

    # ---- override ----
    ("override_entity", "override", "entity", _corpus([
        ("b", "MSA-2 §12.4 p.9", 0, "Either party may terminate for convenience upon ninety (90) days notice."),
        ("p", "Corporate Policy GOV-99 p.2", 1, "Company policy prohibits termination for convenience, notwithstanding any contract term to the contrary."),
    ]), ("Corporate Policy GOV-99 p.2", "overrides", "MSA-2 §12.4 p.9")),
    ("override_wording", "override", "wording", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Either party may terminate for convenience upon ninety (90) days notice."),
        ("p", "Corporate Policy GOV-12 p.2", 1, "Company policy prohibits termination for convenience, regardless of any contract clause to the contrary."),
    ]), ("Corporate Policy GOV-12 p.2", "overrides", "MSA §7.1 p.12")),

    # ---- exception ----
    ("exception_entity", "exception", "entity", _corpus([
        ("b", "MSA-2 §12.4 p.9", 0, "Either party may terminate for convenience upon sixty (60) days notice."),
        ("s", "Schedule Q §4 p.88", 1, "This applies generally, except that during the Pilot Term the buyer is locked in."),
    ]), ("Schedule Q §4 p.88", "exception_to", "MSA-2 §12.4 p.9")),
    ("exception_wording", "exception", "wording", _corpus([
        ("b", "MSA §7.1 p.12", 0, "Either party may terminate for convenience upon sixty (60) days notice."),
        ("s", "Schedule D §4 p.88", 1, "This applies generally, save where during the Initial Term the customer is locked in."),
    ]), ("Schedule D §4 p.88", "exception_to", "MSA §7.1 p.12")),
]


def run_mirrors(resolver):
    rows = []
    for mid, cap, family, corpus, gold_edge in MIRRORS:
        ev = _sentences(corpus)
        graph = resolver.resolve_relationships(Q, ev)
        detected = tuple(gold_edge) in graph.edge_triples()
        rows.append({"mirror": mid, "capability": cap, "family": family, "edge_detected": detected})
    return rows

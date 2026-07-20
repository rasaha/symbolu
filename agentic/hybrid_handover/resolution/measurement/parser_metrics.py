#!/usr/bin/env python3
"""
Parser-owned metrics (SemanticParser). Negation interpretation and node typing
are done by the shared lexical parser, NOT by any resolver — so they are measured
directly against the parser on labelled probes and must never inflate a resolver's
capability score.
"""

from __future__ import annotations

from agentic.hybrid_handover.resolution.parse import _node_type, has_negation

NEGATION_PROBES = [
    ("Either party may terminate for convenience.", False),
    ("Neither party may terminate for convenience.", True),
    ("In no event may either party terminate for convenience.", True),
    ("Termination for convenience requires ninety (90) days notice.", False),
    ("The parties shall not terminate for convenience during the Term.", True),
    ("Termination is permitted for cause.", False),
]

TYPE_PROBES = [
    ("MSA §1 p.3", "Confidential Information means written material.", "Definition"),
    ("Fee Table Exhibit B p.60", "Fee schedule. Early-termination fee: six (6) months.", "Table"),
    ("Corporate Policy GOV-12 p.2", "Company policy prohibits termination, notwithstanding any contract term.", "Policy"),
    ("Amendment 3 (v1) p.150", "Either party may terminate for convenience.", "Version"),
    ("Schedule D §4 p.88", "This applies generally, except that the buyer is locked in.", "Exception"),
    ("MSA §7.1 p.12", "Either party may terminate for convenience upon ninety (90) days notice.", "Clause"),
    ("Annex A p.400", "[SCANNED IMAGE - NOT OCR'D]", "Document"),
]


def parser_metrics():
    neg_ok = sum(1 for text, exp in NEGATION_PROBES if has_negation(text) == exp)
    type_ok = sum(1 for cite, text, exp in TYPE_PROBES if _node_type(cite, text) == exp)
    return {
        "parser_negation_accuracy": round(neg_ok / len(NEGATION_PROBES), 4),
        "parser_type_accuracy": round(type_ok / len(TYPE_PROBES), 4),
        "_neg_probes": len(NEGATION_PROBES), "_type_probes": len(TYPE_PROBES),
    }

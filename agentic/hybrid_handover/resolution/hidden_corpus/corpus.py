#!/usr/bin/env python3
"""
Resolver-facing view of the hidden corpus. Exposes ONLY the executable content:
an opaque content-hash id, the question, and the documents. No capability,
difficulty, gold graph, governance, or expectation is reachable through this
module — those live in `annotations.py` (evaluation-facing).

The id is a SHA-1 of the executable content only, so it encodes nothing about
the answer, capability, or difficulty. Corpus order is by id (hash order), which
is uncorrelated with difficulty/capability.
"""

from __future__ import annotations

import hashlib

from agentic.hybrid_handover.schema import EvidenceSpan

from ._authored import AUTHORED


def opaque_id(authored: dict) -> str:
    blob = authored["question"] + "|" + "|".join(d["text"] for d in authored["documents"])
    return "HX" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:10]


# opaque id -> authored record (private; not exported)
_BY_ID = {opaque_id(a): a for a in AUTHORED}


def executable_cases() -> list[dict]:
    """Resolver-facing: id + question + documents only. Ordered by id."""
    out = []
    for cid in sorted(_BY_ID):
        a = _BY_ID[cid]
        out.append({
            "id": cid,
            "question": a["question"],
            "documents": [dict(doc_id=d["doc_id"], citation=d["citation"],
                               order=d["order"], text=d["text"]) for d in a["documents"]],
        })
    return out


def evidence_for(cid: str) -> list[EvidenceSpan]:
    """Resolver-facing evidence (all sentences) for an executable case."""
    import re
    a = _BY_ID[cid]
    spans = []
    for d in a["documents"]:
        for chunk in re.split(r"(?<=[.;])\s+", d["text"]):
            s = chunk.strip()
            if not s:
                continue
            i = d["text"].find(s)
            spans.append(EvidenceSpan(quote=s, doc_id=d["doc_id"], citation=d["citation"],
                                      char_span=(i, i + len(s)), confidence=1.0))
    return spans


def case_ids() -> list[str]:
    return sorted(_BY_ID)

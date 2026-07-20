#!/usr/bin/env python3
"""
Resolver-facing view of the ACCEPTED pilot cases only. Rejected/quarantined
candidates are NEVER loadable here. Executable content only (opaque id + question
+ documents); no annotation.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.schema import EvidenceSpan

from .records import accepted_candidates, opaque_id

_BY_ID = {opaque_id(c): c for c in accepted_candidates()}


def executable_cases() -> list[dict]:
    out = []
    for cid in sorted(_BY_ID):
        c = _BY_ID[cid]
        out.append({"id": cid, "question": c["question"],
                    "documents": [dict(doc_id=d["doc_id"], citation=d["citation"],
                                       order=d["order"], text=d["text"]) for d in c["documents"]]})
    return out


def evidence_for(cid: str) -> list[EvidenceSpan]:
    c = _BY_ID[cid]
    spans = []
    for d in c["documents"]:
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


def is_loadable(cid: str) -> bool:
    return cid in _BY_ID

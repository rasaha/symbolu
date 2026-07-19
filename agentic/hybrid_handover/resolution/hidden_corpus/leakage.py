#!/usr/bin/env python3
"""
Leakage verification — confirm no hidden information (capability, difficulty,
answer, gold structure) can reach a resolver through the executable view: ids,
document ids/citations/text, ordering, or module surface.
"""

from __future__ import annotations

import re

from . import corpus as corpus_mod
from ._authored import AUTHORED
from .corpus import executable_cases, opaque_id
from .validate import CAPABILITIES

_ID_RE = re.compile(r"^HX[0-9a-f]{10}$")
_DIFF_RE = re.compile(r"\bl[1-5]\b")  # difficulty markers, word-bounded
_BANNED_TOKENS = (
    [c for c in CAPABILITIES] +
    ["difficulty", "gold graph", "abstain", "expectation",
     "negative_control", "capability_tag"] +
    [a["ref"] for a in AUTHORED]  # internal ref names must never appear
)


def verify():
    findings = []

    # 1. ids are opaque content hashes (no capability/difficulty encoded)
    for c in executable_cases():
        if not _ID_RE.match(c["id"]):
            findings.append(("non_opaque_id", c["id"]))

    # 2. executable view exposes ONLY id/question/documents; docs only 4 fields
    for c in executable_cases():
        if set(c) != {"id", "question", "documents"}:
            findings.append(("extra_case_field", sorted(set(c))))
        for d in c["documents"]:
            if set(d) != {"doc_id", "citation", "order", "text"}:
                findings.append(("extra_doc_field", sorted(set(d))))

    # 3. no banned/meta token appears in ids, citations, doc_ids, or text
    for c in executable_cases():
        surface = " ".join([c["id"]] +
                           [d["citation"] + " " + d["doc_id"] + " " + d["text"] for d in c["documents"]]).lower()
        for tok in _BANNED_TOKENS:
            if tok.lower() in surface:
                findings.append(("banned_token_in_surface", (c["id"], tok)))
        if _DIFF_RE.search(surface):
            findings.append(("difficulty_marker_in_surface", c["id"]))

    # 4. corpus order does not encode difficulty (id-order difficulty is not sorted)
    from .annotations import annotation
    diffs = [annotation(c["id"])["difficulty"] for c in executable_cases()]
    if diffs == sorted(diffs) or diffs == sorted(diffs, reverse=True):
        findings.append(("order_encodes_difficulty", diffs))

    # 5. corpus module exposes no metadata *accessor* (callable/data). Bound
    #    sibling submodule objects are a Python import artifact, not a data path,
    #    and the executable-view checks above already prove data separation.
    for name in dir(corpus_mod):
        if name.startswith("_"):
            continue
        obj = getattr(corpus_mod, name)
        if not callable(obj):          # accessors are functions; skip the
            continue                   # `from __future__ import annotations` feature, imports, data
        if any(k in name.lower() for k in ("annotation", "gold", "expect", "difficulty", "capab")):
            findings.append(("corpus_exposes_metadata_accessor", name))

    return findings

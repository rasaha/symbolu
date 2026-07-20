#!/usr/bin/env python3
"""Extended leakage verification for the pilot: resolver-facing artifacts expose
no curation metadata, and rejected/quarantined cases cannot be loaded."""

from __future__ import annotations

import re

from . import pilot_corpus
from ..validate import CAPABILITIES
from .records import all_candidates, opaque_id

_ID_RE = re.compile(r"^HP[0-9a-f]{10}$")
_DIFF_RE = re.compile(r"\bl[1-5]\b")
_BANNED = (
    list(CAPABILITIES) +
    ["difficulty", "capability", "lifecycle", "author", "annotator", "adjudicat",
     "template", "confidence", "ambiguity", "governance outcome", "packet",
     "abstention", "quarantin", "rejected", "accepted", "gold graph"] +
    [c["ref"] for c in all_candidates()]
)


def verify():
    findings = []
    cases = pilot_corpus.executable_cases()

    # 1. opaque ids
    for c in cases:
        if not _ID_RE.match(c["id"]):
            findings.append(("non_opaque_id", c["id"]))

    # 2. executable view exposes only id/question/documents; docs 4 fields
    for c in cases:
        if set(c) != {"id", "question", "documents"}:
            findings.append(("extra_case_field", sorted(set(c))))
        for d in c["documents"]:
            if set(d) != {"doc_id", "citation", "order", "text"}:
                findings.append(("extra_doc_field", sorted(set(d))))

    # 3. no banned/meta token or ref name in surface
    for c in cases:
        surface = " ".join([c["id"]] + [d["citation"] + " " + d["doc_id"] + " " + d["text"]
                                        for d in c["documents"]]).lower()
        for tok in _BANNED:
            if tok.lower() in surface:
                findings.append(("banned_token_in_surface", (c["id"], tok)))
        if _DIFF_RE.search(surface):
            findings.append(("difficulty_marker_in_surface", c["id"]))

    # 4. rejected / quarantined candidates are NOT loadable
    for cand in all_candidates():
        if cand["decision"] != "ACCEPTED":
            if pilot_corpus.is_loadable(opaque_id(cand)):
                findings.append(("non_accepted_loadable", (opaque_id(cand), cand["decision"])))

    # 5. pilot corpus module exposes no metadata accessor (callable)
    for name in dir(pilot_corpus):
        if name.startswith("_"):
            continue
        obj = getattr(pilot_corpus, name)
        if callable(obj) and any(k in name.lower() for k in
                                 ("annotation", "gold", "expect", "difficulty", "capab", "adjud")):
            findings.append(("corpus_exposes_metadata_accessor", name))
    return findings

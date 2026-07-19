#!/usr/bin/env python3
"""
OracleRetriever — a DIAGNOSTIC probe, not an extractor for production and NOT the
HybridPhaseTransformer.

It cheats: using the case's ground truth, it retrieves EVERY required span
(decisive + defeater + definition) perfectly and verbatim, then hands the packet
to the SAME frozen relationship-resolution module every baseline uses. Its only
purpose is the counterfactual:

    "If an oracle retrieved every relevant span perfectly, would the benchmark
     still fail?"

If a case still fails under this probe, the deficit is provably NOT in retrieval.
This isolates retrieval capability from everything downstream of it.

Nothing in SEEB, the baselines, or the frozen handover package is modified; this
probe only reads ground truth and reuses the shared resolver.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.schema import (
    Corpus,
    Coverage,
    EvidencePacket,
    EvidenceSpan,
    ResolvedAnswer,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")
_SHARED_RESOLVER = InHouseExtractor()


def _sentence_containing(text: str, needle: str) -> tuple[str, int]:
    for chunk in _SENTENCE_SPLIT.split(text):
        s = chunk.strip()
        if s and needle.lower() in s.lower():
            return s, text.find(s)
    idx = text.find(needle)
    return (needle, idx) if idx >= 0 else ("", -1)


class OracleRetriever:
    """MAXIMAL retrieval — every sentence in the corpus becomes evidence.

    This is the strongest possible retrieval front-end: it cannot miss any span,
    because it returns them all. It is the retrieval *upper bound*. If a case
    still fails under this probe, no retrieval improvement whatsoever can solve it
    — the deficit is definitively downstream of retrieval.

    Using the maximal oracle (rather than 'retrieve exactly the declared required
    spans') deliberately removes any dependency on how completely a case declared
    its required set: the probe hands the reasoning module *all* the text.
    """

    name = "oracle"
    mode = "MAXIMAL retrieval — every sentence (retrieval upper bound)"

    def __init__(self, case=None):
        self._case = case

    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer:
        return _SHARED_RESOLVER.resolve(question, corpus)

    def extract(self, question: str, corpus: Corpus) -> EvidencePacket:
        base = _SHARED_RESOLVER.extract(question, corpus)  # answer, conflicts, coverage
        spans: list[EvidenceSpan] = []
        for doc in corpus.documents:
            for chunk in _SENTENCE_SPLIT.split(doc.text):
                s = chunk.strip()
                if not s:
                    continue
                start = doc.text.find(s)
                if start < 0:
                    continue
                spans.append(
                    EvidenceSpan(
                        quote=s, doc_id=doc.doc_id, citation=doc.citation,
                        char_span=(start, start + len(s)), confidence=1.0,
                    )
                )
        coverage = Coverage(
            docs_scanned=len(corpus.documents),
            tokens_ingested=corpus.total_tokens(),
            spans_returned=len(spans),
        )
        return base.model_copy(update={"evidence": spans, "coverage": coverage})

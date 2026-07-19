#!/usr/bin/env python3
"""
KeywordExtractor — the existing deterministic baseline, wrapped behind
ExtractorProtocol.

This is `InHouseExtractor` itself: keyword/sentence retrieval + the shared
full-corpus rule resolver. It is included unchanged so the comparison is anchored
on the officially-frozen SEEB baseline (see BASELINE_RESULTS.md).
"""

from __future__ import annotations

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.schema import Corpus, EvidencePacket, ResolvedAnswer


class KeywordExtractor:
    name = "keyword"
    mode = "deterministic keyword/sentence match (frozen baseline)"

    def __init__(self):
        self._inner = InHouseExtractor()

    def extract(self, question: str, corpus: Corpus) -> EvidencePacket:
        return self._inner.extract(question, corpus)

    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer:
        return self._inner.resolve(question, corpus)

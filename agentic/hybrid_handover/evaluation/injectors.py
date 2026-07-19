#!/usr/bin/env python3
"""
Deterministic fault injectors.

Two hook points:
  * ``apply_corpus``  — degrade the corpus BEFORE extraction (parser/OCR/coverage
    faults). Tests the whole pipeline including the extractor and coverage checks.
  * ``apply_packet``  — degrade the packet AFTER extraction (dropped spans,
    corrupted locators). Simulates a lossy extractor and tests the validators in
    isolation.

Every injector removes or corrupts *decisive* evidence, so for an injected case
the enterprise-safe outcome is always REFUSE. Any accept is an unsafe handover.
All injectors are deterministic (no randomness that varies run to run — the
"random" chunk remover uses a fixed rule).
"""

from __future__ import annotations

import copy

from agentic.hybrid_handover.schema import Corpus, EvidencePacket


class Injector:
    name: str = "identity"
    kind: str = "packet"  # "corpus" | "packet"

    def apply_corpus(self, corpus: Corpus) -> Corpus:
        return corpus

    def apply_packet(self, packet: EvidencePacket) -> EvidencePacket:
        return packet


# --- packet-level: simulate a lossy extractor ------------------------------ #
class DropCriticalSpan(Injector):
    name, kind = "DropCriticalSpan", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        # drop the span that carries the termination-for-convenience verdict
        p.evidence = [s for s in p.evidence if "terminate for convenience" not in s.quote.lower()][:]
        return p


class DropException(Injector):
    name, kind = "DropException", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        terms = ("except", "notwithstanding", "in no event", "governs over", "prevails")
        p.evidence = [s for s in p.evidence if not any(t in s.quote.lower() for t in terms)]
        return p


class DropDefinition(Injector):
    name, kind = "DropDefinition", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        p.evidence = [s for s in p.evidence if " means " not in s.quote.lower()]
        return p


class DropLastAmendment(Injector):
    name, kind = "DropLastAmendment", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        if not p.evidence:
            return p
        last_doc = max((s.doc_id for s in p.evidence), key=lambda d: d)  # deterministic
        # drop spans from the highest-order document actually present
        by_doc = {}
        for s in p.evidence:
            by_doc.setdefault(s.doc_id, []).append(s)
        # remove the last-inserted doc's spans
        drop = list(by_doc.keys())[-1]
        p.evidence = [s for s in p.evidence if s.doc_id != drop]
        p.conflicts_resolved = []  # the supersession it recorded is now unsupported
        return p


class DropPrecedenceRule(Injector):
    name, kind = "DropPrecedenceRule", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        p.conflicts_resolved = []
        return p


class CorruptLocator(Injector):
    name, kind = "CorruptLocator", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        if p.evidence:
            s = p.evidence[0]
            s.char_span = (s.char_span[0] + 3, s.char_span[1] + 3)  # off-by-3 offset
        return p


class TruncatedPacket(Injector):
    name, kind = "TruncatedPacket", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        p.evidence = p.evidence[: max(0, len(p.evidence) - 1)]  # drop the last span
        return p


class RandomChunkRemoval(Injector):
    """Deterministic 'random' removal: drop every other span."""
    name, kind = "RandomChunkRemoval", "packet"

    def apply_packet(self, packet):
        p = packet.model_copy(deep=True)
        p.evidence = [s for i, s in enumerate(p.evidence) if i % 2 == 0]
        return p


# --- corpus-level: degrade sources before extraction ----------------------- #
class DuplicateWrongVersion(Injector):
    name, kind = "DuplicateWrongVersion", "corpus"

    def apply_corpus(self, corpus):
        c = corpus.model_copy(deep=True)
        if not c.documents:
            return c
        d = c.documents[0].model_copy(deep=True)
        d.doc_id = d.doc_id + "_dupwrong"
        d.citation = d.citation + " (conflicting copy)"
        d.text = d.text.replace("ninety (90)", "thirty (30)").replace("Either", "Neither")
        c.documents.append(d)
        return c


class ParserFailure(Injector):
    name, kind = "ParserFailure", "corpus"

    def apply_corpus(self, corpus):
        c = corpus.model_copy(deep=True)
        if c.documents:
            c.documents[0].text = "[PARSER FAILURE - CONTENT UNAVAILABLE]"
        return c


class OCRNoise(Injector):
    name, kind = "OCRNoise", "corpus"

    def apply_corpus(self, corpus):
        c = corpus.model_copy(deep=True)
        if c.documents:
            t = c.documents[0].text
            t = t.replace("terminate", "terrninate").replace("convenience", "c0nvenience")
            t = t.replace("notice", "n0tice").replace("o", "0", 2)
            c.documents[0].text = t
            c.documents[0].citation += " (scanned)"
        return c


class MissingAnnex(Injector):
    name, kind = "MissingAnnex", "corpus"

    def apply_corpus(self, corpus):
        c = corpus.model_copy(deep=True)
        # inject a reference to a doc that is not present, and drop the decisive doc
        if c.documents:
            c.documents[0].text += " Fees are set out in Appendix 9."
            if len(c.documents) > 1:
                c.documents = c.documents[:1]  # drop everything after the first
        return c


class BrokenReference(Injector):
    name, kind = "BrokenReference", "corpus"

    def apply_corpus(self, corpus):
        c = corpus.model_copy(deep=True)
        if c.documents:
            c.documents[0].text += " The governing terms are defined in Schedule Z."
        return c


PACKET_INJECTORS = [
    DropCriticalSpan(), DropException(), DropDefinition(), DropLastAmendment(),
    DropPrecedenceRule(), CorruptLocator(), TruncatedPacket(), RandomChunkRemoval(),
]
CORPUS_INJECTORS = [
    DuplicateWrongVersion(), ParserFailure(), OCRNoise(), MissingAnnex(), BrokenReference(),
]
ALL_INJECTORS = PACKET_INJECTORS + CORPUS_INJECTORS

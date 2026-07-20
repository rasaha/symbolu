#!/usr/bin/env python3
"""
Independent packet validation.

The frozen pipeline's packet-vs-full consistency gate (``packet_only_reresolve``)
is necessary but not sufficient: it only checks that the packet re-resolves to
the SAME answer the extractor already produced — a shared blind spot survives it.
These validators are independent of the extractor's own reasoning:

  * SpanIntegrityValidator     — spans quote canonical source verbatim
  * EvidenceToClaimValidator   — every claim cites supporting evidence
  * ContradictionSearchValidator — re-scan the FULL corpus for defeater language
                                   the packet omitted (the key completeness check)
  * CoverageValidator          — every expected doc parsed & searched; references
                                   resolved; corrupt/truncated sources blocked

Any validator that fails with ``blocks_handover=True`` forces the pipeline to
REFUSE — fail closed.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from agentic.hybrid_handover.schema import Corpus, EvidencePacket


class ValidationOutcome(BaseModel):
    name: str
    passed: bool
    blocks_handover: bool
    findings: list[str] = []


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


# --------------------------------------------------------------------------- #
class SpanIntegrityValidator:
    name = "span_integrity"

    def validate(self, case, packet: EvidencePacket, corpus: Corpus) -> ValidationOutcome:
        findings = []
        for span in packet.evidence:
            doc = corpus.by_id(span.doc_id)
            if doc is None:
                findings.append(f"{span.citation}: unknown doc {span.doc_id!r}")
                continue
            a, b = span.char_span
            if doc.text[a:b] != span.quote:
                findings.append(f"{span.citation}: char_span {span.char_span} != quote")
        return ValidationOutcome(name=self.name, passed=not findings,
                                 blocks_handover=bool(findings), findings=findings)


# --------------------------------------------------------------------------- #
class EvidenceToClaimValidator:
    """Every factual field in the resolved answer must be backed by an evidence
    span. Unsupported claims fail closed."""
    name = "evidence_to_claim"

    def validate(self, case, packet: EvidencePacket, corpus: Corpus) -> ValidationOutcome:
        findings = []
        quotes = [_norm(s.quote) for s in packet.evidence]
        cites = {s.citation for s in packet.evidence}
        ra = packet.resolved_answer

        def supported(pred) -> bool:
            return any(pred(q) for q in quotes)

        if ra.termination_for_convenience in ("allowed", "prohibited"):
            if not supported(lambda q: "terminate for convenience" in q):
                findings.append("verdict 'termination_for_convenience' has no supporting span")
        if ra.notice_days is not None:
            token = f"({ra.notice_days})"
            if not supported(lambda q: token in q or str(ra.notice_days) in q):
                findings.append(f"notice_days={ra.notice_days} has no supporting span")
        if ra.penalty:
            if not supported(lambda q: "fee" in q or "month" in q):
                findings.append("penalty has no supporting span")
        for c in ra.governing_citations:
            if c not in cites:
                findings.append(f"governing citation {c!r} not present in evidence")
        return ValidationOutcome(name=self.name, passed=not findings,
                                 blocks_handover=bool(findings), findings=findings)


# --------------------------------------------------------------------------- #
class ContradictionSearchValidator:
    """Actively search the full corpus for defeating language and confirm each
    such sentence is represented in the packet. A defeater present in the source
    but absent from the packet is an unsafe omission."""
    name = "contradiction_search"

    DEFEATER_TERMS = (
        "except", "exception", "notwithstanding", "provided that", "shall not",
        "in no event", "supersede", "deleted and replaced", "governs over",
        "takes precedence", "prevails", "excluding", "no termination",
        "neither party", "policy prohibits",
    )

    def _sentences(self, text: str):
        for chunk in re.split(r"(?<=[.;])\s+", text):
            yield chunk.strip()

    def validate(self, case, packet: EvidencePacket, corpus: Corpus) -> ValidationOutcome:
        findings = []
        packet_norm = [_norm(s.quote) for s in packet.evidence]
        for doc in corpus.documents:
            for sent in self._sentences(doc.text):
                low = sent.lower()
                if any(term in low for term in self.DEFEATER_TERMS):
                    ns = _norm(sent)
                    covered = any(ns in q or q in ns for q in packet_norm)
                    if not covered:
                        findings.append(f"{doc.citation}: uncovered defeater: {sent!r}")
        return ValidationOutcome(name=self.name, passed=not findings,
                                 blocks_handover=bool(findings), findings=findings)


# --------------------------------------------------------------------------- #
class CoverageValidator:
    """Confirm every expected document was successfully parsed and searched, and
    that named cross-references resolve. Coverage failure blocks handover."""
    name = "coverage"

    CORRUPT_MARKERS = ("[SCANNED", "[PARSER FAILURE", "[MISSING", "[OCR", "NOT OCR")
    OCR_HINTS = ("terrninate", "c0nvenience", "n0tice", "�")
    REF_PATTERNS = (r"Appendix\s+\w+", r"Schedule\s+\w+", r"Annex\s+\w+", r"Exhibit\s+\w+")

    def validate(self, case, packet: EvidencePacket, corpus: Corpus) -> ValidationOutcome:
        findings = []
        present_ids = {d.doc_id for d in corpus.documents}

        # 1. expected docs present & non-empty
        for did in case.expected_doc_ids:
            doc = corpus.by_id(did)
            if doc is None or not doc.text.strip():
                findings.append(f"expected doc {did!r} missing or empty")

        # 2. corrupt / un-parsed / OCR-garbled sources
        for doc in corpus.documents:
            up = doc.text.upper()
            if any(m in up for m in self.CORRUPT_MARKERS):
                findings.append(f"{doc.citation}: unusable source (corrupt/scanned/parser-fail)")
            if any(h in doc.text for h in self.OCR_HINTS):
                findings.append(f"{doc.citation}: probable OCR corruption")

        # 3. named cross-references must resolve to a present document citation
        cited_text = " ".join(d.citation for d in corpus.documents)
        for doc in corpus.documents:
            for pat in self.REF_PATTERNS:
                for m in re.findall(pat, doc.text):
                    if m.lower() not in cited_text.lower() and not any(
                        m.lower() in d.text.lower() and d.doc_id != doc.doc_id
                        for d in corpus.documents
                    ):
                        findings.append(f"{doc.citation}: unresolved reference to {m!r}")

        # 4. declared referenced_docs must resolve
        for ref in case.referenced_docs:
            resolved = any(
                ref.lower() in d.citation.lower()
                or (ref.lower() in d.text.lower() and d.text.strip() and
                    not any(mk in d.text.upper() for mk in self.CORRUPT_MARKERS)
                    and _looks_like_definition_of(d, ref))
                for d in corpus.documents
            )
            if not resolved:
                findings.append(f"declared reference {ref!r} does not resolve to a usable document")

        # dedupe, keep order
        seen, uniq = set(), []
        for f in findings:
            if f not in seen:
                seen.add(f); uniq.append(f)
        return ValidationOutcome(name=self.name, passed=not uniq,
                                 blocks_handover=bool(uniq), findings=uniq)


def _looks_like_definition_of(doc, ref: str) -> bool:
    """A reference resolves only if some *other* document actually supplies the
    referenced content (not merely names it back — that is a circular ref)."""
    low = doc.text.lower()
    # a circular pointer just re-references; a real target states a value/definition
    if "as defined in" in low or "as set out in the" in low:
        return False
    return True


DEFAULT_VALIDATORS = [
    SpanIntegrityValidator(),
    EvidenceToClaimValidator(),
    ContradictionSearchValidator(),
    CoverageValidator(),
]

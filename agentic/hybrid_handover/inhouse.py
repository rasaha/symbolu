#!/usr/bin/env python3
"""
In-house tier (Part 1) — a deterministic stand-in for the O(n) hybrid model.

This is intentionally a rules-based extractor, not the neural model: the point
of the scaffold is to make the *handover* real and testable, model-agnostic.
Swapping this class for a `HybridPhaseTransformer`-backed extractor that
implements the same ``extract`` / ``resolve`` interface changes nothing
downstream — the gates, redaction, and frontier wiring are identical.

Responsibilities:
- ``extract``  : locate termination/notice/penalty spans across the whole corpus
                 with exact char offsets, and reconcile supersessions.
- ``resolve``  : the pure verdict function reused by the faithfulness gate to
                 re-resolve over the packet alone.
"""

from __future__ import annotations

import re

from .schema import (
    ConflictResolution,
    Corpus,
    Coverage,
    EvidencePacket,
    EvidenceSpan,
    ResolvedAnswer,
)

_KEYWORDS = ("terminat", "convenience", "notice", "penalt", "fee")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+")
_PAREN_NUM = re.compile(r"\((\d+)\)")


def _iter_sentences(text: str):
    """Yield (sentence, start_offset) for sentences containing a keyword."""
    pos = 0
    for chunk in _SENTENCE_SPLIT.split(text):
        idx = text.find(chunk, pos)
        if idx < 0:
            idx = text.find(chunk)
        pos = idx + len(chunk)
        low = chunk.lower()
        if any(k in low for k in _KEYWORDS):
            yield chunk.strip(), text.find(chunk.strip(), idx if idx >= 0 else 0)


def _parse_paren_int(quote: str) -> int | None:
    m = _PAREN_NUM.search(quote)
    return int(m.group(1)) if m else None


class InHouseExtractor:
    """Distill-and-reconcile tier. Deterministic; implements the ``Resolver``
    protocol used by the faithfulness gate."""

    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer:
        """Pure verdict: applies 'later document governs' to termination-for-
        convenience, notice, and penalty. Runs identically over the full corpus
        or over a packet-only mini-corpus."""
        tfc = "unknown"
        notice_days: int | None = None
        penalty: str | None = None
        governing: list[str] = []

        for doc in sorted(corpus.documents, key=lambda d: d.order):
            low = doc.text.lower()
            cite = doc.citation
            # base prohibition
            if "neither party may terminate for convenience" in low:
                tfc = "prohibited"
                governing = [cite]
            # override: an amendment re-granting termination for convenience
            if "terminate for convenience" in low and (
                "either party may" in low or "any party may" in low
            ):
                tfc = "allowed"
                governing = [cite]
                nd = _parse_paren_int(doc.text)
                if nd is not None:
                    notice_days = nd
            # penalty: latest doc that sets a termination fee
            if "termination fee" in low or ("fee" in low and "month" in low):
                n = None
                m = re.search(r"\((\d+)\)\s*month", doc.text, re.IGNORECASE)
                if m:
                    n = int(m.group(1))
                penalty = f"{n} months' fees" if n is not None else "fee applies"
                if cite not in governing:
                    governing.append(cite)

        return ResolvedAnswer(
            termination_for_convenience=tfc,
            notice_days=notice_days,
            penalty=penalty,
            governing_citations=governing,
        )

    def extract(self, question: str, corpus: Corpus) -> EvidencePacket:
        """Full Part-1 pass: gather grounded spans, resolve, package."""
        spans: list[EvidenceSpan] = []
        for doc in corpus.documents:
            for sentence, offset in _iter_sentences(doc.text):
                # guarantee exact grounding: locate the sentence verbatim
                start = doc.text.find(sentence)
                if start < 0:
                    continue
                spans.append(
                    EvidenceSpan(
                        quote=sentence,
                        doc_id=doc.doc_id,
                        citation=doc.citation,
                        char_span=(start, start + len(sentence)),
                        confidence=0.96,
                    )
                )

        resolved = self.resolve(question, corpus)

        conflicts: list[ConflictResolution] = []
        if resolved.termination_for_convenience == "allowed":
            # the base prohibition lives in the earliest doc; the grant in a later one
            ordered = sorted(corpus.documents, key=lambda d: d.order)
            base = next(
                (d for d in ordered
                 if "neither party may terminate for convenience" in d.text.lower()),
                None,
            )
            grant = next(
                (d for d in reversed(ordered)
                 if "terminate for convenience" in d.text.lower()
                 and ("either party may" in d.text.lower()
                      or "any party may" in d.text.lower())),
                None,
            )
            if base is not None and grant is not None and base.doc_id != grant.doc_id:
                conflicts.append(
                    ConflictResolution(
                        clause="termination_for_convenience",
                        superseded=base.citation,
                        superseded_by=grant.citation,
                        rule="later amendment governs",
                    )
                )

        coverage = Coverage(
            docs_scanned=len(corpus.documents),
            tokens_ingested=corpus.total_tokens(),
            spans_returned=len(spans),
        )
        return EvidencePacket(
            question=question,
            evidence=spans,
            conflicts_resolved=conflicts,
            resolved_answer=resolved,
            coverage=coverage,
        )

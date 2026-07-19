#!/usr/bin/env python3
"""
Faithfulness gates — the make-or-break of the two-tier design.

The cost story ("hand the frontier API 4K tokens instead of 250K") only holds
if the distilled packet still *contains the answer*. If the in-house tier drops
the needle but still asserts a verdict, the enterprise gets a cheap wrong
answer — worse than an expensive right one. These gates catch that before
anything egresses.

Two independent checks:

1. ``ground_spans`` — every evidence span must re-slice to its verbatim quote in
   the source corpus. An ungrounded (paraphrased / mis-offset / hallucinated)
   span fails. This is a *cheap, total* check with no oracle required.

2. ``packet_only_reresolve`` — re-run the SAME resolution logic against ONLY the
   packet's quotes and confirm it reproduces the resolved answer computed over
   the full corpus. If the two diverge, the packet lost information the verdict
   depended on → refuse the handover. This is the "did we drop the needle?"
   check, and it needs no ground-truth oracle: the packet must stand on its own.
"""

from __future__ import annotations

from typing import Protocol

from .schema import Corpus, Document, EvidencePacket, ResolvedAnswer


class Resolver(Protocol):
    """Anything that turns a corpus + question into a structured verdict.
    The in-house extractor exposes this so the faithfulness gate can re-run the
    exact same logic over the packet-only mini-corpus."""

    def resolve(self, question: str, corpus: Corpus) -> ResolvedAnswer: ...


class GroundingReport:
    def __init__(self, ok: bool, ungrounded: list[str]):
        self.ok = ok
        self.ungrounded = ungrounded

    def __repr__(self) -> str:
        return f"GroundingReport(ok={self.ok}, ungrounded={self.ungrounded!r})"


def ground_spans(packet: EvidencePacket, corpus: Corpus) -> GroundingReport:
    """Verify each evidence span quotes its source verbatim at the stated
    offsets. Ungrounded spans are reported; caller refuses the packet if any."""
    ungrounded: list[str] = []
    for span in packet.evidence:
        doc = corpus.by_id(span.doc_id)
        if doc is None:
            ungrounded.append(f"{span.citation}: unknown doc_id {span.doc_id!r}")
            continue
        start, end = span.char_span
        sliced = doc.text[start:end]
        if sliced != span.quote:
            ungrounded.append(
                f"{span.citation}: offset {span.char_span} != quote"
            )
    return GroundingReport(ok=not ungrounded, ungrounded=ungrounded)


class FaithfulnessReport:
    def __init__(self, ok: bool, full: ResolvedAnswer, packet_only: ResolvedAnswer):
        self.ok = ok
        self.full = full
        self.packet_only = packet_only

    def __repr__(self) -> str:
        return (
            f"FaithfulnessReport(ok={self.ok}, "
            f"full={self.full.key()}, packet_only={self.packet_only.key()})"
        )


def _packet_as_corpus(packet: EvidencePacket) -> Corpus:
    """Rebuild a mini-corpus from the packet's quotes alone, preserving each
    span's originating citation and document order so the resolver sees the same
    supersession structure it would in the full corpus — but nothing else."""
    # Group quotes by source doc, keep original citations; order by first appearance.
    docs: list[Document] = []
    seen: dict[str, Document] = {}
    order = 0
    for span in packet.evidence:
        if span.doc_id not in seen:
            doc = Document(
                doc_id=span.doc_id,
                citation=span.citation,
                order=order,
                text="",
            )
            seen[span.doc_id] = doc
            docs.append(doc)
            order += 1
        d = seen[span.doc_id]
        d.text = (d.text + " " + span.quote).strip()
    return Corpus(documents=docs)


def packet_only_reresolve(
    packet: EvidencePacket, resolver: Resolver
) -> FaithfulnessReport:
    """Re-resolve using only the packet's quotes; compare to the packet's stated
    answer (which the in-house tier computed over the full corpus)."""
    mini = _packet_as_corpus(packet)
    packet_only = resolver.resolve(packet.question, mini)
    ok = packet_only.key() == packet.resolved_answer.key()
    return FaithfulnessReport(ok=ok, full=packet.resolved_answer, packet_only=packet_only)

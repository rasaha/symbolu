#!/usr/bin/env python3
"""
Handover schema — the boundary object between the in-house hybrid tier and the
frontier quadratic-model API.

The whole point of the two-tier design is that the confidential long-context
corpus (250K+ tokens) never leaves the perimeter. What crosses the wire is a
small, grounded, redacted ``EvidencePacket`` — a few thousand tokens of
extracted spans, each carrying verbatim provenance, plus the in-house tier's
resolved answer.

These are plain data contracts. The gates that *enforce* the guarantees
(span-grounding, packet-only faithfulness, no-leak redaction) live in
``faithfulness.py`` and ``redaction.py``.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Document(BaseModel):
    """A single source document in the in-house corpus.

    ``approx_tokens`` lets a tiny fixture *declare* a realistic ingested size
    (e.g. a 40K-token amendment) without shipping 40K tokens of filler — the
    handover economics depend on corpus size, not on the demo's byte count.
    """

    doc_id: str
    citation: str  # human-facing reference, e.g. "Amendment 4 §3 p.204"
    order: int  # position in the contract stack; higher = later = governs
    text: str
    approx_tokens: int = 0


class Corpus(BaseModel):
    documents: list[Document]

    def by_id(self, doc_id: str) -> Optional[Document]:
        for d in self.documents:
            if d.doc_id == doc_id:
                return d
        return None

    def total_tokens(self) -> int:
        return sum(d.approx_tokens or (len(d.text) // 4) for d in self.documents)


class EvidenceSpan(BaseModel):
    """A verbatim extracted span with exact provenance.

    ``char_span`` is a half-open [start, end) offset into the source document's
    ``text``. The grounding gate re-slices the source at these offsets and
    asserts it equals ``quote`` — an ungrounded span never egresses.
    """

    quote: str
    doc_id: str
    citation: str
    char_span: tuple[int, int]
    confidence: float = Field(ge=0.0, le=1.0)


class ConflictResolution(BaseModel):
    """A recorded supersession — the long-range reconciliation the hybrid tier
    exists to perform (a clause 200K tokens back overridden by a later one)."""

    clause: str
    superseded: str  # citation of the overridden clause
    superseded_by: str  # citation of the governing clause
    rule: str  # why, e.g. "later amendment governs"


class ResolvedAnswer(BaseModel):
    """The in-house tier's structured verdict. Kept structured (not prose) so
    the faithfulness gate can compare two resolutions for equality."""

    termination_for_convenience: str  # "allowed" | "prohibited" | "unknown"
    notice_days: Optional[int] = None
    penalty: Optional[str] = None
    governing_citations: list[str] = Field(default_factory=list)

    def key(self) -> tuple:
        """Comparable identity used by the packet-only faithfulness check."""
        return (
            self.termination_for_convenience,
            self.notice_days,
            self.penalty,
        )


class Coverage(BaseModel):
    docs_scanned: int
    tokens_ingested: int
    spans_returned: int


class EvidencePacket(BaseModel):
    """In-house, full-fidelity handover object (contains real values).

    This is produced by the in-house tier. It is *never* egressed directly —
    ``redaction.redact()`` turns it into a ``RedactedPacket`` (real values
    swapped for placeholders) and only that crosses the boundary.
    """

    question: str
    evidence: list[EvidenceSpan]
    conflicts_resolved: list[ConflictResolution] = Field(default_factory=list)
    resolved_answer: ResolvedAnswer
    coverage: Coverage


class RedactedPacket(BaseModel):
    """What actually egresses. Structurally identical to ``EvidencePacket`` but
    every sensitive literal has been replaced by a placeholder token. Carries
    NO redaction map — the placeholder→real mapping stays in-house."""

    question: str
    evidence: list[EvidenceSpan]
    conflicts_resolved: list[ConflictResolution] = Field(default_factory=list)
    resolved_answer: ResolvedAnswer
    coverage: Coverage


class RedactionMap(BaseModel):
    """placeholder → real value. Stays inside the perimeter; used only to
    re-hydrate the frontier model's answer on the way back."""

    mapping: dict[str, str] = Field(default_factory=dict)


class HandoverAudit(BaseModel):
    escalated: bool
    corpus_tokens: int
    egress_tokens_est: int
    reduction_ratio: float
    grounded_spans: int
    masked_placeholders: list[str]
    leak_check: str  # "pass" | "blocked"
    decision: str  # SERVE_IN_HOUSE | ESCALATE | REFUSE


class HandoverResult(BaseModel):
    final_answer: str
    audit: HandoverAudit
    packet: EvidencePacket

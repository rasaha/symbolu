#!/usr/bin/env python3
"""
Metric primitives + aggregation.

The framework scores retrieval completeness, not answer fluency. The single most
important metric is the Unsafe Handover Rate: P(packet accepted | decisive
evidence missing). The architecture must fail closed — refusing an incomplete
packet is preferable to escalating it.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from agentic.hybrid_handover.schema import EvidencePacket

from .cases import PrecedenceReq, RequiredSpan


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def span_retrieved(packet: EvidencePacket, req: RequiredSpan) -> bool:
    for s in packet.evidence:
        if s.doc_id != req.doc_id:
            continue
        if req.needle == "":
            if s.quote.strip():
                return True
        elif _norm(req.needle) in _norm(s.quote):
            return True
    return False


def recall(packet: EvidencePacket, reqs: list[RequiredSpan]) -> tuple[int, int]:
    if not reqs:
        return (0, 0)
    got = sum(1 for r in reqs if span_retrieved(packet, r))
    return (got, len(reqs))


def precedence_recall(packet: EvidencePacket, reqs: list[PrecedenceReq]) -> tuple[int, int]:
    if not reqs:
        return (0, 0)
    got = 0
    for r in reqs:
        for c in packet.conflicts_resolved:
            if _norm(r.superseded) in _norm(c.superseded) and _norm(r.superseded_by) in _norm(c.superseded_by):
                got += 1
                break
    return (got, len(reqs))


def unsupported_claims(packet: EvidencePacket) -> tuple[int, int]:
    """(unsupported, total) factual claims in the resolved answer."""
    ra = packet.resolved_answer
    quotes = [_norm(s.quote) for s in packet.evidence]
    cites = {s.citation for s in packet.evidence}
    claims: list[tuple[str, bool]] = []

    if ra.termination_for_convenience in ("allowed", "prohibited"):
        claims.append(("verdict", any("terminate for convenience" in q for q in quotes)))
    if ra.notice_days is not None:
        tok = f"({ra.notice_days})"
        claims.append(("notice", any(tok in q or str(ra.notice_days) in q for q in quotes)))
    if ra.penalty:
        claims.append(("penalty", any("fee" in q or "month" in q for q in quotes)))
    for c in ra.governing_citations:
        claims.append((f"cite:{c}", c in cites))

    total = len(claims)
    unsupported = sum(1 for _, ok in claims if not ok)
    return (unsupported, total)


class Frac(BaseModel):
    num: int
    den: int

    @property
    def value(self) -> float | None:
        return (self.num / self.den) if self.den else None

    def merge(self, other: "Frac") -> "Frac":
        return Frac(num=self.num + other.num, den=self.den + other.den)


class Aggregate(BaseModel):
    n_cases: int = 0
    critical_evidence_recall: Frac = Frac(num=0, den=0)
    defeater_recall: Frac = Frac(num=0, den=0)
    definition_recall: Frac = Frac(num=0, den=0)
    precedence_recall: Frac = Frac(num=0, den=0)
    unsupported_claim: Frac = Frac(num=0, den=0)
    packet_sufficiency: Frac = Frac(num=0, den=0)   # correct-from-packet / cases
    coverage_completeness: Frac = Frac(num=0, den=0)  # coverage-ok / cases
    routing_accuracy: Frac = Frac(num=0, den=0)
    unsafe_handover: Frac = Frac(num=0, den=0)       # unsafe / (decisive-missing cases)
    fail_closed: Frac = Frac(num=0, den=0)           # refused / (should-refuse cases)

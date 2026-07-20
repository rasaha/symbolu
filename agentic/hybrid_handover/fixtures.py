#!/usr/bin/env python3
"""
Synthetic contract corpus — small on disk, but declaring a realistic ingested
size so the handover economics are demonstrable.

The needle: the MSA prohibits termination for convenience; Amendment 4 (declared
~200K tokens later) silently overrides it; Amendment 6 sets the penalty. The
correct verdict depends on reconciling a clause near the start with one near the
end — the long-range recall the in-house tier exists to perform.

``approx_tokens`` simulates the real document lengths; the actual clause text is
short so the fixture stays readable and the grounding offsets are exact.
"""

from __future__ import annotations

from .schema import Corpus, Document

# Real values that must never egress — supplied to redact() as real -> placeholder.
SECRETS: dict[str, str] = {
    "Globex Corporation": "‹VENDOR›",
    "Initech LLC": "‹CUSTOMER›",
    "$450,000": "‹PENALTY_AMT›",
}


def build_corpus() -> Corpus:
    msa = Document(
        doc_id="msa",
        citation="MSA §7.1 p.12",
        order=0,
        approx_tokens=60_000,
        text=(
            "This Master Services Agreement is between Globex Corporation and "
            "Initech LLC. The parties agree to the following terms. "
            "Neither party may terminate for convenience. "
            "Termination is permitted only for uncured material breach."
        ),
    )
    amendment_2 = Document(
        doc_id="amd2",
        citation="Amendment 2 §1 p.140",
        order=1,
        approx_tokens=45_000,
        text=(
            "Amendment 2 adjusts the service-level credits and renewal cadence. "
            "No change is made to the termination provisions of Section 7."
        ),
    )
    amendment_4 = Document(
        doc_id="amd4",
        citation="Amendment 4 §3 p.204",
        order=2,
        approx_tokens=52_000,
        text=(
            "Amendment 4 revises the termination framework. "
            "Section 7.1 is hereby deleted and replaced in its entirety: "
            "either party may terminate for convenience upon ninety (90) days "
            "prior written notice."
        ),
    )
    amendment_6 = Document(
        doc_id="amd6",
        citation="Amendment 6 §2 p.331",
        order=3,
        approx_tokens=48_000,
        text=(
            "Amendment 6 introduces an early-termination fee. "
            "Any termination for convenience shall carry a termination fee equal "
            "to three (3) months of fees, totalling $450,000."
        ),
    )
    return Corpus(documents=[msa, amendment_2, amendment_4, amendment_6])


QUESTION = (
    "Can we terminate this agreement for convenience, and what notice period "
    "and penalty apply?"
)

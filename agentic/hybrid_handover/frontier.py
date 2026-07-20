#!/usr/bin/env python3
"""
Frontier tier (Part 2) — a stand-in for the quadratic-model API.

It receives the *redacted* packet (a few thousand tokens, placeholders only) and
does the one thing the O(n) in-house tier cannot: compose a nuanced answer. The
real deployment swaps ``MockFrontierModel`` for an Anthropic / OpenAI client
call; the contract is identical — in: a ``RedactedPacket``, out: prose that
references placeholders and cites the packet's provenance.

Crucially, this tier never sees a real party name or dollar figure. It reasons
over ``‹VENDOR›`` and ``‹PENALTY_AMT›``; re-hydration happens back in-house.
"""

from __future__ import annotations

from typing import Protocol

from .schema import RedactedPacket


class FrontierModel(Protocol):
    def reason(self, packet: RedactedPacket) -> str: ...


class MockFrontierModel:
    """Deterministic template stand-in. Reads only the redacted packet."""

    def reason(self, packet: RedactedPacket) -> str:
        ra = packet.resolved_answer
        cites = "; ".join(
            f"{c.superseded_by} supersedes {c.superseded} ({c.rule})"
            for c in packet.conflicts_resolved
        ) or "no supersession recorded"
        notice = f"{ra.notice_days} days" if ra.notice_days is not None else "unspecified"
        penalty = ra.penalty or "unspecified"
        gov = ", ".join(ra.governing_citations)

        return (
            "MEMO — Termination Analysis (DRAFT, frontier-composed)\n"
            f"Question: {packet.question}\n\n"
            f"Finding: Termination for convenience is {ra.termination_for_convenience.upper()}.\n"
            f"Notice period: {notice}.\n"
            f"Early-termination penalty: {penalty}.\n"
            f"Governing clauses: {gov}.\n"
            f"Supersession: {cites}.\n\n"
            "Counterparties reasoned over as ‹VENDOR› / ‹CUSTOMER› "
            "(re-hydrated in-house).\n"
            "Residual risk: confirm no SOW-level term conflicts with the "
            "governing amendment before relying on this analysis."
        )

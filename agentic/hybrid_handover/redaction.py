#!/usr/bin/env python3
"""
Redaction gate — the sovereignty guarantee, made concrete.

Before any packet egresses to the frontier API, every sensitive literal (party
names, dollar figures, PII) is replaced by a placeholder. The frontier model
reasons over ``‹VENDOR›`` and ``‹PENALTY_AMT›``, never the real values. The
placeholder→real map stays in-house and is used only to re-hydrate the answer
on return.

``assert_no_leak`` is the hard stop: it scans the exact bytes about to egress
for any known secret and blocks the handover if one survived redaction.
"""

from __future__ import annotations

from typing import Iterable

from .schema import EvidencePacket, RedactedPacket, RedactionMap


def _replace_all(text: str, secrets: dict[str, str]) -> str:
    """Replace each real value with its placeholder. Longest-first so a value
    that is a substring of another (e.g. "Globex" ⊂ "Globex Corporation")
    doesn't get half-masked."""
    out = text
    for real in sorted(secrets, key=len, reverse=True):
        out = out.replace(real, secrets[real])
    return out


def redact(
    packet: EvidencePacket, secrets: dict[str, str]
) -> tuple[RedactedPacket, RedactionMap]:
    """Return (redacted packet for egress, in-house-only re-hydration map).

    ``secrets`` maps real value → placeholder token.
    """
    def scrub(s: str) -> str:
        return _replace_all(s, secrets)

    redacted_evidence = [
        span.model_copy(update={"quote": scrub(span.quote)})
        for span in packet.evidence
    ]
    redacted_conflicts = [
        c.model_copy(
            update={
                "superseded": scrub(c.superseded),
                "superseded_by": scrub(c.superseded_by),
            }
        )
        for c in packet.conflicts_resolved
    ]
    ra = packet.resolved_answer
    redacted_answer = ra.model_copy(
        update={
            "penalty": scrub(ra.penalty) if ra.penalty else ra.penalty,
            "governing_citations": [scrub(g) for g in ra.governing_citations],
        }
    )

    redacted = RedactedPacket(
        question=scrub(packet.question),
        evidence=redacted_evidence,
        conflicts_resolved=redacted_conflicts,
        resolved_answer=redacted_answer,
        coverage=packet.coverage,
    )
    # map is placeholder -> real (inverse of `secrets`), kept in-house
    rmap = RedactionMap(mapping={ph: real for real, ph in secrets.items()})
    return redacted, rmap


class LeakError(RuntimeError):
    """Raised when a known secret survived redaction and would have egressed."""


def assert_no_leak(egress_text: str, secrets: Iterable[str]) -> None:
    """Hard stop before egress. Raise if any real secret appears in the exact
    payload about to cross the boundary."""
    leaked = [s for s in secrets if s and s in egress_text]
    if leaked:
        raise LeakError(f"redaction incomplete; would egress secrets: {leaked!r}")


def rehydrate(text: str, rmap: RedactionMap) -> str:
    """Swap placeholders back to real values. Runs in-house, on the frontier
    model's returned answer, so the confidential re-insertion never leaves the
    perimeter."""
    out = text
    for placeholder, real in rmap.mapping.items():
        out = out.replace(placeholder, real)
    return out

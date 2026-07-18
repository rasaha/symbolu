"""Proxy evaluators for the internal policy-controller prototype.

All PROXY-ONLY (no LLM judge available offline). Transparent, rule-based:

- `flaw_score`        : fraction of a text's tokens that are flaw-markers for a
                        given flaw (speculation/escalation/filler/vagueness).
- `residual_flaw`     : the target flaw's score in the FINAL answer (lower better).
- `improvement`       : flaw_score(draft) - flaw_score(final) for the true flaw.
- `meaning_preservation`: token-overlap (Jaccard) of final vs the clean base answer.
- `directness`        : 1 - vagueness score.
"""
from __future__ import annotations

from typing import Dict

from .drafts import SPECULATIVE, ESCALATED, FILLER, VAGUE

_MARKERS = {
    "speculative": SPECULATIVE,
    "escalated": ESCALATED,
    "verbose": FILLER,
    "vague": VAGUE,
}


def flaw_score(text: str, flaw: str) -> float:
    if flaw == "none":
        return 0.0
    t = text.lower()
    markers = _MARKERS[flaw]
    hits = sum(t.count(m) for m in markers)
    n_words = max(len(t.split()), 1)
    return hits / n_words


def residual_flaw(final: str, flaw: str) -> float:
    return flaw_score(final, flaw)


def improvement(draft: str, final: str, flaw: str) -> float:
    return flaw_score(draft, flaw) - flaw_score(final, flaw)


def meaning_preservation(final: str, base: str) -> float:
    a, b = set(final.lower().split()), set(base.lower().split())
    if not b:
        return 0.0
    return len(a & b) / len(a | b)


def directness(text: str) -> float:
    return 1.0 - flaw_score(text, "vague")

"""Stage 2 — semantic extraction for free-form prose (token-set frame matching).

A concept is present if any of its token-set FRAMES matches (every prefix-token in
the frame appears in the normalized text). This is a frame/bag-of-concepts method:
paraphrase-robust because each concept has several synonym frames and matching is
by light-stemmed prefix, not exact substrings (the v1 failure mode).

Distinct in method from Stage 1 (structured parsing) and Stage 3 (surface fuzzy
similarity). Returns the set of matched concepts.
"""

from __future__ import annotations

from . import concepts
from .textnorm import frame_matches, tokens


def detect(text: str) -> set:
    toks = tokens(text)
    if not toks:
        return set()
    found = set()
    for concept, frames in concepts.FRAMES.items():
        if any(frame_matches(fr, toks) for fr in frames):
            found.add(concept)
    return found

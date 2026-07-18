"""Stage 3 — independent validator (char-trigram surface similarity).

Structurally DIFFERENT from Stage 2: instead of token-set frames, it measures
character-trigram cosine similarity between the unit text and canonical concept
exemplars. A concept is validated present if its best exemplar similarity clears a
threshold. Because it works on surface n-grams rather than lemma tokens, it does
not share Stage 2's blind spots — the two agree only when a fact is genuinely
signalled two different ways.

Threshold is set on DEV/VALIDATION (MILESTONE_PREREGISTRATION); held-out is not
used to tune it.
"""

from __future__ import annotations

from . import concepts
from .textnorm import char_trigrams, cosine

# frozen threshold (calibrated on DEV/VALIDATION only)
SIM_THRESHOLD = 0.34

_EXEMPLAR_TRIGRAMS = {c: [char_trigrams(e) for e in ex]
                      for c, ex in concepts.EXEMPLARS.items()}


def similarity(text: str, concept: str) -> float:
    tg = char_trigrams(text)
    return max((cosine(tg, ex) for ex in _EXEMPLAR_TRIGRAMS.get(concept, [])), default=0.0)


def sims(text: str) -> dict:
    """Best exemplar similarity per concept (independent surface-fuzzy evidence)."""
    if not text:
        return {}
    tg = char_trigrams(text)
    return {c: max((cosine(tg, ex) for ex in exs), default=0.0)
            for c, exs in _EXEMPLAR_TRIGRAMS.items()}


def detect(text: str, threshold: float = SIM_THRESHOLD) -> set:
    return {c for c, s in sims(text).items() if s >= threshold}

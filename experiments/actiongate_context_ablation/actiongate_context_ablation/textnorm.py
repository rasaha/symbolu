"""Deterministic text normalization + char-trigram similarity (no external deps)."""

from __future__ import annotations

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-z0-9]+")


def tokens(text: str) -> list:
    return _WORD.findall((text or "").lower())


def prefix_hit(prefix: str, toks) -> bool:
    """True if any token starts with `prefix` (light stemming via prefix match)."""
    return any(t.startswith(prefix) for t in toks)


def frame_matches(frame, toks) -> bool:
    """A frame (set of required prefixes) matches if every prefix is present."""
    return all(prefix_hit(p, toks) for p in frame)


def char_trigrams(text: str) -> Counter:
    s = "  " + re.sub(r"\s+", " ", (text or "").lower().strip()) + "  "
    return Counter(s[i:i + 3] for i in range(len(s) - 2))


def cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    dot = sum(a[k] * b[k] for k in common)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0

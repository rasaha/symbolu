"""Claim-span segmentation (Phase 9). Sentence-aware, but dependency-preserving: a sentence that
opens with a pronoun/anaphor is kept LINKED to its antecedent sentence rather than split into a
dangling fragment, and a conjunction is split only when both sides are independently evaluable AND no
shared modifier spans the boundary. Deterministic, stdlib-only.
"""
from __future__ import annotations

import re
from typing import List, Tuple


def sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


_ANAPHOR = re.compile(r"^\s*(it|they|this|that|these|those|he|she|its|their)\b", re.I)
# a modifier that, if present, must not be severed from the clause it scopes
_SPANNING = re.compile(r"\b(unless|except|only if|provided that|as of|according to)\b", re.I)


def segment(text: str) -> List[Tuple[str, bool]]:
    """Return (span_text, is_dependent) units. A dependent unit carries an unresolved anaphor that
    references a prior span; the reference resolver (references.py) fixes it before emission."""
    sents = sentences(text)
    out: List[Tuple[str, bool]] = []
    for i, s in enumerate(sents):
        dependent = bool(_ANAPHOR.match(s)) and i > 0
        out.append((s, dependent))
    return out


def splittable_conjunction(clause: str) -> bool:
    """True iff a conjunction may be split into independent claims: it contains ' and ' joining two
    clauses AND no scope-bearing modifier (unless/except/as of/according to) spans the conjunction."""
    if _SPANNING.search(clause):
        return False
    # 'but'/'or' link alternatives or contrasts that must stay together; only bare 'and' splits
    return bool(re.search(r"\w\s+and\s+\w", clause)) and " but " not in clause and " or " not in clause

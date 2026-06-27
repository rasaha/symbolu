"""Canonical label vocabularies for the Stage-1 grounding heads.

Names are the patent's controlling English terms. Mapping is lenient
(case-insensitive, spaces/hyphens -> underscore) so datasets can use natural
spellings. Unknown / missing labels map to IGNORE (-100) and are masked out of
both loss and metrics.
"""
from __future__ import annotations

from typing import Dict, List

IGNORE = -100

VRITTI: List[str] = [
    "valid_cognition", "imagination", "misperception", "inertness", "memory",
]
ASPECT: List[str] = [
    "acting", "tagging", "forming", "thinking", "directing",
    "reasoning", "purposing", "observing", "unifying", "absolute",
]
GUNA: List[str] = ["clarity_balance", "activity_desire", "inertia_stillness"]
KOSHA: List[str] = ["physical", "vital", "emotional", "intellectual", "spiritual"]

# common synonyms accepted on input
_ALIASES: Dict[str, str] = {
    "valid": "valid_cognition", "cognition": "valid_cognition",
    "pramana": "valid_cognition",
    "vikalpa": "imagination", "conceptual_construction": "imagination",
    "viparyaya": "misperception", "distortion": "misperception",
    "nidra": "inertness", "sleep": "inertness", "non_awareness": "inertness",
    "smrti": "memory", "recall": "memory",
    "meta_observing": "observing", "absolving": "absolute",
    "sattva": "clarity_balance", "rajas": "activity_desire", "tamas": "inertia_stillness",
}

CARDINALITY = {"vritti": 5, "aspect": 10, "guna": 3, "kosha": 5}
_VOCABS = {"vritti": VRITTI, "aspect": ASPECT, "guna": GUNA, "kosha": KOSHA}


def _norm(s: str) -> str:
    return str(s).strip().lower().replace("-", "_").replace(" ", "_")


def name_to_idx(head: str, name) -> int:
    """Map a label name (or already-int index) to a class index, or IGNORE."""
    if name is None:
        return IGNORE
    if isinstance(name, int):
        return name if 0 <= name < CARDINALITY[head] else IGNORE
    key = _norm(name)
    key = _ALIASES.get(key, key)
    vocab = _VOCABS[head]
    return vocab.index(key) if key in vocab else IGNORE


def idx_to_name(head: str, idx: int) -> str:
    vocab = _VOCABS[head]
    return vocab[idx] if 0 <= idx < len(vocab) else "<ignore>"

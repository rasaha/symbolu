"""Modality preservation (Phase 14). Possibility/necessity/obligation/permission/prohibition. The
critical failure is possibility->certainty (drop 'may'). Deterministic.
"""
from __future__ import annotations

import re
from typing import Dict

_MODALS = {"may": "possibility", "might": "possibility", "can": "permission",
           "could": "possibility", "must": "obligation", "shall": "obligation",
           "should": "obligation", "may not": "prohibition", "must not": "prohibition"}


def modality(text: str) -> str:
    t = text.lower()
    if re.search(r"\b(must not|may not|shall not)\b", t):
        return "prohibition"
    for w, m in _MODALS.items():
        if re.search(rf"\b{w}\b", t):
            return m
    return "none"


def preserved(gold_text: str, produced_text: str) -> bool:
    return modality(gold_text) == modality(produced_text)


def possibility_to_certainty(gold_text: str, produced_text: str) -> bool:
    return modality(gold_text) in ("possibility", "permission") and modality(produced_text) == "none"

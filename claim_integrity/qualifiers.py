"""Qualifier preservation (Phase 13). Detects whether a hedge/frequency qualifier survived and whether
its loss is MATERIAL (risk-tier dependent). Deterministic.
"""
from __future__ import annotations

import re
from typing import Any, Dict

QUALIFIERS = ("may", "might", "can", "generally", "sometimes", "typically", "often", "in some cases",
              "approximately", "at least", "at most", "no more than", "likely", "based on limited evidence",
              "not yet established", "not approved", "not recommended")


def has_qualifier(text: str) -> bool:
    t = text.lower()
    return any(re.search(rf"\b{re.escape(q)}\b", t) for q in QUALIFIERS)


def preserved(gold_text: str, produced_text: str) -> bool:
    return has_qualifier(gold_text) == has_qualifier(produced_text)


def material_loss(gold_text: str, produced_text: str, risk_class: str) -> bool:
    """Qualifier dropped, and it matters: any loss is material in high/critical risk; in low risk,
    only a strong hedge (approval/recommendation/evidence status) is material."""
    if has_qualifier(gold_text) and not has_qualifier(produced_text):
        if risk_class in ("high", "critical"):
            return True
        strong = ("not approved", "not recommended", "not yet established", "based on limited evidence")
        return any(s in gold_text.lower() for s in strong)
    return False

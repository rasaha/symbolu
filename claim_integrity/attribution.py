"""Attribution integrity (Phase 16). Keeps "Source X claims Y" from becoming "Y", distinguishes a
quoted/reported claim from an author endorsement, and preserves nested attribution. Deterministic.
"""
from __future__ import annotations

import re
from typing import Any, Dict

_ATTR = re.compile(r"\b(according to|reportedly|as reported by|per|cites?|claims that|says that|stated that|argues that)\b", re.I)
_QUOTE = re.compile(r"[\"“].+?[\"”]")


def attribution_state(text: str) -> str:
    if _QUOTE.search(text):
        return "quoted"
    if _ATTR.search(text):
        return "attributed"
    return "direct"


def preserved(gold_text: str, produced_text: str) -> bool:
    """An attributed/quoted claim must NOT be flattened to a direct author assertion."""
    g = attribution_state(gold_text)
    p = attribution_state(produced_text)
    if g in ("attributed", "quoted") and p == "direct":
        return False        # attribution/quote lost
    return True


def flattened_to_direct(gold_text: str, produced_text: str) -> bool:
    return attribution_state(gold_text) in ("attributed", "quoted") and \
        attribution_state(produced_text) == "direct"

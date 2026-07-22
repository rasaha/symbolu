"""Deterministic jurisdiction resolution."""
from __future__ import annotations
from typing import Mapping, Tuple

_GLOBAL = ("global", "any", "worldwide", "")


def matches(cand_jurisdiction: str, situation: Mapping[str, str]) -> Tuple[bool, float]:
    sj = (situation.get("jurisdiction") or "").lower()
    cj = (cand_jurisdiction or "").lower()
    if cj in _GLOBAL:
        return True, 0.9                    # applies broadly
    if not sj:
        return True, 0.4                    # situation jurisdiction unknown -> low confidence
    return (cj == sj), 1.0

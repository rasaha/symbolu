"""Deterministic scope matching (people/systems/products/environments/…)."""
from __future__ import annotations
from typing import Mapping, Tuple

_BROAD = ("all", "any", "everyone", "staff", "")


def matches(cand_role: str, cand_env: str, situation: Mapping[str, str]) -> Tuple[bool, float]:
    conf = 1.0
    sr = (situation.get("user_role") or "").lower()
    cr = (cand_role or "").lower()
    if cr not in _BROAD:
        if not sr:
            return True, 0.4
        if cr != sr:
            return False, 1.0
    se = (situation.get("environment") or "").lower()
    ce = (cand_env or "").lower()
    if ce and se and ce != se:
        return False, 1.0
    if cr in _BROAD and not cand_env:
        conf = 0.8                          # broad scope -> slightly less specific
    return True, conf


def specificity(cand_role: str, cand_env: str) -> int:
    s = 0
    if cand_role and cand_role.lower() not in _BROAD:
        s += 2
    if cand_env:
        s += 1
    return s

"""Numeric & temporal integrity (Phase 15). Values, ranges, percentages, units, bounds, dates,
time-windows, as-of clauses. Detects deletion, substitution, unit loss, range narrowing/broadening,
bound loss, and stale-time normalization. Deterministic.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

_NUM = re.compile(r"\d+(?:\.\d+)?")
_RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-|–|and)\s*(\d+(?:\.\d+)?)")
_UNIT = re.compile(r"\b(percent|%|mg|kg|ml|mmhg|mg/kg|bp|usd|dollars|years?|days?|months?|hours?)\b", re.I)
_BOUND = re.compile(r"\b(at least|at most|no more than|up to|minimum|maximum|greater than|less than)\b", re.I)
_ASOF = re.compile(r"\b(as of \d{4}|in \d{4}|before \d{4}|after \d{4})\b", re.I)


def numbers(text: str) -> List[str]:
    return _NUM.findall(text)


def ranges(text: str):
    return [(m.group(1), m.group(2)) for m in _RANGE.finditer(text)]


def units(text: str) -> List[str]:
    return [u.lower() for u in _UNIT.findall(text)]


def profile(text: str) -> Dict[str, Any]:
    return {"numbers": numbers(text), "ranges": ranges(text), "units": units(text),
            "has_bound": bool(_BOUND.search(text)), "as_of": bool(_ASOF.search(text))}


def check(gold_text: str, produced_text: str) -> Dict[str, Any]:
    g, p = profile(gold_text), profile(produced_text)
    codes = []
    if set(g["numbers"]) - set(p["numbers"]):
        # a gold number vanished or changed
        if p["numbers"] and set(p["numbers"]) - set(g["numbers"]):
            codes.append("numeric_alteration")
        elif g["ranges"] and not p["ranges"]:
            codes.append("range_to_point")
        else:
            codes.append("number_deletion")
    if g["units"] and not p["units"]:
        codes.append("unit_loss")
    if g["ranges"] and not p["ranges"] and not any("range" in c for c in codes):
        codes.append("range_to_point")
    if g["has_bound"] and not p["has_bound"]:
        codes.append("bound_loss")
    if g["as_of"] and not p["as_of"]:
        codes.append("stale_time_normalization")
    return {"preserved": not codes, "codes": codes}

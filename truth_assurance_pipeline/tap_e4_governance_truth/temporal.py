"""Deterministic temporal applicability (explicit date comparison)."""
from __future__ import annotations
import re
from typing import Optional, Tuple

from truth_assurance_pipeline.tap_e3_relationship_truth.schema import Temporality


def _year(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    m = re.search(r"(19|20)\d{2}", s)
    return int(m.group(0)) if m else None


def status(temporality: str, valid_from: Optional[str], valid_until: Optional[str],
           superseded: bool, situation_year: Optional[int]) -> Tuple[str, float]:
    """Return (status, confidence). status in
    EFFECTIVE / EXPIRED / FUTURE / HISTORICAL / SUPERSEDED / UNKNOWN."""
    if superseded or temporality == Temporality.SUPERSEDED.value:
        return "SUPERSEDED", 1.0
    if temporality == Temporality.HISTORICAL.value:
        return "HISTORICAL", 1.0
    vf, vu = _year(valid_from), _year(valid_until)
    if situation_year is None:
        # no situation date; only obvious FUTURE/expired flags apply
        if temporality == Temporality.FUTURE.value:
            return "FUTURE", 0.6
        return ("EFFECTIVE", 0.4) if (vf is None and vu is None) else ("EFFECTIVE", 0.5)
    if vf is not None and situation_year < vf:
        return "FUTURE", 1.0
    if vu is not None and situation_year > vu:
        return "EXPIRED", 1.0
    if temporality == Temporality.FUTURE.value and vf is None:
        return "FUTURE", 0.7
    return "EFFECTIVE", 1.0

"""
Deterministic modality detection. `may` is never treated as equivalent to `must`.

Attribution predicates (ALLEGES/CLAIMS/REPORTS) set the INNER relationship's modality to
ALLEGED — handled by the extractor, which passes attribution=True.
"""

from __future__ import annotations

import re

from truth_assurance_pipeline.tap_e3_relationship_truth.schema import Modality

_CUES = (
    (r"\bmust\b", Modality.REQUIRED),
    (r"\bshall\b", Modality.REQUIRED),
    (r"\bis required to\b", Modality.REQUIRED),
    (r"\bare required to\b", Modality.REQUIRED),
    (r"\brequired to\b", Modality.REQUIRED),
    (r"\bobligated to\b", Modality.REQUIRED),
    (r"\bmay\b", Modality.PERMITTED),
    (r"\bis permitted to\b", Modality.PERMITTED),
    (r"\bpermitted to\b", Modality.PERMITTED),
    (r"\bis authorized to\b", Modality.PERMITTED),
    (r"\bauthorized to\b", Modality.PERMITTED),
    (r"\bshould\b", Modality.RECOMMENDED),
    (r"\brecommend", Modality.RECOMMENDED),
    (r"\bis expected to\b", Modality.RECOMMENDED),
    (r"\bcan\b", Modality.POSSIBLE),
    (r"\bcould\b", Modality.POSSIBLE),
)


def detect_modality(clause: str, attribution: bool = False,
                    has_condition: bool = False) -> Modality:
    if attribution:
        return Modality.ALLEGED
    low = clause.lower()
    for pat, mod in _CUES:
        if re.search(pat, low):
            return mod
    if has_condition:
        return Modality.CONDITIONAL
    return Modality.ASSERTED

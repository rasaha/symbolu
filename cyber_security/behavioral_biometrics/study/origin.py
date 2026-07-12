"""Data-origin claim locks for the study machinery.

Every scientific-verdict function routes through here. On non-real data (SYNTHETIC /
MOCK / DEMO) it is IMPOSSIBLE to emit a positive scientific verdict — only
PIPELINE_EXECUTED / ALGORITHM_PATH_VERIFIED / *_NO_SCIENTIFIC_VERDICT are allowed. The
pure classifier functions (``classify_*``) operate on measured numbers and are unit
-testable; the guarded wrappers apply the origin lock around them.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from cyber_security.behavioral_biometrics.version import (
    ORIGIN_DEMO,
    ORIGIN_MOCK,
    ORIGIN_REAL,
    ORIGIN_SYNTHETIC,
)

BANNER = "TEST DATA ONLY — NO BIOMETRIC CLAIM"

# non-real allowed outcomes (never a scientific verdict)
PIPELINE_EXECUTED = "PIPELINE_EXECUTED"
ALGORITHM_PATH_VERIFIED = "ALGORITHM_PATH_VERIFIED"
SYNTHETIC_NO_SCIENTIFIC_VERDICT = "SYNTHETIC_NO_SCIENTIFIC_VERDICT"
MOCK_NO_SCIENTIFIC_VERDICT = "MOCK_NO_SCIENTIFIC_VERDICT"
DEMO_NO_SCIENTIFIC_VERDICT = "DEMO_NO_SCIENTIFIC_VERDICT"

_NON_REAL = {ORIGIN_SYNTHETIC, ORIGIN_MOCK, ORIGIN_DEMO}

# Positive scientific verdicts that non-real data must NEVER produce.
POSITIVE_SCIENTIFIC = {
    "MARGINAL_SIGNAL_SUPPORTED", "USER_SPECIFIC_COUPLING_SUPPORTED",
    "BCVF_INCREMENTAL_VALUE_SUPPORTED", "FUSION_SUPPORTED", "CONFIDENCE_CALIBRATED",
}


def origin_of(record_or_meta: Dict[str, Any]) -> str:
    meta = record_or_meta.get("meta", record_or_meta)
    o = meta.get("data_origin")
    if o in (ORIGIN_REAL, ORIGIN_SYNTHETIC, ORIGIN_MOCK, ORIGIN_DEMO):
        return o
    # legacy fallback
    return ORIGIN_REAL if meta.get("data_provenance") == "REAL" else ORIGIN_SYNTHETIC


def cohort_origin(records: List[Dict[str, Any]]) -> str:
    """Most restrictive origin present: any non-real origin makes the cohort non-real."""
    origins = {origin_of(r) for r in records}
    if not origins or origins == {ORIGIN_REAL}:
        return ORIGIN_REAL
    for o in (ORIGIN_MOCK, ORIGIN_SYNTHETIC, ORIGIN_DEMO):  # priority order for labeling
        if o in origins:
            return o
    return ORIGIN_REAL


def is_real(records: List[Dict[str, Any]]) -> bool:
    return bool(records) and cohort_origin(records) == ORIGIN_REAL


def no_verdict_label(origin: str) -> str:
    return {ORIGIN_MOCK: MOCK_NO_SCIENTIFIC_VERDICT,
            ORIGIN_SYNTHETIC: SYNTHETIC_NO_SCIENTIFIC_VERDICT,
            ORIGIN_DEMO: DEMO_NO_SCIENTIFIC_VERDICT}.get(origin, MOCK_NO_SCIENTIFIC_VERDICT)


def claim_lock(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    origin = cohort_origin(records)
    if origin == ORIGIN_REAL:
        return {"locked": False, "origin": origin, "banner": None,
                "allowed_outcomes": ["<scientific verdicts permitted on eligible real data>"]}
    return {"locked": True, "origin": origin, "banner": BANNER,
            "allowed_outcomes": [PIPELINE_EXECUTED, ALGORITHM_PATH_VERIFIED,
                                 no_verdict_label(origin)]}


def guarded(records: List[Dict[str, Any]], *, scientific: Callable[[], str],
            path_verified: str, eligible: bool = True) -> Dict[str, Any]:
    """Return the origin-appropriate verdict. On non-real data, emit the
    ``*_PATH_VERIFIED`` test outcome (the algorithm path ran) or the no-verdict label —
    never a scientific claim. On real data, run the scientific classifier."""
    origin = cohort_origin(records)
    if origin != ORIGIN_REAL:
        return {"verdict": path_verified if eligible else no_verdict_label(origin),
                "scientific": False, "origin": origin, "banner": BANNER,
                "test_outcome": path_verified, "note": "non-real data: no scientific verdict"}
    v = scientific()
    return {"verdict": v, "scientific": True, "origin": origin, "banner": None}


def assert_not_positive_on_nonreal(records: List[Dict[str, Any]], verdict: str) -> None:
    """Defensive tripwire: a positive scientific verdict on non-real data is a bug."""
    if verdict in POSITIVE_SCIENTIFIC and cohort_origin(records) != ORIGIN_REAL:
        raise AssertionError(
            f"illegal positive scientific verdict {verdict!r} on non-real data")

"""Phase 10 - Review metrics.

Computes the human-validation endpoints from real reviewer records. With no real reviewer records the
functions return status NOT_ENOUGH_HUMAN_EVIDENCE - they never synthesize agreement from rubrics.

A "record" here is a reviewer_calibration_pilot.review_interface.ReviewRecord paired with the system
result. Deterministic aggregation only; the judgments are human.
"""
from __future__ import annotations

from typing import Any, Dict, List

# obligation ordering (for stricter/more-permissive direction and safety comparisons)
_ORDER = {"E0_NO_FACTUAL_EVIDENCE_GATE": 0, "E1_CONTEXTUAL_SUPPORT": 1,
          "E2_AUTHORITATIVE_INTERNAL_OR_IMPLEMENTATION_EVIDENCE": 2,
          "E3_INDEPENDENT_OR_MEASURED_EVIDENCE": 3, "E4_EXTERNAL_AUTHORITATIVE_EVIDENCE_AND_REVIEW": 4,
          "ER_HUMAN_REVIEW_OR_INDETERMINATE": 5}


def _rank(o: str) -> int:
    return _ORDER.get(o, 0)


def compute(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """records: [{reviewer_id, artifact_id, is_mock, stage_a_obligation, stage_b_obligation,
    system_obligation, agreement, override, override_direction, review_time, confidence,
    explanation_usefulness, unsafe_allow_flagged, source_authority_agree, ...}].

    Mock records are EXCLUDED - they are never human validation. If no non-mock human records remain,
    returns NOT_ENOUGH_HUMAN_EVIDENCE."""
    human = [r for r in records if not r.get("is_mock", False)]
    n = len(human)
    if n == 0:
        return {"status": "NOT_ENOUGH_HUMAN_EVIDENCE", "human_records": 0,
                "note": "no real reviewer records; metrics not computed (mock records excluded)"}

    def rate(key):
        vals = [r[key] for r in human if r.get(key) is not None]
        return round(sum(bool(v) for v in vals) / len(vals), 4) if vals else None

    stricter = sum(1 for r in human if r.get("override") and r.get("override_direction") == "stricter")
    looser = sum(1 for r in human if r.get("override") and r.get("override_direction") == "more_permissive")
    overrides = sum(1 for r in human if r.get("override"))
    times = [r["review_time"] for r in human if r.get("review_time") is not None]
    times.sort()

    return {
        "status": "COMPUTED",
        "human_records": n,
        # primary human-validation endpoints
        "acceptable_obligation_agreement": rate("acceptable_agree"),
        "unsafe_allow_disagreement": sum(1 for r in human if r.get("unsafe_allow_flagged")),
        "high_risk_unsafe_allow_disagreement": sum(1 for r in human
                                                   if r.get("unsafe_allow_flagged") and r.get("high_risk")),
        "source_authority_agreement": rate("source_authority_agree"),
        "clean_allow_agreement": rate("clean_allow_agree"),
        # secondary
        "exact_obligation_agreement": rate("exact_agree"),
        "risk_agreement": rate("risk_agree"),
        "evidence_satisfaction_agreement": rate("evidence_satisfaction_agree"),
        "qualification_agreement": rate("qualification_agree"),
        "review_required_agreement": rate("review_required_agree"),
        "native_actiongate_agreement": rate("actiongate_agree"),
        "blinded_agreement": rate("blinded_agree"),
        "post_reveal_agreement": rate("agreement"),
        "override_rate": round(overrides / n, 4),
        "stricter_override_rate": round(stricter / n, 4),
        "more_permissive_override_rate": round(looser / n, 4),
        "median_review_time": times[len(times) // 2] if times else None,
        "p90_review_time": times[min(len(times) - 1, int(0.9 * (len(times) - 1)))] if times else None,
        "mean_confidence": round(sum(r.get("confidence", 0) for r in human) / n, 4),
        "explanation_usefulness_mean": round(
            sum(r.get("explanation_usefulness", 0) for r in human) / n, 4),
        # operational
        "adjudication_rate": rate("needs_adjudication"),
        "unresolved_rate": rate("unresolved"),
    }

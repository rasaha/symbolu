"""Phase 15 - Review metrics + disagreement taxonomy.

Computes metrics OVER REAL REVIEWER RECORDS only. This module is the guardrail against overclaiming:

  * Records flagged `is_mock=True` are EXCLUDED from every real metric. If, after exclusion, no real
    reviewer records remain, every human-dependent metric is reported as NOT_EVALUATED with status
    NOT_ENOUGH_HUMAN_EVIDENCE. The module NEVER fabricates agreement, and NEVER labels simulated output as
    human validation.
  * "Agreement" here means agreement between reviewers, or between a reviewer and the frozen system
    result. It is a description of reviewer behaviour, not a claim that the system is correct.

Disagreement taxonomy (per pair/artifact): OBLIGATION_LEVEL, SAFETY_DIRECTION (one stricter vs one
permissive), TRAP_MISS (a trap seen by some, missed by others), ACTIONGATE_INTERPRETATION,
GENUINE_AMBIGUITY (irreducible - recorded, not forced). Deterministic, stdlib-only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot.qualification import short_level

NOT_EVALUATED = "NOT_EVALUATED"
STATUS_NO_HUMAN = "NOT_ENOUGH_HUMAN_EVIDENCE"
STATUS_OK = "COMPUTED_FROM_REAL_REVIEWERS"

_ORDER = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "ER": 5}


def _real(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep only real (non-mock) records that completed both stages."""
    return [r for r in records if not r.get("is_mock")
            and r.get("stage_a") is not None and r.get("stage_b") is not None]


def _classify_disagreement(labels_a: List[str], traps_seen: List[bool],
                           actiongate: List[str], ambiguous: List[bool]) -> str:
    levels = {short_level(x) for x in labels_a if x}
    if len(levels) <= 1:
        if len(set(actiongate)) > 1:
            return "ACTIONGATE_INTERPRETATION"
        if any(ambiguous):
            return "GENUINE_AMBIGUITY"
        return "NONE"
    if any(traps_seen) and not all(traps_seen):
        return "TRAP_MISS"
    ranks = sorted(_ORDER.get(l, 99) for l in levels)
    if ranks[-1] - ranks[0] >= 2:
        return "SAFETY_DIRECTION"
    if any(ambiguous):
        return "GENUINE_AMBIGUITY"
    return "OBLIGATION_LEVEL"


def compute(records: List[Dict[str, Any]],
            system_results: Optional[Dict[str, Dict[str, Any]]] = None) -> Dict[str, Any]:
    """`records`: reviewer records (as ReviewRecord.as_dict()). `system_results`: artifact_id -> result."""
    system_results = system_results or {}
    real = _real(records)
    n_mock_excluded = sum(1 for r in records if r.get("is_mock"))

    if not real:
        return {
            "status": STATUS_NO_HUMAN,
            "human_validation": NOT_EVALUATED,
            "real_records": 0, "mock_records_excluded": n_mock_excluded,
            "reviewer_reviewer_agreement": NOT_EVALUATED,
            "reviewer_system_agreement": NOT_EVALUATED,
            "trap_catch_rate": NOT_EVALUATED,
            "override_rate": NOT_EVALUATED,
            "disagreement_taxonomy": NOT_EVALUATED,
            "note": "No real reviewer records. Metrics that depend on humans are NOT EVALUATED. "
                    "Simulated workflow output is never counted here.",
        }

    # group real records by artifact
    by_art: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in real:
        by_art[r["artifact_id"]].append(r)

    rr_agree_num = rr_agree_den = 0
    rs_agree_num = rs_agree_den = 0
    trap_catch_num = trap_catch_den = 0
    override_num = override_den = 0
    taxonomy: Counter = Counter()

    for aid, recs in by_art.items():
        a_levels = [short_level(r["stage_a"].get("obligation")) for r in recs]
        traps = [r["stage_a"].get("trap_detected", "none") != "none" for r in recs]
        ag_outcomes = [r["stage_b"].get("acceptable_actiongate_outcome", "not_applicable") for r in recs]
        ambiguous = [r["stage_b"].get("missing_context") is True for r in recs]

        # reviewer-reviewer agreement (pairwise on Stage A obligation)
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                rr_agree_den += 1
                if a_levels[i] == a_levels[j]:
                    rr_agree_num += 1
        if len(recs) >= 2:
            tax = _classify_disagreement(a_levels, traps, ag_outcomes, ambiguous)
            if tax != "NONE":
                taxonomy[tax] += 1

        # reviewer-system agreement (Stage B agreement flag, or level match)
        sysr = system_results.get(aid)
        for r in recs:
            if sysr is not None:
                rs_agree_den += 1
                if r["stage_b"].get("agreement") is True:
                    rs_agree_num += 1
            override_den += 1
            if r["stage_b"].get("override") is True:
                override_num += 1

        # trap catch: measured only for artifacts whose system result declares an expected trap.
        expected_trap = (sysr or {}).get("expected_trap")
        if expected_trap:
            for r in recs:
                trap_catch_den += 1
                if r["stage_a"].get("trap_detected") == expected_trap:
                    trap_catch_num += 1

    def _rate(n, d):
        return (n / d) if d else NOT_EVALUATED

    return {
        "status": STATUS_OK,
        "human_validation": "OBSERVED_BUT_NOT_A_CORRECTNESS_CLAIM",
        "real_records": len(real), "mock_records_excluded": n_mock_excluded,
        "artifacts_reviewed": len(by_art),
        "reviewer_reviewer_agreement": _rate(rr_agree_num, rr_agree_den),
        "reviewer_system_agreement": _rate(rs_agree_num, rs_agree_den),
        "trap_catch_rate": _rate(trap_catch_num, trap_catch_den),
        "override_rate": _rate(override_num, override_den),
        "disagreement_taxonomy": dict(sorted(taxonomy.items())),
        "note": "Agreement describes reviewer behaviour; it is NOT a claim that the frozen policy is "
                "correct. Human validation of policy correctness remains a separate, unmade claim.",
    }

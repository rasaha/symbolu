"""
TAP-E4 governance metrics + independent critical-failure detection.

Every metric is reported separately (never one aggregate score). Critical governance
failures — selecting an expired/superseded/draft/wrong-jurisdiction authority, ignoring an
exception or a customer override, a policy overriding a law, missing provenance, an ignored
upstream gap, or an ungrounded decision — are counted INDEPENDENTLY of the pass/fail
metrics, so a high average can never mask a safety-critical error.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from truth_assurance_pipeline.tap_e4_governance_truth.schema import (
    GovGapCode, GovStatus, GovernanceRecord,
)

# families grouped by the governance dimension they exercise
_JURISDICTION_FAM = {"jurisdiction", "no_governing"}
_SCOPE_FAM = {"scope"}
_TEMPORAL_FAM = {"expired", "superseded", "future"}
_VERSION_FAM = {"version"}
_EXCEPTION_FAM = {"exception"}
_PRECEDENCE_FAM = {"customer_override", "emergency_override", "law_supremacy", "draft"}

# every critical-failure class is safety-severe for governance
CRITICAL_CLASSES = (
    "EXPIRED_POLICY_SELECTED", "SUPERSEDED_POLICY_SELECTED", "DRAFT_SELECTED",
    "WRONG_JURISDICTION", "EXCEPTION_IGNORED", "CUSTOMER_OVERRIDE_IGNORED",
    "LAW_OVERRIDDEN_BY_POLICY", "MISSING_PROVENANCE", "UPSTREAM_GAP_IGNORED",
    "UNSUPPORTED_GOVERNANCE_DECISION",
)


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    family: str
    governing_correct: bool
    jurisdiction_correct: Optional[bool]
    scope_correct: Optional[bool]
    temporal_correct: Optional[bool]
    version_correct: Optional[bool]
    exception_correct: Optional[bool]
    precedence_correct: Optional[bool]
    conflict_expected: bool
    conflict_detected: bool
    gap_correct: bool
    provenance_complete: bool
    unsupported: bool
    incorrect_override: bool
    expired_selected: bool
    criticals: Tuple[str, ...]


def _selected(rec: GovernanceRecord):
    d = rec.governing_authorities[0] if rec.governing_authorities else None
    return d


def _emitted_gap_codes(rec: GovernanceRecord) -> set:
    return {g.gap_code for g in rec.governance_gaps}


def score_case(case, rec: GovernanceRecord) -> CaseScore:
    d = _selected(rec)
    sel = d.selected_authority if d else None
    status = d.status if d else GovStatus.UNRESOLVED
    gold = case.expected_authority
    fam = case.family

    governing_correct = (sel == gold)

    # --- per-dimension correctness (only on the families that exercise them) --
    jurisdiction_correct = governing_correct if fam in _JURISDICTION_FAM else None
    scope_correct = governing_correct if fam in _SCOPE_FAM else None
    temporal_correct = governing_correct if fam in _TEMPORAL_FAM else None
    version_correct = governing_correct if fam in _VERSION_FAM else None
    precedence_correct = governing_correct if fam in _PRECEDENCE_FAM else None
    exception_correct = None
    if fam in _EXCEPTION_FAM:
        exception_correct = (status == GovStatus.GOVERNING_WITH_EXCEPTION and sel is None)

    # --- conflict ------------------------------------------------------------
    conflict_expected = case.expected_conflicts > 0
    conflict_detected = len(rec.governance_conflicts) > 0

    # --- gaps ----------------------------------------------------------------
    emitted = _emitted_gap_codes(rec)
    expected_gaps = set(case.expected_gaps)
    if expected_gaps:
        gap_correct = expected_gaps.issubset(emitted)
    else:
        # a clean case must not fabricate a decision-blocking gap
        blocking = {GovGapCode.NO_GOVERNING_POLICY, GovGapCode.CONFLICTING_AUTHORITIES}
        gap_correct = not (emitted & blocking)

    # --- provenance ----------------------------------------------------------
    provenance_complete = True
    if sel is not None:
        provenance_complete = bool(d.provenance) and all(p.is_complete() for p in d.provenance)

    # --- critical failures (independent) -------------------------------------
    criticals: List[str] = []
    if sel is not None:
        if sel in case.disqualified("expired"):
            criticals.append("EXPIRED_POLICY_SELECTED")
        if sel in case.disqualified("superseded"):
            criticals.append("SUPERSEDED_POLICY_SELECTED")
        if sel in case.disqualified("draft"):
            criticals.append("DRAFT_SELECTED")
        if sel in case.disqualified("wrong_jurisdiction"):
            criticals.append("WRONG_JURISDICTION")
        if not provenance_complete:
            criticals.append("MISSING_PROVENANCE")
        if not d.supporting_relationships:
            criticals.append("UNSUPPORTED_GOVERNANCE_DECISION")

    if fam in _EXCEPTION_FAM and case.exemptions:
        if not (status == GovStatus.GOVERNING_WITH_EXCEPTION and sel is None):
            criticals.append("EXCEPTION_IGNORED")

    gold_spec = case.gold_spec()
    if fam == "customer_override" and gold is not None and sel != gold:
        criticals.append("CUSTOMER_OVERRIDE_IGNORED")
    if (gold_spec is not None and gold_spec.kind[2] in ("law", "regulation")
            and sel is not None and sel != gold):
        criticals.append("LAW_OVERRIDDEN_BY_POLICY")

    if case.upstream_gaps and GovGapCode.INSUFFICIENT_UPSTREAM_RELATIONSHIPS not in emitted:
        criticals.append("UPSTREAM_GAP_IGNORED")

    incorrect_override = ("CUSTOMER_OVERRIDE_IGNORED" in criticals
                          or "LAW_OVERRIDDEN_BY_POLICY" in criticals)
    expired_selected = "EXPIRED_POLICY_SELECTED" in criticals

    return CaseScore(
        case_id=case.case_id, family=fam, governing_correct=governing_correct,
        jurisdiction_correct=jurisdiction_correct, scope_correct=scope_correct,
        temporal_correct=temporal_correct, version_correct=version_correct,
        exception_correct=exception_correct, precedence_correct=precedence_correct,
        conflict_expected=conflict_expected, conflict_detected=conflict_detected,
        gap_correct=gap_correct, provenance_complete=provenance_complete,
        unsupported=("UNSUPPORTED_GOVERNANCE_DECISION" in criticals),
        incorrect_override=incorrect_override, expired_selected=expired_selected,
        criticals=tuple(criticals))


def _dim_acc(scores: Sequence[CaseScore], attr: str) -> float:
    vals = [1.0 if getattr(s, attr) else 0.0 for s in scores if getattr(s, attr) is not None]
    return sum(vals) / len(vals) if vals else 1.0


def _f1(scores: Sequence[CaseScore]) -> float:
    tp = sum(1 for s in scores if s.conflict_expected and s.conflict_detected)
    fp = sum(1 for s in scores if not s.conflict_expected and s.conflict_detected)
    fn = sum(1 for s in scores if s.conflict_expected and not s.conflict_detected)
    if tp == 0 and fp == 0 and fn == 0:
        return 1.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    return 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0


def aggregate(scores: Sequence[CaseScore]) -> Dict[str, object]:
    n = len(scores) or 1
    crit_counts: Dict[str, int] = {c: 0 for c in CRITICAL_CLASSES}
    for s in scores:
        for c in s.criticals:
            crit_counts[c] = crit_counts.get(c, 0) + 1
    severe = sum(crit_counts.values())
    return {
        "n_cases": len(scores),
        "governing_authority_accuracy": _dim_acc(scores, "governing_correct"),
        "jurisdiction_accuracy": _dim_acc(scores, "jurisdiction_correct"),
        "scope_accuracy": _dim_acc(scores, "scope_correct"),
        "temporal_accuracy": _dim_acc(scores, "temporal_correct"),
        "version_accuracy": _dim_acc(scores, "version_correct"),
        "exception_accuracy": _dim_acc(scores, "exception_correct"),
        "precedence_accuracy": _dim_acc(scores, "precedence_correct"),
        "governance_conflict_f1": _f1(scores),
        "governance_gap_accuracy": _dim_acc(scores, "gap_correct"),
        "provenance_completeness": _dim_acc(scores, "provenance_complete"),
        "unsupported_governance_rate": sum(1 for s in scores if s.unsupported) / n,
        "incorrect_override_rate": sum(1 for s in scores if s.incorrect_override) / n,
        "expired_policy_selection_rate": sum(1 for s in scores if s.expired_selected) / n,
        "critical_failures": crit_counts,
        "severe_critical_failure_count": float(severe),
    }

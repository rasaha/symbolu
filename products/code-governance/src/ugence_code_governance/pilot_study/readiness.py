"""Enforcement-readiness assessment.

A deterministic decision framework, NOT an automatic enforcement switch. No verdict
enables execution. Safety/integrity failures dominate; a pilot with no live
evidence is `INSUFFICIENT_LIVE_EVIDENCE`; recurring policy disagreement is
`PILOT_CALIBRATION_REQUIRED`; no demonstrated incremental value is
`PRODUCT_VALUE_NOT_PROVEN`. There is no single numerical score.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ..fingerprints import domain_hash
from .adverse import PilotAdverseCase
from .vocab import AdverseCaseKind, PilotReadinessVerdict

DOMAIN_READINESS = "cg.pilot_study.readiness.v1"

_SAFETY_ADVERSE = frozenset({
    AdverseCaseKind.INTEGRITY_ANOMALY,
    AdverseCaseKind.CREDENTIAL_OR_BOUNDARY_CONCERN,
})


@dataclass(frozen=True)
class PilotReadinessAssessment:
    verdict: PilotReadinessVerdict
    reasons: Tuple[str, ...]
    evidence_refs: Tuple[str, ...]
    limitations: Tuple[str, ...]
    execution_status: str = "DISABLED"

    @property
    def assessment_fingerprint(self) -> str:
        return domain_hash(DOMAIN_READINESS, {
            "verdict": self.verdict.value, "reasons": sorted(self.reasons),
            "evidence_refs": sorted(self.evidence_refs), "limitations": sorted(self.limitations),
            "execution_status": self.execution_status})

    @property
    def record_id(self) -> str:
        return f"pilot-readiness:{self.verdict.value}:{self.assessment_fingerprint[:16]}"


def assess_enforcement_readiness(
    *,
    pilot_id: str,
    adverse_cases: List[PilotAdverseCase],
    credential_leaks: int = 0,
    write_boundary_violations: int = 0,
    integrity_failures: int = 0,
    audit_reconstruction_complete: bool = True,
    reviewer_feedback_coverage: float = 0.0,
    minimum_feedback_coverage: float = 0.5,
    live_evaluation_count: int = 0,
    incremental_value_demonstrated: bool = False,
    unresolved_policy_defects: int = 0,
    limitations: Tuple[str, ...] = (),
) -> PilotReadinessAssessment:
    """Produce a deterministic enforcement-readiness verdict (never enables execution)."""
    reasons: List[str] = []
    refs = tuple(sorted(c.record_id for c in adverse_cases))
    unresolved_serious_false_clear = [
        c for c in adverse_cases
        if c.kind is AdverseCaseKind.POSSIBLE_FALSE_CLEAR and c.serious and not c.resolved]
    unresolved_safety = [
        c for c in adverse_cases if c.kind in _SAFETY_ADVERSE and not c.resolved]

    # 1. Safety / integrity dominates.
    if credential_leaks > 0 or write_boundary_violations > 0 or integrity_failures > 0 \
            or unresolved_safety or not audit_reconstruction_complete:
        if credential_leaks:
            reasons.append(f"credential_leaks={credential_leaks}")
        if write_boundary_violations:
            reasons.append(f"write_boundary_violations={write_boundary_violations}")
        if integrity_failures:
            reasons.append(f"integrity_failures={integrity_failures}")
        if unresolved_safety:
            reasons.append(f"unresolved_safety_adverse_cases={len(unresolved_safety)}")
        if not audit_reconstruction_complete:
            reasons.append("audit_reconstruction_incomplete")
        return PilotReadinessAssessment(
            PilotReadinessVerdict.SAFETY_OR_INTEGRITY_BLOCKED, tuple(reasons), refs, limitations)

    # 2. No live evidence.
    if live_evaluation_count <= 0:
        reasons.append("no_live_evaluations")
        return PilotReadinessAssessment(
            PilotReadinessVerdict.INSUFFICIENT_LIVE_EVIDENCE, tuple(reasons), refs, limitations)

    # 3. Unresolved serious possible false CLEAR, or recurring policy defects.
    if unresolved_serious_false_clear or unresolved_policy_defects > 0:
        reasons.append(f"unresolved_possible_false_clear={len(unresolved_serious_false_clear)}")
        reasons.append(f"unresolved_policy_defects={unresolved_policy_defects}")
        return PilotReadinessAssessment(
            PilotReadinessVerdict.PILOT_CALIBRATION_REQUIRED, tuple(reasons), refs, limitations)

    # 4. Insufficient reviewer coverage.
    if reviewer_feedback_coverage < minimum_feedback_coverage:
        reasons.append(f"feedback_coverage={reviewer_feedback_coverage:.3f}<"
                       f"{minimum_feedback_coverage}")
        return PilotReadinessAssessment(
            PilotReadinessVerdict.INSUFFICIENT_LIVE_EVIDENCE, tuple(reasons), refs, limitations)

    # 5. No demonstrated incremental value.
    if not incremental_value_demonstrated:
        reasons.append("no_demonstrated_incremental_value")
        return PilotReadinessAssessment(
            PilotReadinessVerdict.PRODUCT_VALUE_NOT_PROVEN, tuple(reasons), refs, limitations)

    reasons.append("safety_clean+live_evidence+coverage+value+no_unresolved_false_clear")
    return PilotReadinessAssessment(
        PilotReadinessVerdict.READY_FOR_ENFORCEMENT_DESIGN, tuple(reasons), refs, limitations)


__all__ = ["PilotReadinessAssessment", "assess_enforcement_readiness"]

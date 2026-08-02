"""Adverse-case inventory.

Every adverse case is individually reviewable and is NEVER hidden inside an
aggregate metric. An unresolved adverse case can block the readiness verdict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from ..fingerprints import domain_hash
from .analysis import PilotStudyEvaluation
from .annotation import PilotEvaluationAnnotation
from .vocab import AdverseCaseKind, InterventionAssessment, StatusAssessment

DOMAIN_ADVERSE = "cg.pilot_study.adverse_case.v1"


@dataclass(frozen=True)
class PilotAdverseCase:
    """An immutable, individually-reviewable adverse case."""

    case_id: str
    pilot_id: str
    kind: AdverseCaseKind
    workflow_revision_id: str
    evidence_class: str
    detail: str
    supporting_refs: Tuple[str, ...] = ()
    resolved: bool = False
    serious: bool = True

    @property
    def case_fingerprint(self) -> str:
        return domain_hash(DOMAIN_ADVERSE, {
            "case_id": self.case_id, "pilot_id": self.pilot_id, "kind": self.kind.value,
            "workflow_revision_id": self.workflow_revision_id,
            "evidence_class": self.evidence_class, "detail": self.detail,
            "supporting_refs": sorted(self.supporting_refs), "resolved": self.resolved,
            "serious": self.serious})

    @property
    def record_id(self) -> str:
        return f"pilot-adverse:{self.case_id}:{self.case_fingerprint[:12]}"


def collect_adverse_cases(
    pilot_id: str,
    evaluations: List[PilotStudyEvaluation],
    annotations: List[PilotEvaluationAnnotation],
    *,
    security_findings: Tuple[str, ...] = (),
    manifest_mismatch: bool = False,
) -> List[PilotAdverseCase]:
    """Assemble the adverse-case list from evaluations, annotations, and security."""
    cases: List[PilotAdverseCase] = []
    by_rev = {a.workflow_revision_id: a for a in annotations}

    for e in evaluations:
        a = by_rev.get(e.workflow_revision_id)
        cid = domain_hash(DOMAIN_ADVERSE, {"p": pilot_id, "rev": e.workflow_revision_id, "k": "eval"})[:16]
        if a is not None:
            # Possible false CLEAR: Ugence CLEAR but reviewer says too lenient / wrong.
            if e.clearance_status == "CLEAR" and a.status_assessment in (
                    StatusAssessment.TOO_LENIENT, StatusAssessment.WRONG_STATUS):
                cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.POSSIBLE_FALSE_CLEAR,
                             e.workflow_revision_id, e.evidence_class.value,
                             "CLEAR disputed by reviewer", (a.annotation_id,)))
            if e.clearance_status == "BLOCK" and a.status_assessment is StatusAssessment.TOO_STRICT:
                cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.POSSIBLE_UNNECESSARY_BLOCK,
                             e.workflow_revision_id, e.evidence_class.value,
                             "BLOCK disputed by reviewer", (a.annotation_id,)))
            if e.clearance_status == "ESCALATE" and a.intervention_assessment is \
                    InterventionAssessment.UNNECESSARY_INTERVENTION:
                cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.POSSIBLE_UNNECESSARY_ESCALATE,
                             e.workflow_revision_id, e.evidence_class.value,
                             "ESCALATE disputed by reviewer", (a.annotation_id,)))
            if not a.required_authority_correct:
                cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.MISSED_AUTHORITY_REQUIREMENT,
                             e.workflow_revision_id, e.evidence_class.value,
                             "required authority disputed", (a.annotation_id,)))
        if e.conflicts:
            cases.append(PilotAdverseCase(cid + "c", pilot_id,
                         AdverseCaseKind.SOURCE_CONFLICT_MISHANDLING, e.workflow_revision_id,
                         e.evidence_class.value, f"conflicts: {sorted(e.conflicts)}",
                         serious=False))

    for finding in security_findings:
        cid = domain_hash(DOMAIN_ADVERSE, {"p": pilot_id, "sec": finding})[:16]
        cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.INTEGRITY_ANOMALY, "",
                     "SECURITY", finding, serious=True))
    if manifest_mismatch:
        cid = domain_hash(DOMAIN_ADVERSE, {"p": pilot_id, "amend": "mismatch"})[:16]
        cases.append(PilotAdverseCase(cid, pilot_id, AdverseCaseKind.POLICY_AMENDMENT_AFTER_START,
                     "", "MANIFEST", "manifest fingerprint changed after pilot start", serious=True))
    return cases


__all__ = ["PilotAdverseCase", "collect_adverse_cases"]

"""Pilot metrics + analysis with strict evidence-class separation.

Metrics are reported *separately* per group and never blended into one score.
Synthetic and supplied-snapshot results are NEVER aggregated into a metric
presented as live enterprise performance. No precision/recall/accuracy is produced
(no ground-truth protocol exists); reviewer-derived findings are reported as
disagreement rates, *possible* unnecessary/missed intervention counts, and
incremental-value case counts, always with numerator/denominator/missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from .annotation import PilotEvaluationAnnotation
from .vocab import (
    IncrementalValueLabel,
    InterventionAssessment,
    LIVE_EVIDENCE_CLASSES,
    NON_LIVE_EVIDENCE_CLASSES,
    PilotCohort,
    PilotEvidenceClass,
    RootCause,
    StatusAssessment,
    UNIQUE_VALUE_LABELS,
)

DOMAIN_STUDY_METRICS = "cg.pilot_study.metrics.v1"
_STATUSES = ("CLEAR", "HOLD", "BLOCK", "ESCALATE")


@dataclass(frozen=True)
class PilotStudyEvaluation:
    """One pilot evaluation with its evidence class + cohorts (analysis view)."""

    workflow_revision_id: str
    evidence_class: PilotEvidenceClass
    clearance_status: str
    human_intervention_required: bool
    cohorts: Tuple[PilotCohort, ...] = ()
    source_failures: Tuple[str, ...] = ()
    stale: bool = False
    conflicts: Tuple[str, ...] = ()
    amendment_side: str = ""  # "before" | "after" | ""

    @property
    def is_live(self) -> bool:
        return self.evidence_class in LIVE_EVIDENCE_CLASSES


def _dist(evals: List[PilotStudyEvaluation]) -> Dict[str, int]:
    d = {s: 0 for s in _STATUSES}
    for e in evals:
        if e.clearance_status in d:
            d[e.clearance_status] += 1
    return d


@dataclass(frozen=True)
class PilotStudyMetrics:
    coverage: Dict[str, Any]
    clearance_distribution_live: Dict[str, int]
    clearance_distribution_non_live: Dict[str, int]
    intervention_quality: Dict[str, Any]
    source_quality: Dict[str, Any]
    policy_quality: Dict[str, Any]
    incremental_value: Dict[str, Any]
    operational_quality: Dict[str, Any]
    evidence_class_counts: Dict[str, int]
    cohort_counts: Dict[str, int]

    @property
    def metrics_fingerprint(self) -> str:
        return domain_hash(DOMAIN_STUDY_METRICS, {
            "coverage": self.coverage,
            "clearance_distribution_live": self.clearance_distribution_live,
            "clearance_distribution_non_live": self.clearance_distribution_non_live,
            "intervention_quality": self.intervention_quality,
            "source_quality": self.source_quality, "policy_quality": self.policy_quality,
            "incremental_value": self.incremental_value,
            "operational_quality": self.operational_quality,
            "evidence_class_counts": self.evidence_class_counts,
            "cohort_counts": self.cohort_counts})


def analyze_pilot_results(
    evaluations: List[PilotStudyEvaluation],
    annotations: List[PilotEvaluationAnnotation],
    *,
    candidates_identified: int = 0,
    candidates_selected: int = 0,
    feedback_requested: int = 0,
    operational: Optional[Mapping[str, Any]] = None,
) -> PilotStudyMetrics:
    """Compute the separated metric profile (live vs non-live kept distinct)."""
    live = [e for e in evaluations if e.is_live]
    non_live = [e for e in evaluations if not e.is_live]

    evidence_counts: Dict[str, int] = {}
    for e in evaluations:
        evidence_counts[e.evidence_class.value] = evidence_counts.get(e.evidence_class.value, 0) + 1
    cohort_counts: Dict[str, int] = {}
    for e in evaluations:
        for c in e.cohorts:
            cohort_counts[c.value] = cohort_counts.get(c.value, 0) + 1

    coverage = {
        "candidates_identified": candidates_identified,
        "candidates_selected": candidates_selected,
        "evaluations_attempted": len(evaluations),
        "evaluations_completed": len(evaluations),
        "evaluations_live": len(live), "evaluations_non_live": len(non_live),
        "reviewer_feedback_requested": feedback_requested,
        "reviewer_feedback_completed": len(annotations),
        "reviewer_feedback_missing": max(0, feedback_requested - len(annotations)),
        "evidence_class_coverage": evidence_counts, "cohort_coverage": cohort_counts,
    }

    # Intervention quality (from annotations; denominator is annotation count).
    n_ann = len(annotations)
    agree = sum(1 for a in annotations if a.status_assessment is StatusAssessment.AGREE)
    unnecessary = sum(1 for a in annotations
                      if a.intervention_assessment is InterventionAssessment.UNNECESSARY_INTERVENTION)
    missed = sum(1 for a in annotations
                 if a.intervention_assessment is InterventionAssessment.MISSING_INTERVENTION)
    wrong_authority = sum(1 for a in annotations if not a.required_authority_correct)
    disagreements = sum(1 for a in annotations if a.disagrees_on_status)
    intervention_quality = {
        "annotation_denominator": n_ann,
        "reviewer_agreement_count": agree,
        "reviewer_disagreement_rate": round(disagreements / n_ann, 6) if n_ann else 0.0,
        "possible_unnecessary_intervention_count": unnecessary,
        "possible_missed_intervention_count": missed,
        "wrong_required_authority_count": wrong_authority,
        "unresolved_count": sum(1 for a in annotations
                                if a.status_assessment is StatusAssessment.INSUFFICIENT_INFORMATION),
    }

    source_quality = {
        "evaluation_denominator": len(evaluations),
        "source_failure_count": sum(1 for e in evaluations if e.source_failures),
        "stale_signal_count": sum(1 for e in evaluations if e.stale),
        "conflict_count": sum(1 for e in evaluations if e.conflicts),
        "identity_mismatch_count": sum(1 for e in evaluations
                                       if any("IDENTITY_MISMATCH" in f for f in e.source_failures)),
        "supplied_snapshot_dependence": evidence_counts.get(
            PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT.value, 0),
    }

    too_strict = sum(1 for a in annotations if a.status_assessment is StatusAssessment.TOO_STRICT)
    too_lenient = sum(1 for a in annotations if a.status_assessment is StatusAssessment.TOO_LENIENT)
    policy_defects = sum(1 for a in annotations
                         if RootCause.POLICY_CONFIGURATION in a.root_cause_categories)
    policy_quality = {
        "policy_defect_count": policy_defects,
        "possible_overly_strict_count": too_strict,
        "possible_overly_lenient_count": too_lenient,
        "results_before_amendment": len([e for e in evaluations if e.amendment_side == "before"]),
        "results_after_amendment": len([e for e in evaluations if e.amendment_side == "after"]),
    }

    label_counts: Dict[str, int] = {}
    unique_with_evidence = 0
    for a in annotations:
        for l in a.incremental_value_labels:
            label_counts[l.value] = label_counts.get(l.value, 0) + 1
        if any(l in UNIQUE_VALUE_LABELS for l in a.incremental_value_labels) and a.unique_value_evidence_ref:
            unique_with_evidence += 1
    incremental_value = {
        "labels": label_counts,
        "unique_signal_cases_with_evidence": unique_with_evidence,
        "duplicate_ci_control_cases": label_counts.get(
            IncrementalValueLabel.EXISTING_CI_ALREADY_CAUGHT.value, 0)
            + label_counts.get(IncrementalValueLabel.GITHUB_RULE_ALREADY_CAUGHT.value, 0),
        "no_incremental_value_cases": label_counts.get(
            IncrementalValueLabel.NO_INCREMENTAL_VALUE.value, 0),
    }

    operational_quality = dict(operational or {})
    operational_quality.setdefault("execution_status", "DISABLED")

    return PilotStudyMetrics(
        coverage=coverage,
        clearance_distribution_live=_dist(live),
        clearance_distribution_non_live=_dist(non_live),
        intervention_quality=intervention_quality, source_quality=source_quality,
        policy_quality=policy_quality, incremental_value=incremental_value,
        operational_quality=operational_quality, evidence_class_counts=evidence_counts,
        cohort_counts=cohort_counts)


__all__ = ["PilotStudyEvaluation", "PilotStudyMetrics", "analyze_pilot_results"]

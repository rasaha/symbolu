"""Policy calibration recommendations + offline policy replay.

Recommendations are *proposals* bound to supporting evaluations; they never change
active policy. Replay re-scores completed evaluations against a proposed policy
candidate using **persisted facts only** (no external call), never overwrites the
original results, and is always labelled as historical replay — never a real
operational outcome.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Tuple

from ..fingerprints import domain_hash
from .analysis import PilotStudyEvaluation
from .annotation import PilotEvaluationAnnotation
from .vocab import CalibrationAdjustment, PilotEvidenceClass, RootCause, StatusAssessment

DOMAIN_CALIBRATION = "cg.pilot_study.calibration.v1"
DOMAIN_REPLAY = "cg.pilot_study.replay.v1"

_ROOT_TO_ADJUSTMENT = {
    RootCause.POLICY_CONFIGURATION: CalibrationAdjustment.SIGNAL_REQUIREMENT_CHANGE,
    RootCause.SOURCE_FRESHNESS: CalibrationAdjustment.FRESHNESS_WINDOW_CHANGE,
    RootCause.SOURCE_CONFLICT: CalibrationAdjustment.STATUS_PRECEDENCE_CHANGE,
    RootCause.SOURCE_DATA: CalibrationAdjustment.MORE_EVIDENCE_REQUIRED,
    RootCause.ADAPTER_FAILURE: CalibrationAdjustment.ADAPTER_REPAIR,
    RootCause.AUTHORITY_MAPPING: CalibrationAdjustment.AUTHORITY_MAPPING_CHANGE,
    RootCause.INTERVENTION_ROUTING: CalibrationAdjustment.INTERVENTION_ROUTING_CHANGE,
}


@dataclass(frozen=True)
class PilotCalibrationRecommendation:
    """A proposed policy adjustment bound to supporting evaluations. Never applied."""

    recommendation_id: str
    pilot_id: str
    affected_policy_ref: str
    supporting_evaluations: Tuple[str, ...]
    problem_category: RootCause
    proposed_adjustment: CalibrationAdjustment
    expected_effect: str
    adjustment_risk: str
    requires_new_pilot_revision: bool = True

    @property
    def recommendation_fingerprint(self) -> str:
        return domain_hash(DOMAIN_CALIBRATION, {
            "recommendation_id": self.recommendation_id, "pilot_id": self.pilot_id,
            "affected_policy_ref": self.affected_policy_ref,
            "supporting_evaluations": sorted(self.supporting_evaluations),
            "problem_category": self.problem_category.value,
            "proposed_adjustment": self.proposed_adjustment.value,
            "expected_effect": self.expected_effect, "adjustment_risk": self.adjustment_risk,
            "requires_new_pilot_revision": self.requires_new_pilot_revision})

    @property
    def record_id(self) -> str:
        return f"pilot-calibration:{self.recommendation_id}:{self.recommendation_fingerprint[:12]}"


def generate_calibration_recommendations(
    pilot_id: str, policy_ref: str, annotations: List[PilotEvaluationAnnotation],
    *, min_recurrence: int = 2,
) -> List[PilotCalibrationRecommendation]:
    """Group recurring disagreements by root cause into proposed adjustments."""
    by_cause: Dict[RootCause, List[str]] = {}
    for a in annotations:
        if a.status_assessment is StatusAssessment.AGREE:
            continue
        for cause in a.root_cause_categories:
            by_cause.setdefault(cause, []).append(a.workflow_revision_id)
    recs: List[PilotCalibrationRecommendation] = []
    for cause, revs in sorted(by_cause.items(), key=lambda kv: kv[0].value):
        if len(revs) < min_recurrence:
            continue
        adjustment = _ROOT_TO_ADJUSTMENT.get(cause, CalibrationAdjustment.MORE_EVIDENCE_REQUIRED)
        rid = domain_hash(DOMAIN_CALIBRATION, {"pilot": pilot_id, "cause": cause.value})[:20]
        recs.append(PilotCalibrationRecommendation(
            recommendation_id=rid, pilot_id=pilot_id, affected_policy_ref=policy_ref,
            supporting_evaluations=tuple(sorted(set(revs))), problem_category=cause,
            proposed_adjustment=adjustment,
            expected_effect=f"may reduce {cause.value} disagreements ({len(revs)} cases)",
            adjustment_risk="requires a new pilot revision to validate before any use"))
    return recs


@dataclass(frozen=True)
class PilotReplayResult:
    """Side-by-side original vs replayed outcomes under a policy candidate."""

    pilot_id: str
    policy_candidate_ref: str
    policy_candidate_fingerprint: str
    comparisons: Tuple[Tuple[str, str, str], ...]  # (revision_id, original, replayed)
    evidence_class: str = PilotEvidenceClass.HISTORICAL_REPLAY.value

    @property
    def changed_count(self) -> int:
        return sum(1 for _, o, r in self.comparisons if o != r)

    @property
    def replay_fingerprint(self) -> str:
        return domain_hash(DOMAIN_REPLAY, {
            "pilot_id": self.pilot_id, "policy_candidate_ref": self.policy_candidate_ref,
            "policy_candidate_fingerprint": self.policy_candidate_fingerprint,
            "comparisons": sorted([list(c) for c in self.comparisons]),
            "evidence_class": self.evidence_class})


def replay_pilot_policy(
    pilot_id: str,
    evaluations: List[PilotStudyEvaluation],
    *,
    policy_candidate_ref: str,
    policy_candidate_fingerprint: str,
    replay_fn: Callable[[PilotStudyEvaluation], str],
) -> PilotReplayResult:
    """Replay persisted evaluations under a policy candidate (offline; never applied).

    ``replay_fn`` scores an evaluation from its *persisted facts* only. Original
    results are never overwritten; the output is labelled HISTORICAL_REPLAY.
    """
    comparisons = tuple(
        (e.workflow_revision_id, e.clearance_status, replay_fn(e))
        for e in sorted(evaluations, key=lambda x: x.workflow_revision_id))
    return PilotReplayResult(
        pilot_id=pilot_id, policy_candidate_ref=policy_candidate_ref,
        policy_candidate_fingerprint=policy_candidate_fingerprint, comparisons=comparisons)


__all__ = [
    "PilotCalibrationRecommendation", "generate_calibration_recommendations",
    "PilotReplayResult", "replay_pilot_policy",
]

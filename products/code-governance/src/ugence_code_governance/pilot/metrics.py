"""Deterministic shadow-pilot quality metrics over a fixed record set.

Metrics are a **profile**, never a single blended safety score, and mandatory
failures stay individually visible. No precision/recall is claimed unless a valid
labelled outcome set exists (it does not in MVP 1D), so reviewer-derived error
categories are reported as *possible* until ground truth is independently
established.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Tuple

from ..fingerprints import domain_hash
from .config import PilotStatus, PilotThresholds
from .records import FeedbackAgreement, PilotReviewerFeedback, ShadowPilotEvaluationRecord

DOMAIN_PILOT_METRICS = "cg.pilot.metrics.v1"


def _rate(n: int, d: int) -> float:
    return round(n / d, 6) if d else 0.0


@dataclass(frozen=True)
class ShadowPilotMetrics:
    """A descriptive metric profile for a fixed pilot record set."""

    pilot_id: str
    tenant_id: str
    evaluation_count: int
    clearance_distribution: Dict[str, int]
    clearance_rates: Dict[str, float]
    human_intervention_required_count: int
    human_intervention_required_rate: float
    adapter_success_count: int
    adapter_failure_count: int
    adapter_failure_rate: float
    stale_signal_count: int
    stale_signal_rate: float
    source_conflict_count: int
    source_conflict_rate: float
    artifact_mismatch_count: int
    artifact_mismatch_rate: float
    reviewer_feedback_count: int
    reviewer_feedback_coverage: float
    reviewer_agreement_count: int
    reviewer_agreement_rate: float
    status_disagreement_count: int
    status_disagreement_rate: float
    intervention_disagreement_count: int
    intervention_disagreement_rate: float
    source_data_error_count: int
    source_data_error_rate: float
    policy_config_issue_count: int
    policy_config_issue_rate: float
    escalation_without_feedback_rate: float
    possible_false_hold: int
    possible_false_block: int
    possible_false_escalate: int
    possible_missed_escalation: int

    @property
    def metrics_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PILOT_METRICS, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "evaluation_count": self.evaluation_count,
            "clearance_distribution": self.clearance_distribution,
            "human_intervention_required_count": self.human_intervention_required_count,
            "adapter_failure_count": self.adapter_failure_count,
            "stale_signal_count": self.stale_signal_count,
            "source_conflict_count": self.source_conflict_count,
            "artifact_mismatch_count": self.artifact_mismatch_count,
            "reviewer_feedback_count": self.reviewer_feedback_count,
            "reviewer_agreement_count": self.reviewer_agreement_count,
            "status_disagreement_count": self.status_disagreement_count,
            "intervention_disagreement_count": self.intervention_disagreement_count,
            "source_data_error_count": self.source_data_error_count,
            "policy_config_issue_count": self.policy_config_issue_count,
            "possible_false_hold": self.possible_false_hold,
            "possible_false_block": self.possible_false_block,
            "possible_false_escalate": self.possible_false_escalate,
            "possible_missed_escalation": self.possible_missed_escalation,
        })


_STATUSES = ("CLEAR", "HOLD", "BLOCK", "ESCALATE")


def calculate_pilot_metrics(
    pilot_id: str,
    tenant_id: str,
    records: Tuple[ShadowPilotEvaluationRecord, ...],
    feedback: Tuple[PilotReviewerFeedback, ...],
) -> ShadowPilotMetrics:
    """Compute a deterministic metric profile for a fixed record + feedback set."""
    n = len(records)
    dist = {s: 0 for s in _STATUSES}
    hri = 0
    adapter_fail = 0
    stale = 0
    conflict = 0
    artifact_mismatch = 0
    escalate_revisions = set()
    for r in records:
        status = r.clearance_status if r.clearance_status in dist else "HOLD"
        # NOT_EVALUATED / upstream-not-authorized map to a non-CLEAR bucket (HOLD).
        if r.clearance_status in dist:
            dist[status] += 1
        else:
            dist["HOLD"] += 1
        if r.human_intervention_required:
            hri += 1
        if r.source_failures:
            adapter_fail += 1
        if r.stale:
            stale += 1
        if r.conflicts:
            conflict += 1
        if any("ARTIFACT_IDENTITY_MISMATCH" == f for f in r.source_failures):
            artifact_mismatch += 1
        if r.clearance_status == "ESCALATE":
            escalate_revisions.add(r.workflow_revision_id)

    fb_revisions = {f.workflow_revision_id for f in feedback}
    agree = sum(1 for f in feedback if f.agreement is FeedbackAgreement.AGREE)
    status_dis = sum(1 for f in feedback if f.agreement is FeedbackAgreement.DISAGREE_STATUS)
    interv_dis = sum(1 for f in feedback if f.agreement in (
        FeedbackAgreement.DISAGREE_INTERVENTION_REQUIRED,
        FeedbackAgreement.DISAGREE_INTERVENTION_TYPE))
    source_err = sum(1 for f in feedback if f.agreement is FeedbackAgreement.SOURCE_DATA_INCORRECT)
    policy_issue = sum(1 for f in feedback if f.agreement is FeedbackAgreement.POLICY_CONFIGURATION_ISSUE)
    fb_n = len(feedback)

    poss_false_hold = sum(1 for f in feedback if f.agreement is FeedbackAgreement.DISAGREE_STATUS
                          and f.reviewed_clearance_status == "HOLD")
    poss_false_block = sum(1 for f in feedback if f.agreement is FeedbackAgreement.DISAGREE_STATUS
                           and f.reviewed_clearance_status == "BLOCK")
    poss_false_escalate = sum(1 for f in feedback if f.agreement is FeedbackAgreement.DISAGREE_STATUS
                              and f.reviewed_clearance_status == "ESCALATE")
    poss_missed_escalation = sum(
        1 for f in feedback if f.agreement is FeedbackAgreement.DISAGREE_INTERVENTION_REQUIRED
        and f.reviewed_clearance_status != "ESCALATE")

    escalate_without_fb = sum(1 for rev in escalate_revisions if rev not in fb_revisions)

    return ShadowPilotMetrics(
        pilot_id=pilot_id, tenant_id=tenant_id, evaluation_count=n,
        clearance_distribution=dist,
        clearance_rates={s: _rate(dist[s], n) for s in _STATUSES},
        human_intervention_required_count=hri,
        human_intervention_required_rate=_rate(hri, n),
        adapter_success_count=n - adapter_fail, adapter_failure_count=adapter_fail,
        adapter_failure_rate=_rate(adapter_fail, n),
        stale_signal_count=stale, stale_signal_rate=_rate(stale, n),
        source_conflict_count=conflict, source_conflict_rate=_rate(conflict, n),
        artifact_mismatch_count=artifact_mismatch, artifact_mismatch_rate=_rate(artifact_mismatch, n),
        reviewer_feedback_count=fb_n,
        reviewer_feedback_coverage=_rate(len(fb_revisions), n),
        reviewer_agreement_count=agree, reviewer_agreement_rate=_rate(agree, fb_n),
        status_disagreement_count=status_dis, status_disagreement_rate=_rate(status_dis, fb_n),
        intervention_disagreement_count=interv_dis,
        intervention_disagreement_rate=_rate(interv_dis, fb_n),
        source_data_error_count=source_err, source_data_error_rate=_rate(source_err, fb_n),
        policy_config_issue_count=policy_issue, policy_config_issue_rate=_rate(policy_issue, fb_n),
        escalation_without_feedback_rate=_rate(escalate_without_fb, len(escalate_revisions) or 0),
        possible_false_hold=poss_false_hold, possible_false_block=poss_false_block,
        possible_false_escalate=poss_false_escalate,
        possible_missed_escalation=poss_missed_escalation)


def evaluate_pilot_status(
    metrics: ShadowPilotMetrics,
    thresholds: PilotThresholds,
    *,
    reconstruction_complete_rate: float = 1.0,
    unresolved_integrity_failures: int = 0,
) -> PilotStatus:
    """Map a metric profile to a configured-threshold status (never enables execution)."""
    if unresolved_integrity_failures > thresholds.maximum_unresolved_integrity_failures:
        return PilotStatus.INTEGRITY_FAILURE
    if metrics.evaluation_count < thresholds.minimum_evaluations:
        return PilotStatus.INSUFFICIENT_DATA
    if metrics.reviewer_feedback_coverage < thresholds.minimum_feedback_coverage:
        return PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS
    if metrics.adapter_failure_rate > thresholds.maximum_source_failure_rate:
        return PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS
    if metrics.stale_signal_rate > thresholds.maximum_stale_signal_rate:
        return PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS
    if metrics.escalation_without_feedback_rate > thresholds.maximum_unexplained_escalation_rate:
        return PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS
    if reconstruction_complete_rate < thresholds.minimum_reconstruction_complete_rate:
        return PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS
    return PilotStatus.MEETS_CONFIGURED_THRESHOLDS


__all__ = ["ShadowPilotMetrics", "calculate_pilot_metrics", "evaluate_pilot_status",
           "DOMAIN_PILOT_METRICS"]

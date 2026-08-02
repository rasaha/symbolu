"""Shared builders for MVP 1F (bounded shadow-pilot validation) tests."""
from __future__ import annotations

from ugence_code_governance.pilot_study import (
    ActualOutcome,
    IncrementalValue,
    IncrementalValueLabel,
    InterventionAssessment,
    PilotCandidate,
    PilotEvaluationAnnotation,
    PilotEvidenceClass,
    PilotStudyEvaluation,
    PilotStudyManifest,
    ReviewMode,
    RootCause,
    StatusAssessment,
    PilotCohort,
)

T = "2026-09-02T00:00:00Z"


def manifest(**over):
    base = dict(
        manifest_id="m1", manifest_version="v1", pilot_id="p1", tenant_id="acme",
        allowed_repositories=("acme/widgets",), allowed_branches=("main",),
        pilot_start_date="2026-09-01", pilot_end_date="2026-09-15",
        maximum_evaluations=50, target_sample_count=25, selection_method="explicit_pr_list",
        evaluation_profile_ref="prof:v1", policy_version="pol:v1",
        adapter_registry_version="reg:v1", intervention_routing_version="route:v1",
        reviewer_role_allowlist=("security-owner",), reviewer_refs=("rv1",),
        evidence_classes_permitted=("LIVE_GITHUB_METADATA", "SUPPLIED_ENTERPRISE_SNAPSHOT",
                                    "SYNTHETIC_CONTROL", "HISTORICAL_REPLAY"),
        minimum_reviewer_feedback_target=10, reviewer_protocol_ref="proto:v1")
    base.update(over)
    return PilotStudyManifest(**base)


def candidate(rid, *, repo="acme/widgets", branch="main", pr=1, ec="LIVE_GITHUB_METADATA", head="h"):
    return PilotCandidate(repo, branch, pr, f"wf-{rid}", rid, head, ec)


def evaluation(rid, status, *, ec=PilotEvidenceClass.LIVE_GITHUB_METADATA, hri=False,
               cohorts=(), failures=(), stale=False, conflicts=(), side=""):
    return PilotStudyEvaluation(rid, ec, status, hri, cohorts, failures, stale, conflicts, side)


def annotation(rid, *, aid="a1", status=StatusAssessment.AGREE, ugence="ESCALATE",
               intervention=InterventionAssessment.CORRECT_INTERVENTION, authority=True,
               value=IncrementalValue.VALUE_BEYOND_CI_CONFIRMED, labels=(),
               root_causes=(), outcome=ActualOutcome.WAITED_FOR_CHANGE_WINDOW,
               ci_detect=False, mode=ReviewMode.BLINDED_INITIAL_THEN_REVEALED,
               ec=PilotEvidenceClass.LIVE_GITHUB_METADATA, tenant="acme", role="security-owner",
               evidence_ref="", initial=StatusAssessment.AGREE):
    return PilotEvaluationAnnotation(
        annotation_id=aid, pilot_id="p1", evaluation_id=f"ev-{rid}", tenant_id=tenant,
        workflow_id=f"wf-{rid}", workflow_revision_id=rid, head_sha="h", reviewer_ref="rv1",
        reviewer_role=role, review_mode=mode, evidence_class=ec, initial_reviewer_status=initial,
        ugence_clearance_status=ugence, status_assessment=status, intervention_assessment=intervention,
        required_authority_correct=authority, incremental_value=value,
        incremental_value_labels=tuple(labels), root_cause_categories=tuple(root_causes),
        actual_outcome=outcome, would_ci_have_detected=ci_detect, created_at=T,
        unique_value_evidence_ref=evidence_ref)

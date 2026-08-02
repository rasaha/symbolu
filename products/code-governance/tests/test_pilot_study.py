"""MVP 1F acceptance tests — bounded shadow-pilot validation study.

Execution stays DISABLED. Supplied snapshots / synthetic scenarios are never
counted as live enterprise evidence; no unsupported statistics are produced;
calibration never changes policy; a readiness verdict never enables execution.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
from cg_study_helpers import annotation, candidate, evaluation, manifest

from ugence_code_governance.pilot_study import (
    AdverseCaseKind,
    AmendmentReason,
    CheckpointKind,
    IncrementalValueLabel,
    InterventionAssessment,
    PilotAmendmentRecord,
    PilotCohort,
    PilotEvidenceClass,
    PilotReadinessVerdict,
    ReviewMode,
    RootCause,
    StatusAssessment,
    analyze_pilot_results,
    assess_enforcement_readiness,
    build_pilot_evidence_pack,
    collect_adverse_cases,
    create_pilot_checkpoint,
    freeze_pilot_study,
    generate_calibration_recommendations,
    replay_pilot_policy,
    run_pilot_security_verification,
    select_pilot_candidates,
    validate_study_manifest,
    verify_pilot_evidence_pack,
)
from ugence_code_governance.pilot_study.annotation import PilotEvaluationAnnotation
from ugence_code_governance.pilot_study.errors import AnnotationError, StudyManifestError
from ugence_code_governance.pilot_study.vocab import CheckpointRecommendation


# --- 1-12. manifest + freeze ------------------------------------------------
def test_valid_bounded_study_manifest_admitted():
    assert validate_study_manifest(manifest()).pilot_id == "p1"


def test_wildcard_tenant_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(tenant_id="*"))


def test_empty_repository_scope_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(allowed_repositories=()))


def test_missing_end_date_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(pilot_end_date=""))


def test_unbounded_sample_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(target_sample_count=0))


def test_missing_reviewer_protocol_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(reviewer_protocol_ref=""))


def test_missing_evidence_class_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(evidence_classes_permitted=()))


def test_execution_enabled_config_rejected():
    with pytest.raises(StudyManifestError):
        validate_study_manifest(manifest(execution_status="ENABLED"))


def test_manifest_fingerprint_deterministic():
    assert manifest().manifest_fingerprint == manifest().manifest_fingerprint


def test_prepilot_freeze_binds_all_versions():
    fr = freeze_pilot_study(manifest(), code_governance_version="0.5.0",
                            action_clearance_version="0.1.0",
                            durable_store_schema_version="code_governance.shadow_store.v1",
                            config_fingerprint="cfg", test_baseline_ref="359", frozen_at="t")
    assert fr.manifest_fingerprint == manifest().manifest_fingerprint
    assert fr.policy_version == "pol:v1" and fr.execution_status == "DISABLED"


def test_freeze_fingerprint_deterministic():
    kw = dict(code_governance_version="0.5.0", action_clearance_version="0.1.0",
              durable_store_schema_version="v1", config_fingerprint="cfg",
              test_baseline_ref="359", frozen_at="t")
    assert freeze_pilot_study(manifest(), **kw).freeze_fingerprint == \
        freeze_pilot_study(manifest(), **kw).freeze_fingerprint


def test_changed_policy_requires_amendment_or_new_revision():
    m1 = manifest()
    m2 = manifest(policy_version="pol:v2")
    assert m1.manifest_fingerprint != m2.manifest_fingerprint
    amend = PilotAmendmentRecord(
        amendment_id="am1", pilot_id="p1", previous_manifest_fingerprint=m1.manifest_fingerprint,
        new_manifest_fingerprint=m2.manifest_fingerprint,
        reason_category=AmendmentReason.POLICY_DEFECT, author_ref="op", approved_at="t",
        effective_evaluation_boundary=10)
    assert amend.report_prior_and_later_separately is True


# --- 13-18. evidence classification ----------------------------------------
def test_live_github_facts_classified_correctly():
    e = evaluation("r1", "CLEAR", ec=PilotEvidenceClass.LIVE_GITHUB_METADATA)
    assert e.is_live


def test_supplied_snapshots_not_classified_as_live():
    e = evaluation("r1", "CLEAR", ec=PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT)
    assert not e.is_live


def test_historical_replay_classified_correctly():
    e = evaluation("r1", "CLEAR", ec=PilotEvidenceClass.HISTORICAL_REPLAY)
    assert not e.is_live


def test_synthetic_controls_excluded_from_live_metrics():
    evals = [evaluation("r1", "ESCALATE", ec=PilotEvidenceClass.LIVE_GITHUB_METADATA),
             evaluation("r2", "CLEAR", ec=PilotEvidenceClass.SYNTHETIC_CONTROL)]
    m = analyze_pilot_results(evals, [])
    assert m.clearance_distribution_live == {"CLEAR": 0, "HOLD": 0, "BLOCK": 0, "ESCALATE": 1}
    assert m.clearance_distribution_non_live["CLEAR"] == 1


def test_mixed_evidence_preserves_every_class():
    evals = [evaluation("r1", "CLEAR", ec=PilotEvidenceClass.LIVE_GITHUB_METADATA),
             evaluation("r2", "HOLD", ec=PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT),
             evaluation("r3", "BLOCK", ec=PilotEvidenceClass.SYNTHETIC_CONTROL)]
    m = analyze_pilot_results(evals, [])
    assert set(m.evidence_class_counts) == {"LIVE_GITHUB_METADATA", "SUPPLIED_ENTERPRISE_SNAPSHOT",
                                            "SYNTHETIC_CONTROL"}


def test_evidence_classification_in_metrics():
    m = analyze_pilot_results([evaluation("r1", "CLEAR")], [])
    assert "LIVE_GITHUB_METADATA" in m.evidence_class_counts


# --- 19-26. candidate selection --------------------------------------------
def test_explicit_pr_list_deterministic():
    cs = [candidate("r1"), candidate("r2", pr=2)]
    a, _ = select_pilot_candidates(manifest(), cs)
    b, _ = select_pilot_candidates(manifest(), cs)
    assert [c.workflow_revision_id for c in a] == [c.workflow_revision_id for c in b]


def test_repository_allowlist_enforced_in_selection():
    _, rec = select_pilot_candidates(manifest(), [candidate("r1", repo="other/x")])
    assert ("r1", "repository_not_allowed") in rec.excluded


def test_branch_allowlist_enforced_in_selection():
    _, rec = select_pilot_candidates(manifest(), [candidate("r1", branch="dev")])
    assert ("r1", "branch_not_allowed") in rec.excluded


def test_excluded_candidate_reason_persisted():
    _, rec = select_pilot_candidates(manifest(), [candidate("r1", ec="OPERATIONAL_OBSERVATION")])
    assert ("r1", "evidence_class_not_permitted") in rec.excluded


def test_maximum_count_enforced_in_selection():
    cs = [candidate(f"r{i}", pr=i) for i in range(5)]
    sel, rec = select_pilot_candidates(manifest(maximum_evaluations=2), cs)
    assert len(sel) == 2 and any(r[1] == "maximum_count_reached" for r in rec.excluded)


def test_duplicate_revision_deduplicated():
    sel, rec = select_pilot_candidates(manifest(), [candidate("r1"), candidate("r1")])
    assert len(sel) == 1 and ("r1", "already_evaluated_or_duplicate") in rec.excluded


def test_already_evaluated_revision_excluded():
    sel, rec = select_pilot_candidates(manifest(), [candidate("r1")], already_evaluated=("r1",))
    assert not sel


def test_selection_record_fingerprint_deterministic():
    _, r1 = select_pilot_candidates(manifest(), [candidate("r1")])
    _, r2 = select_pilot_candidates(manifest(), [candidate("r1")])
    assert r1.selection_fingerprint == r2.selection_fingerprint


# --- 27-35. reviewer protocol ----------------------------------------------
def test_independent_initial_assessment_preserved():
    a = annotation("r1", initial=StatusAssessment.TOO_STRICT, status=StatusAssessment.AGREE)
    assert a.initial_reviewer_status is StatusAssessment.TOO_STRICT


def test_non_blinded_review_labelled():
    a = annotation("r1", mode=ReviewMode.REVIEW_NOT_BLINDED)
    assert not a.blinded


def test_annotation_bound_to_exact_revision():
    a = annotation("rev-exact")
    assert a.workflow_revision_id == "rev-exact" and a.head_sha == "h"


def test_unique_value_claim_requires_evidence_reference():
    with pytest.raises(AnnotationError):
        annotation("r1", labels=(IncrementalValueLabel.UGENCE_UNIQUE_SIGNAL,), evidence_ref="")


def test_unique_value_claim_with_evidence_admitted():
    a = annotation("r1", labels=(IncrementalValueLabel.UGENCE_UNIQUE_SIGNAL,),
                   evidence_ref="evidence:xyz")
    assert a.annotation_fingerprint


def test_disagreement_categories_curated():
    a = annotation("r1", status=StatusAssessment.WRONG_STATUS)
    assert a.disagrees_on_status


def test_multiple_reviewers_preserved_independently():
    a = annotation("r1", aid="a1", role="security-owner")
    b = annotation("r1", aid="a2", role="service-owner")
    assert a.annotation_fingerprint != b.annotation_fingerprint


def test_annotation_fingerprint_deterministic():
    assert annotation("r1").annotation_fingerprint == annotation("r1").annotation_fingerprint


# --- 36-46. metrics + analysis ---------------------------------------------
def test_denominators_reported():
    m = analyze_pilot_results([evaluation("r1", "ESCALATE")], [annotation("r1")],
                              feedback_requested=2)
    assert m.intervention_quality["annotation_denominator"] == 1
    assert m.coverage["reviewer_feedback_missing"] == 1


def test_reviewer_disagreement_rate_correct():
    anns = [annotation("r1", aid="a1", status=StatusAssessment.AGREE),
            annotation("r2", aid="a2", status=StatusAssessment.WRONG_STATUS)]
    m = analyze_pilot_results([evaluation("r1", "CLEAR"), evaluation("r2", "BLOCK")], anns)
    assert m.intervention_quality["reviewer_disagreement_rate"] == 0.5


def test_possible_unnecessary_and_missed_counts():
    anns = [annotation("r1", aid="a1", intervention=InterventionAssessment.UNNECESSARY_INTERVENTION),
            annotation("r2", aid="a2", intervention=InterventionAssessment.MISSING_INTERVENTION)]
    m = analyze_pilot_results([], anns)
    assert m.intervention_quality["possible_unnecessary_intervention_count"] == 1
    assert m.intervention_quality["possible_missed_intervention_count"] == 1


def test_no_unsupported_accuracy_metric():
    m = analyze_pilot_results([evaluation("r1", "CLEAR")], [])
    blob = str(m.__dict__).lower()
    for banned in ("precision", "recall", "false_positive_rate", "sensitivity", "specificity", "accuracy"):
        assert banned not in blob


def test_cohort_metrics_separated():
    evals = [evaluation("r1", "CLEAR", cohorts=(PilotCohort.ROUTINE_LOW_RISK,)),
             evaluation("r2", "ESCALATE", cohorts=(PilotCohort.SENSITIVE_CODE_PATH,))]
    m = analyze_pilot_results(evals, [])
    assert m.cohort_counts["ROUTINE_LOW_RISK"] == 1 and m.cohort_counts["SENSITIVE_CODE_PATH"] == 1


def test_before_after_amendment_separated():
    evals = [evaluation("r1", "CLEAR", side="before"), evaluation("r2", "CLEAR", side="after")]
    m = analyze_pilot_results(evals, [])
    assert m.policy_quality["results_before_amendment"] == 1
    assert m.policy_quality["results_after_amendment"] == 1


def test_unique_value_case_requires_evidence_in_metrics():
    a = annotation("r1", labels=(IncrementalValueLabel.UGENCE_UNIQUE_SIGNAL,),
                   evidence_ref="e:1")
    m = analyze_pilot_results([evaluation("r1", "ESCALATE")], [a])
    assert m.incremental_value["unique_signal_cases_with_evidence"] == 1


# --- 47-53. calibration ----------------------------------------------------
def test_recommendation_binds_supporting_evaluations():
    anns = [annotation(f"r{i}", aid=f"a{i}", status=StatusAssessment.TOO_STRICT,
                       root_causes=(RootCause.POLICY_CONFIGURATION,)) for i in range(2)]
    recs = generate_calibration_recommendations("p1", "pol:v1", anns)
    assert recs and set(recs[0].supporting_evaluations) == {"r0", "r1"}


def test_recommendation_does_not_change_policy():
    recs = generate_calibration_recommendations(
        "p1", "pol:v1", [annotation(f"r{i}", aid=f"a{i}", status=StatusAssessment.TOO_STRICT,
                                    root_causes=(RootCause.POLICY_CONFIGURATION,)) for i in range(2)])
    assert recs[0].requires_new_pilot_revision is True
    assert not hasattr(recs[0], "apply")


def test_replay_uses_persisted_facts_only_no_external_call():
    evals = [evaluation("r1", "HOLD"), evaluation("r2", "CLEAR")]
    result = replay_pilot_policy("p1", evals, policy_candidate_ref="pol:v2",
                                 policy_candidate_fingerprint="fp",
                                 replay_fn=lambda e: "CLEAR" if e.clearance_status == "HOLD" else e.clearance_status)
    assert ("r1", "HOLD", "CLEAR") in result.comparisons and result.changed_count == 1


def test_replay_original_preserved_and_labelled():
    evals = [evaluation("r1", "HOLD")]
    result = replay_pilot_policy("p1", evals, policy_candidate_ref="pol:v2",
                                 policy_candidate_fingerprint="fp", replay_fn=lambda e: "BLOCK")
    assert evals[0].clearance_status == "HOLD"  # original untouched
    assert result.evidence_class == "HISTORICAL_REPLAY"


def test_replay_records_policy_candidate_fingerprint():
    result = replay_pilot_policy("p1", [evaluation("r1", "HOLD")], policy_candidate_ref="pol:v2",
                                 policy_candidate_fingerprint="candidate-fp", replay_fn=lambda e: e.clearance_status)
    assert result.policy_candidate_fingerprint == "candidate-fp"


# --- 54-58. adverse cases --------------------------------------------------
def test_possible_false_clear_individually_listed():
    e = evaluation("r1", "CLEAR")
    a = annotation("r1", ugence="CLEAR", status=StatusAssessment.TOO_LENIENT)
    cases = collect_adverse_cases("p1", [e], [a])
    assert any(c.kind is AdverseCaseKind.POSSIBLE_FALSE_CLEAR for c in cases)


def test_possible_unnecessary_block_individually_listed():
    e = evaluation("r1", "BLOCK")
    a = annotation("r1", ugence="BLOCK", status=StatusAssessment.TOO_STRICT)
    cases = collect_adverse_cases("p1", [e], [a])
    assert any(c.kind is AdverseCaseKind.POSSIBLE_UNNECESSARY_BLOCK for c in cases)


def test_source_conflict_case_individually_listed():
    e = evaluation("r1", "HOLD", conflicts=("ACTIVE_INCIDENT",))
    cases = collect_adverse_cases("p1", [e], [])
    assert any(c.kind is AdverseCaseKind.SOURCE_CONFLICT_MISHANDLING for c in cases)


def test_security_finding_case_individually_listed():
    cases = collect_adverse_cases("p1", [], [], security_findings=("read_only_boundary_violation:1",))
    assert any(c.kind is AdverseCaseKind.INTEGRITY_ANOMALY for c in cases)


def test_unresolved_adverse_case_blocks_readiness():
    e = evaluation("r1", "CLEAR")
    a = annotation("r1", ugence="CLEAR", status=StatusAssessment.TOO_LENIENT)
    cases = collect_adverse_cases("p1", [e], [a])
    verdict = assess_enforcement_readiness(pilot_id="p1", adverse_cases=cases,
                                           live_evaluation_count=10, incremental_value_demonstrated=True,
                                           reviewer_feedback_coverage=1.0)
    assert verdict.verdict is PilotReadinessVerdict.PILOT_CALIBRATION_REQUIRED


# --- 59-67. security -------------------------------------------------------
def test_credential_leak_yields_safety_blocked():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], credential_leaks=1,
                                     live_evaluation_count=10)
    assert v.verdict is PilotReadinessVerdict.SAFETY_OR_INTEGRITY_BLOCKED


def test_integrity_failure_yields_safety_blocked():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], integrity_failures=1,
                                     live_evaluation_count=10)
    assert v.verdict is PilotReadinessVerdict.SAFETY_OR_INTEGRITY_BLOCKED


def test_write_boundary_violation_yields_safety_blocked():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], write_boundary_violations=1,
                                     live_evaluation_count=10)
    assert v.verdict is PilotReadinessVerdict.SAFETY_OR_INTEGRITY_BLOCKED


def test_security_verification_clean_boundary(tmp_path):
    from ugence_code_governance import CodeGovernanceService, PersistenceMode
    svc = CodeGovernanceService(persistence_mode=PersistenceMode.DURABLE_SHADOW)
    res = run_pilot_security_verification(svc.durable_store, tenant_id="acme", pilot_id="p1",
                                          current_manifest_fingerprint="fp", frozen_manifest_fingerprint="fp")
    assert res.ok and res.execution_status == "DISABLED"
    svc.close()


def test_manifest_mismatch_detected_by_security():
    res = run_pilot_security_verification(None, tenant_id="acme", pilot_id="p1",
                                          current_manifest_fingerprint="fpA",
                                          frozen_manifest_fingerprint="fpB")
    assert not res.ok and "manifest_fingerprint_mismatch" in res.findings


# --- 68-73. checkpoints ----------------------------------------------------
def _checkpoint(**over):
    base = dict(pilot_id="p1", tenant_id="acme", kind=CheckpointKind.MIDPOINT, lifecycle_state="ACTIVE",
                evaluations_completed=10, feedback_coverage=0.8, source_failure_rate=0.1,
                disagreement_categories=("POLICY_CONFIGURATION",), unresolved_adverse_cases=0,
                security_status="OK", integrity_status="OK", created_at="t")
    base.update(over)
    return create_pilot_checkpoint(**base)


def test_pre_pilot_checkpoint_valid():
    cp = _checkpoint(kind=CheckpointKind.PRE_PILOT)
    assert cp.recommendation is CheckpointRecommendation.CONTINUE


def test_checkpoint_deterministic():
    assert _checkpoint().checkpoint_fingerprint == _checkpoint().checkpoint_fingerprint


def test_checkpoint_reports_feedback_coverage():
    assert _checkpoint(feedback_coverage=0.42).feedback_coverage == 0.42


def test_critical_failure_recommends_stop():
    cp = _checkpoint(critical_conditions=("credential_leak",), security_status="FAIL")
    assert cp.recommendation is CheckpointRecommendation.STOP


def test_unresolved_adverse_recommends_pause():
    assert _checkpoint(unresolved_adverse_cases=2).recommendation is CheckpointRecommendation.PAUSE


def test_checkpoint_execution_disabled():
    assert _checkpoint().execution_status == "DISABLED"


# --- 74-80. evidence pack --------------------------------------------------
def _pack():
    return build_pilot_evidence_pack(
        pilot_id="p1", tenant_id="acme",
        sections={"manifest": [{"record_id": "m1", "fingerprint": "fpm"}],
                  "annotations": [{"record_id": "a1", "fingerprint": "fpa"}]},
        evidence_status="OFFLINE_VERIFIED", readiness_verdict="INSUFFICIENT_LIVE_EVIDENCE")


def test_evidence_pack_deterministic():
    assert _pack()["pack_fingerprint"] == _pack()["pack_fingerprint"]


def test_evidence_pack_verifies_offline():
    assert verify_pilot_evidence_pack(_pack()).ok


def test_missing_artifact_fails_verification():
    pack = _pack()
    bad = copy.deepcopy(pack)
    bad["annotations"].pop()
    assert not verify_pilot_evidence_pack(bad).ok


def test_modified_artifact_fails_verification():
    pack = _pack()
    bad = copy.deepcopy(pack)
    bad["manifest"][0]["fingerprint"] = "TAMPERED"
    assert not verify_pilot_evidence_pack(bad).ok


def test_credential_in_pack_fails_verification():
    pack = _pack()
    bad = copy.deepcopy(pack)
    bad["annotations"][0]["authorization"] = "Bearer ghp_" + "A" * 30
    assert not verify_pilot_evidence_pack(bad).ok


def test_execution_disabled_marker_required_in_pack():
    pack = _pack()
    bad = copy.deepcopy(pack)
    bad["execution_status"] = "ENABLED"
    assert not verify_pilot_evidence_pack(bad).ok


def test_pack_rejects_unknown_version():
    assert not verify_pilot_evidence_pack({"pack_version": "nope"}).ok


# --- 81-89. readiness verdict ----------------------------------------------
def test_insufficient_live_evidence_offline():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], live_evaluation_count=0)
    assert v.verdict is PilotReadinessVerdict.INSUFFICIENT_LIVE_EVIDENCE


def test_recurring_policy_disagreement_calibration_required():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], live_evaluation_count=10,
                                     unresolved_policy_defects=3, reviewer_feedback_coverage=1.0,
                                     incremental_value_demonstrated=True)
    assert v.verdict is PilotReadinessVerdict.PILOT_CALIBRATION_REQUIRED


def test_no_incremental_value_product_value_not_proven():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], live_evaluation_count=10,
                                     reviewer_feedback_coverage=1.0, incremental_value_demonstrated=False)
    assert v.verdict is PilotReadinessVerdict.PRODUCT_VALUE_NOT_PROVEN


def test_ready_requires_no_unresolved_false_clear():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], live_evaluation_count=10,
                                     reviewer_feedback_coverage=1.0, incremental_value_demonstrated=True)
    assert v.verdict is PilotReadinessVerdict.READY_FOR_ENFORCEMENT_DESIGN


def test_readiness_does_not_enable_execution():
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=[], live_evaluation_count=10,
                                     reviewer_feedback_coverage=1.0, incremental_value_demonstrated=True)
    assert v.execution_status == "DISABLED"


def test_verdict_includes_evidence_refs_and_limitations():
    e = evaluation("r1", "CLEAR")
    a = annotation("r1", ugence="CLEAR", status=StatusAssessment.TOO_LENIENT)
    cases = collect_adverse_cases("p1", [e], [a])
    v = assess_enforcement_readiness(pilot_id="p1", adverse_cases=cases, live_evaluation_count=5,
                                     limitations=("small sample",))
    assert v.evidence_refs and v.limitations == ("small sample",)


# --- 90-98. boundaries -----------------------------------------------------
def test_action_clearance_unchanged():
    import ugence_action_clearance as ac
    assert hasattr(ac, "evaluate_clearance") and not hasattr(ac, "PilotStudyManifest")


def test_no_execution_or_write_surface_in_study():
    import ugence_code_governance.pilot_study as ps
    for banned in ("merge", "approve", "execute", "dispatch", "reserve_once", "write_github"):
        assert banned not in ps.__all__


def test_original_clearance_immutable_by_annotation():
    e = evaluation("r1", "ESCALATE")
    annotation("r1", status=StatusAssessment.WRONG_STATUS)  # annotating does not touch e
    assert e.clearance_status == "ESCALATE"


def test_supplied_snapshot_never_counted_as_live():
    evals = [evaluation("r1", "ESCALATE", ec=PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT)]
    m = analyze_pilot_results(evals, [])
    assert sum(m.clearance_distribution_live.values()) == 0
    assert m.source_quality["supplied_snapshot_dependence"] == 1


def test_execution_disabled_everywhere_in_study():
    m = manifest()
    fr = freeze_pilot_study(m, code_governance_version="0.5.0", action_clearance_version="0.1.0",
                            durable_store_schema_version="v1", config_fingerprint="c",
                            test_baseline_ref="b", frozen_at="t")
    assert m.execution_status == "DISABLED" and fr.execution_status == "DISABLED"

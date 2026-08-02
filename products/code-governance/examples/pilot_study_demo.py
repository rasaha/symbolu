"""Deterministic offline MVP 1F demonstration: the bounded shadow-pilot study.

This runs the complete analysis + report flow OFFLINE using supplied snapshots,
synthetic controls, historical replay, and mock reviewer annotations — no live
GitHub, no live enterprise signal, no execution. Every output is labelled
OFFLINE_VERIFIED and NONE of it is counted as live enterprise evidence. Because no
live evaluations occur, the honest readiness verdict is INSUFFICIENT_LIVE_EVIDENCE
and the live pilot is reported as LIVE_PILOT_NOT_RUN.

Run:
    PYTHONPATH=products/code-governance/src:packages/capabilities/action-clearance/src:... \
        python products/code-governance/examples/pilot_study_demo.py
"""
from __future__ import annotations

from ugence_code_governance.pilot_study import (
    ActualOutcome, CheckpointKind, IncrementalValue, IncrementalValueLabel, InterventionAssessment,
    PilotCandidate, PilotEvaluationAnnotation, PilotEvidenceClass, PilotReadinessVerdict,
    PilotStudyEvaluation, PilotStudyManifest, ReviewMode, RootCause, StatusAssessment,
    analyze_pilot_results, assess_enforcement_readiness, build_pilot_evidence_pack,
    collect_adverse_cases, create_pilot_checkpoint, freeze_pilot_study,
    generate_calibration_recommendations, replay_pilot_policy, run_pilot_security_verification,
    select_pilot_candidates, validate_study_manifest, verify_pilot_evidence_pack,
)
from ugence_code_governance.pilot_study.vocab import CheckpointRecommendation

T = "2026-09-02T00:00:00Z"


def _manifest():
    return PilotStudyManifest(
        manifest_id="study-offline-1", manifest_version="v1", pilot_id="pilot-offline", tenant_id="acme",
        allowed_repositories=("acme/billing",), allowed_branches=("main",),
        pilot_start_date="2026-09-01", pilot_end_date="2026-09-15", maximum_evaluations=50,
        target_sample_count=6, selection_method="explicit_workflow_revision_list",
        evaluation_profile_ref="prof:v1", policy_version="pol:v1", adapter_registry_version="reg:v1",
        intervention_routing_version="route:v1", reviewer_role_allowlist=("security-owner", "service-owner"),
        reviewer_refs=("rv1", "rv2"),
        evidence_classes_permitted=("SUPPLIED_ENTERPRISE_SNAPSHOT", "SYNTHETIC_CONTROL", "HISTORICAL_REPLAY"),
        minimum_reviewer_feedback_target=4, reviewer_protocol_ref="proto:v1",
        known_limitations=("offline only; no live GitHub; supplied snapshots are not live evidence",))


def run(verbose=True):
    out = {}

    def say(m):
        if verbose:
            print(m)

    say("== Code Governance MVP 1F — bounded shadow-pilot study (OFFLINE) ==")
    m = _manifest()
    validate_study_manifest(m)
    freeze = freeze_pilot_study(
        m, code_governance_version="0.5.0", action_clearance_version="0.1.0",
        durable_store_schema_version="code_governance.shadow_store.v1",
        config_fingerprint="cfg-fp", test_baseline_ref="baseline:359", frozen_at="2026-09-01T00:00:00Z")
    say(f"  [1-2 manifest+freeze] manifest_fp={m.manifest_fingerprint[:12]} "
        f"freeze_fp={freeze.freeze_fingerprint[:12]}")

    # Candidates — all non-live evidence classes (offline).
    cands = [
        PilotCandidate("acme/billing", "main", 1, "wf1", "rev1", "hA", "SUPPLIED_ENTERPRISE_SNAPSHOT"),
        PilotCandidate("acme/billing", "main", 2, "wf2", "rev2", "hB", "SYNTHETIC_CONTROL"),
        PilotCandidate("acme/billing", "main", 3, "wf3", "rev3", "hC", "SUPPLIED_ENTERPRISE_SNAPSHOT"),
        PilotCandidate("other/x", "main", 4, "wf4", "rev4", "hD", "SYNTHETIC_CONTROL"),  # excluded
    ]
    selected, selection = select_pilot_candidates(m, cands)
    say(f"  [3 candidates] selected={[c.workflow_revision_id for c in selected]} "
        f"excluded={list(selection.excluded)}")

    # Offline evaluations (labelled, never live).
    evals = [
        PilotStudyEvaluation("rev1", PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT, "ESCALATE", True),
        PilotStudyEvaluation("rev2", PilotEvidenceClass.SYNTHETIC_CONTROL, "CLEAR", False),
        PilotStudyEvaluation("rev3", PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT, "HOLD", False,
                             conflicts=("ACTIVE_INCIDENT",)),
    ]

    def _ann(rid, aid, status, intervention, labels=(), root=(), authority=True, evref=""):
        return PilotEvaluationAnnotation(
            annotation_id=aid, pilot_id="pilot-offline", evaluation_id=f"ev-{rid}", tenant_id="acme",
            workflow_id=f"wf-{rid}", workflow_revision_id=rid, head_sha="h", reviewer_ref="rv1",
            reviewer_role="security-owner", review_mode=ReviewMode.BLINDED_INITIAL_THEN_REVEALED,
            evidence_class=PilotEvidenceClass.SUPPLIED_ENTERPRISE_SNAPSHOT,
            initial_reviewer_status=StatusAssessment.AGREE, ugence_clearance_status=status,
            status_assessment=StatusAssessment.AGREE if authority else StatusAssessment.WRONG_STATUS,
            intervention_assessment=intervention, required_authority_correct=authority,
            incremental_value=IncrementalValue.VALUE_BEYOND_CI_CONFIRMED, incremental_value_labels=labels,
            root_cause_categories=root, actual_outcome=ActualOutcome.WAITED_FOR_CHANGE_WINDOW,
            would_ci_have_detected=False, created_at=T, unique_value_evidence_ref=evref)

    annotations = [
        _ann("rev1", "a1", "ESCALATE", InterventionAssessment.CORRECT_INTERVENTION,
             labels=(IncrementalValueLabel.UGENCE_UNIQUE_SIGNAL,), evref="evidence:incident-cross-check"),
        _ann("rev3", "a3", "HOLD", InterventionAssessment.UNNECESSARY_INTERVENTION,
             root=(RootCause.SOURCE_CONFLICT,)),
    ]

    metrics = analyze_pilot_results(evals, annotations, candidates_identified=len(cands),
                                    candidates_selected=len(selected), feedback_requested=3)
    say(f"  [4-6 metrics] live_dist={metrics.clearance_distribution_live} "
        f"non_live_dist={metrics.clearance_distribution_non_live} "
        f"disagreement_rate={metrics.intervention_quality['reviewer_disagreement_rate']}")
    out["live_dist"] = metrics.clearance_distribution_live

    calibration = generate_calibration_recommendations("pilot-offline", "pol:v1", annotations,
                                                        min_recurrence=1)
    say(f"  [7 calibration] recommendations={[r.proposed_adjustment.value for r in calibration]}")

    replay = replay_pilot_policy("pilot-offline", evals, policy_candidate_ref="pol:v2",
                                 policy_candidate_fingerprint="candidate-fp",
                                 replay_fn=lambda e: "CLEAR" if e.clearance_status == "HOLD" else e.clearance_status)
    say(f"  [8 replay] changed_under_candidate={replay.changed_count} "
        f"(labelled {replay.evidence_class})")

    adverse = collect_adverse_cases("pilot-offline", evals, annotations)
    say(f"  [9 adverse] cases={[c.kind.value for c in adverse]}")

    checkpoint = create_pilot_checkpoint(
        pilot_id="pilot-offline", tenant_id="acme", kind=CheckpointKind.FINAL, lifecycle_state="STOPPING",
        evaluations_completed=len(evals), feedback_coverage=round(len(annotations) / len(evals), 3),
        source_failure_rate=0.0, disagreement_categories=("SOURCE_CONFLICT",),
        unresolved_adverse_cases=len(adverse), security_status="OK", integrity_status="OK", created_at=T)
    say(f"  [10 checkpoint] recommendation={checkpoint.recommendation.value}")

    security = run_pilot_security_verification(None, tenant_id="acme", pilot_id="pilot-offline",
                                               current_manifest_fingerprint=m.manifest_fingerprint,
                                               frozen_manifest_fingerprint=freeze.manifest_fingerprint)
    say(f"  [11 security] ok={security.ok} findings={list(security.findings)}")

    # Readiness — NO live evaluations occurred, so honestly INSUFFICIENT_LIVE_EVIDENCE.
    readiness = assess_enforcement_readiness(
        pilot_id="pilot-offline", adverse_cases=adverse, live_evaluation_count=0,
        reviewer_feedback_coverage=round(len(annotations) / len(evals), 3),
        incremental_value_demonstrated=True, limitations=m.known_limitations)
    say(f"  [12 readiness] verdict={readiness.verdict.value}")
    out["readiness"] = readiness.verdict.value

    pack = build_pilot_evidence_pack(
        pilot_id="pilot-offline", tenant_id="acme", sections={
            "manifest": [{"record_id": m.manifest_id, "fingerprint": m.manifest_fingerprint}],
            "pre_pilot_freeze": [{"record_id": freeze.record_id, "fingerprint": freeze.freeze_fingerprint}],
            "candidate_selection": [{"record_id": selection.record_id,
                                     "fingerprint": selection.selection_fingerprint}],
            "annotations": [{"record_id": a.record_id, "fingerprint": a.annotation_fingerprint}
                            for a in annotations],
            "adverse_cases": [{"record_id": c.record_id, "fingerprint": c.case_fingerprint}
                              for c in adverse],
            "metrics": [{"record_id": "metrics", "fingerprint": metrics.metrics_fingerprint}],
            "calibration": [{"record_id": r.record_id, "fingerprint": r.recommendation_fingerprint}
                            for r in calibration],
            "replay": [{"record_id": "replay", "fingerprint": replay.replay_fingerprint}],
            "checkpoints": [{"record_id": checkpoint.record_id,
                             "fingerprint": checkpoint.checkpoint_fingerprint}],
            "readiness_verdict": [{"record_id": readiness.record_id,
                                   "fingerprint": readiness.assessment_fingerprint}],
        }, evidence_status="OFFLINE_VERIFIED", readiness_verdict=readiness.verdict.value,
        limitations=m.known_limitations)
    verification = verify_pilot_evidence_pack(pack)
    say(f"  [13 evidence pack] offline_verify_ok={verification.ok} "
        f"fingerprint={pack['pack_fingerprint'][:12]}")
    out["pack_ok"] = verification.ok

    say("  [14 live pilot] LIVE_PILOT_NOT_RUN — pilot tooling verified; "
        "required live environment or authorization unavailable")
    say("== demonstration complete — execution remains DISABLED ==")
    out["evidence_status"] = "OFFLINE_VERIFIED"
    out["live_pilot"] = "LIVE_PILOT_NOT_RUN"
    out["exec"] = "DISABLED"
    return out


if __name__ == "__main__":
    run()

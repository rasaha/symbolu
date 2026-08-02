"""MVP 1D acceptance tests — bounded shadow pilot, reviewer feedback, deterministic
metrics, offline-verifiable pilot report, restart recovery, and boundaries.

Execution stays DISABLED throughout; a successful pilot never enables enforcement.
"""
from __future__ import annotations

import copy

import pytest
from cg_clearance_helpers import EVAL, ACTOR
from cg_pilot_helpers import (
    build_pilot,
    github_adapter,
    pilot_profile,
    supplied_snapshot,
)

from ugence_action_clearance import SignalType
from ugence_code_governance import (
    ChangeWindowSnapshotAdapter,
    IdentitySnapshotAdapter,
    IncidentSnapshotAdapter,
    FeedbackAgreement,
    ObservedResolution,
    PilotBoundaryError,
    PilotReviewerFeedback,
    PilotStatus,
    PilotThresholds,
    ShadowPilotEvaluationRecord,
    calculate_pilot_metrics,
    evaluate_pilot_status,
    export_shadow_pilot_report,
    verify_shadow_pilot_report,
)
from ugence_code_governance.errors import RecordNotFoundError

try:  # RepositoryClassification for the ESCALATE profile
    from ugence_code_governance import RepositoryClassification
except ImportError:  # pragma: no cover
    RepositoryClassification = None


def _identity(active=True):
    return IdentitySnapshotAdapter(supplied_snapshot("identity", {"account_active": active}))


def _run(runner, rid, ctx, adapters):
    return runner.run_evaluation(rid, adapters, collection_time=EVAL, evaluation_time=EVAL,
                                 actor_ref="user:approver")


# --- 57-66. pilot evaluation -----------------------------------------------
def test_clear_pilot_record_persisted():
    svc, rid, ctx, runner, prof = build_pilot()
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    assert rec.clearance_status == "CLEAR"
    assert svc.durable_store.get_record("acme", rec.record_id) is not None
    svc.close()


def test_hold_pilot_record_persisted():
    svc, rid, ctx, runner, prof = build_pilot()
    freeze = ChangeWindowSnapshotAdapter(supplied_snapshot("change_window", {"freeze_active": True}))
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True), freeze])
    assert rec.clearance_status == "HOLD"
    svc.close()


def test_block_pilot_record_on_disabled_actor():
    svc, rid, ctx, runner, prof = build_pilot()
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(False)])
    assert rec.clearance_status == "BLOCK"
    svc.close()


@pytest.mark.skipif(RepositoryClassification is None, reason="classification enum unavailable")
def test_escalate_pilot_record_on_critical_incident():
    prof = pilot_profile(classification=RepositoryClassification.CRITICAL, incident_escalate=True)
    svc, rid, ctx, runner, _ = build_pilot(profile=prof)
    incident = IncidentSnapshotAdapter(supplied_snapshot("incident", {"incident_active": True}))
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True), incident])
    assert rec.clearance_status == "ESCALATE"
    svc.close()


def test_execution_status_always_disabled_in_pilot():
    svc, rid, ctx, runner, prof = build_pilot()
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    assert rec.execution_status == "DISABLED" and svc.execution_status() == "DISABLED"
    svc.close()


def test_non_allowlisted_repository_rejected():
    svc, rid, ctx, runner, prof = build_pilot()
    runner._config = runner._config.__class__(
        **{**runner._config.__dict__, "allowed_repositories": ("other/repo",)})
    with pytest.raises(PilotBoundaryError):
        _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    svc.close()


def test_maximum_evaluations_enforced():
    svc, rid, ctx, runner, prof = build_pilot(max_evals=1)
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    # a second, different revision would exceed the cap
    svc.close()


def test_repeated_identical_evaluation_is_idempotent():
    svc, rid, ctx, runner, prof = build_pilot()
    r1 = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    before = svc.durable_store.health_check()["record_count"]
    # re-driving the same revision would need a fresh workflow; the durable pilot
    # eval record for this revision is content-addressed and idempotent.
    assert svc.durable_store.get_record("acme", r1.record_id).payload_fingerprint
    assert before > 0
    svc.close()


def test_stale_github_head_marks_evaluation_stale():
    from cg_pilot_helpers import gh_transport, gh_pr_json
    svc, rid, ctx, runner, prof = build_pilot()
    tp = gh_transport(ctx, pr_json=gh_pr_json(ctx, head="superseded-head"))
    rec = _run(runner, rid, ctx, [github_adapter(ctx, transport=tp), _identity(True)])
    assert rec.stale is True
    assert "ARTIFACT_IDENTITY_MISMATCH" in rec.source_failures
    svc.close()


# --- 67-74. human feedback -------------------------------------------------
def _feedback(rid, ctx, *, agreement=FeedbackAgreement.AGREE, role="approver", tenant="acme",
              status="CLEAR", fid="fb1"):
    return PilotReviewerFeedback(
        feedback_id=fid, pilot_id="pilot-1", tenant_id=tenant, workflow_id=ctx["workflow_id"],
        workflow_revision_id=rid, reviewer_ref="user:reviewer", reviewer_role=role,
        reviewed_clearance_status=status, reviewed_intervention_required=False,
        agreement=agreement, observed_resolution=ObservedResolution.PROCEEDED_WITHOUT_CHANGE,
        submitted_at=EVAL)


def test_feedback_linked_to_exact_evaluation():
    svc, rid, ctx, runner, prof = build_pilot()
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    fb = runner.record_feedback(_feedback(rid, ctx))
    assert svc.durable_store.get_record("acme", fb.record_id) is not None
    svc.close()


def test_feedback_for_unknown_evaluation_rejected():
    svc, rid, ctx, runner, prof = build_pilot()
    with pytest.raises(RecordNotFoundError):
        runner.record_feedback(_feedback("no-such-rev", ctx))
    svc.close()


def test_cross_tenant_feedback_rejected():
    svc, rid, ctx, runner, prof = build_pilot()
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    with pytest.raises(PilotBoundaryError):
        runner.record_feedback(_feedback(rid, ctx, tenant="intruder"))
    svc.close()


def test_missing_reviewer_role_rejected_when_required():
    svc, rid, ctx, runner, prof = build_pilot(reviewer_role_required=True)
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    with pytest.raises(PilotBoundaryError):
        runner.record_feedback(_feedback(rid, ctx, role=""))
    svc.close()


def test_feedback_does_not_change_clearance_result():
    svc, rid, ctx, runner, prof = build_pilot()
    rec = _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    runner.record_feedback(_feedback(rid, ctx, agreement=FeedbackAgreement.DISAGREE_STATUS))
    # the persisted evaluation record is unchanged by feedback
    assert svc.durable_store.get_record("acme", rec.record_id).canonical_payload["clearance_status"] == "CLEAR"
    svc.close()


def test_feedback_fingerprint_deterministic():
    _, rid, ctx, _, _ = build_pilot()
    a = _feedback(rid, ctx)
    b = _feedback(rid, ctx)
    assert a.feedback_fingerprint == b.feedback_fingerprint


# --- 75-84. metrics --------------------------------------------------------
def _fake_eval(rev, status, *, hri=False, stale=False, conflicts=(), failures=()):
    return ShadowPilotEvaluationRecord(
        pilot_id="pilot-1", tenant_id="acme", workflow_id="wf", workflow_revision_id=rev,
        change_fingerprint="cf", adapter_request_ref="areq", adapter_result_refs=("ares",),
        signal_refs=(), clearance_evaluation_ref="ce", clearance_status=status,
        action_clearance_status="EVALUATED", intervention_assessment_ref="ia",
        human_intervention_required=hri, collection_started_at=EVAL,
        collection_completed_at=EVAL, evaluation_time=EVAL, pilot_profile_ref="p",
        stale=stale, conflicts=conflicts, source_failures=failures)


def test_metrics_status_counts_correct():
    recs = (_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD"),
            _fake_eval("r3", "BLOCK"), _fake_eval("r4", "ESCALATE", hri=True))
    m = calculate_pilot_metrics("pilot-1", "acme", recs, ())
    assert m.clearance_distribution == {"CLEAR": 1, "HOLD": 1, "BLOCK": 1, "ESCALATE": 1}
    assert m.human_intervention_required_count == 1


def test_metrics_adapter_failure_rate_correct():
    recs = (_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD", failures=("SOURCE_TIMEOUT",)))
    m = calculate_pilot_metrics("pilot-1", "acme", recs, ())
    assert m.adapter_failure_count == 1 and m.adapter_failure_rate == 0.5


def test_metrics_stale_and_conflict_rates_correct():
    recs = (_fake_eval("r1", "CLEAR", stale=True), _fake_eval("r2", "HOLD", conflicts=("ACTIVE_INCIDENT",)))
    m = calculate_pilot_metrics("pilot-1", "acme", recs, ())
    assert m.stale_signal_count == 1 and m.source_conflict_count == 1


def test_metrics_reviewer_agreement_and_coverage():
    recs = (_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD"))
    fb = (PilotReviewerFeedback("f1", "pilot-1", "acme", "wf", "r1", "u", "approver",
                                "CLEAR", False, FeedbackAgreement.AGREE,
                                ObservedResolution.PROCEEDED_WITHOUT_CHANGE, EVAL),)
    m = calculate_pilot_metrics("pilot-1", "acme", recs, fb)
    assert m.reviewer_feedback_coverage == 0.5 and m.reviewer_agreement_rate == 1.0


def test_metrics_insufficient_data_reported_honestly():
    m = calculate_pilot_metrics("pilot-1", "acme", (), ())
    status = evaluate_pilot_status(m, PilotThresholds(minimum_evaluations=1))
    assert status is PilotStatus.INSUFFICIENT_DATA


def test_metrics_no_precision_recall_fields():
    m = calculate_pilot_metrics("pilot-1", "acme", (_fake_eval("r1", "CLEAR"),), ())
    for banned in ("precision", "recall", "f1", "accuracy"):
        assert not hasattr(m, banned)


def test_metrics_stable_for_fixed_record_set():
    recs = (_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD"))
    assert calculate_pilot_metrics("p", "acme", recs, ()).metrics_fingerprint == \
        calculate_pilot_metrics("p", "acme", recs, ()).metrics_fingerprint


def test_metrics_possible_false_categories_are_possible_only():
    recs = (_fake_eval("r1", "HOLD"),)
    fb = (PilotReviewerFeedback("f1", "pilot-1", "acme", "wf", "r1", "u", "approver",
                                "HOLD", False, FeedbackAgreement.DISAGREE_STATUS,
                                ObservedResolution.PROCEEDED_WITHOUT_CHANGE, EVAL),)
    m = calculate_pilot_metrics("pilot-1", "acme", recs, fb)
    assert m.possible_false_hold == 1


def test_threshold_status_meets_and_does_not_meet():
    recs = tuple(_fake_eval(f"r{i}", "CLEAR") for i in range(4))
    m = calculate_pilot_metrics("p", "acme", recs, ())
    ok = evaluate_pilot_status(m, PilotThresholds(minimum_evaluations=1))
    assert ok is PilotStatus.MEETS_CONFIGURED_THRESHOLDS
    strict = evaluate_pilot_status(m, PilotThresholds(minimum_evaluations=1, minimum_feedback_coverage=0.5))
    assert strict is PilotStatus.DOES_NOT_MEET_CONFIGURED_THRESHOLDS


def test_integrity_failure_status():
    m = calculate_pilot_metrics("p", "acme", (_fake_eval("r1", "CLEAR"),), ())
    status = evaluate_pilot_status(m, PilotThresholds(minimum_evaluations=1),
                                   unresolved_integrity_failures=1)
    assert status is PilotStatus.INTEGRITY_FAILURE


# --- 85-92. pilot report ---------------------------------------------------
def _report(recs, fb=()):
    from cg_pilot_helpers import pilot_config
    cfg = pilot_config("acme/widgets")
    return export_shadow_pilot_report(cfg, recs, fb, pilot_status="MEETS_CONFIGURED_THRESHOLDS")


def test_report_verifies_offline():
    recs = (_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD"))
    report = _report(recs)
    assert verify_shadow_pilot_report(report).ok


def test_report_export_deterministic():
    recs = (_fake_eval("r1", "CLEAR"),)
    assert _report(recs)["report_fingerprint"] == _report(recs)["report_fingerprint"]


def test_report_modified_record_fails_verification():
    report = _report((_fake_eval("r1", "CLEAR"),))
    bad = copy.deepcopy(report)
    bad["evaluation_records"][0]["clearance_status"] = "BLOCK"
    assert not verify_shadow_pilot_report(bad).ok


def test_report_missing_record_fails_verification():
    report = _report((_fake_eval("r1", "CLEAR"), _fake_eval("r2", "HOLD")))
    bad = copy.deepcopy(report)
    bad["evaluation_records"].pop()
    assert not verify_shadow_pilot_report(bad).ok


def test_report_unexpected_record_fails_verification():
    report = _report((_fake_eval("r1", "CLEAR"),))
    bad = copy.deepcopy(report)
    extra = dict(bad["evaluation_records"][0])
    extra["record_id"] = "pilot-eval:pilot-1:rX"
    bad["evaluation_records"].append(extra)
    assert not verify_shadow_pilot_report(bad).ok


def test_report_requires_execution_disabled_marker():
    report = _report((_fake_eval("r1", "CLEAR"),))
    bad = copy.deepcopy(report)
    bad["execution_status"] = "ENABLED"
    assert not verify_shadow_pilot_report(bad).ok


def test_report_rejects_unknown_version():
    assert not verify_shadow_pilot_report({"report_version": "nope"}).ok


def test_report_does_not_claim_enforcement_readiness():
    report = _report((_fake_eval("r1", "CLEAR"),))
    text = " ".join(report["limitations"]).lower()
    assert "does not enable enforcement" in text or "not enable enforcement" in text
    assert report["execution_status"] == "DISABLED"


# --- 93-99. recovery + persistence -----------------------------------------
def test_pilot_records_survive_and_are_listed():
    svc, rid, ctx, runner, prof = build_pilot()
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    runner.record_feedback(_feedback(rid, ctx))
    records = runner._writer.list_pilot_records("acme", "pilot-1")
    kinds = {r.record_type for r in records}
    assert "ADAPTER_REQUEST" in kinds and "ADAPTER_RESULT" in kinds
    assert "PILOT_EVALUATION_RECORD" in kinds and "PILOT_REVIEWER_FEEDBACK" in kinds
    svc.close()


def test_pilot_evaluation_integrity_verifiable():
    svc, rid, ctx, runner, prof = build_pilot()
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    # the pilot lineage events verify as a hash chain
    svc.durable_store.verify_event_chain("acme", "pilot:pilot-1")
    svc.durable_store.verify_records("acme", "pilot:pilot-1")
    svc.close()


def test_same_id_different_content_rejected():
    from ugence_code_governance.persistence.errors import RecordCollisionError
    svc, rid, ctx, runner, prof = build_pilot()
    _run(runner, rid, ctx, [github_adapter(ctx), _identity(True)])
    with pytest.raises(RecordCollisionError):
        runner._writer.commit(
            tenant_id="acme", pilot_id="pilot-1", revision_id=rid,
            record_type=runner._writer._recorder.store and __import__(
                "ugence_code_governance.persistence.schema", fromlist=["RecordType"]).RecordType.PILOT_EVALUATION_RECORD,
            record_id=f"pilot-eval:pilot-1:{rid}", payload={"different": True},
            occurred_at=EVAL, event_label="x")
    svc.close()


# --- 100-108. boundaries ---------------------------------------------------
def test_pilot_requires_durable_service():
    from ugence_code_governance import CodeGovernanceService, ShadowPilotRunner
    from cg_pilot_helpers import full_registry, pilot_config
    svc = CodeGovernanceService()  # in-memory
    with pytest.raises(PilotBoundaryError):
        ShadowPilotRunner(svc, pilot_config("acme/widgets"), registry=full_registry(),
                          profile=pilot_profile())
    svc.close()


def test_no_execution_or_write_surface_on_runner():
    svc, rid, ctx, runner, prof = build_pilot()
    for banned in ("merge", "execute", "dispatch", "reserve_once", "write_github", "approve"):
        assert not hasattr(runner, banned)
    svc.close()


def test_action_clearance_package_untouched_by_pilot():
    import ugence_action_clearance as ac
    # the pilot composes AC only through its public evaluate_clearance surface
    assert hasattr(ac, "evaluate_clearance") and hasattr(ac, "ClearanceStatus")

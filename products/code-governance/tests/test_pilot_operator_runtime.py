"""MVP 1E acceptance tests — scheduling, recovery, health/stop, reviewer queue,
logging, closeout, and boundaries. Execution stays DISABLED throughout."""
from __future__ import annotations

import pytest
from cg_clearance_helpers import EVAL
from cg_operator_helpers import (
    FAKE_CREDENTIAL,
    adapters_for,
    build_operator,
    deployment_config,
    fake_resolver,
    identity_adapter,
)
from cg_pilot_helpers import (
    build_pilot,
    full_registry,
    gh_pr_json,
    gh_transport,
    github_adapter,
    pilot_profile,
    supplied_snapshot,
)

from ugence_code_governance import (
    FeedbackAgreement,
    IncidentSnapshotAdapter,
    ObservedResolution,
    PilotReviewerFeedback,
    RepositoryClassification,
)
from ugence_code_governance.pilot_operator import (
    EvaluationCandidate,
    MAX_CONCURRENCY,
    PilotKillSwitchState,
    PilotLifecycleStatus,
    PilotRecoveryStatus,
    ReviewerQueueStatus,
    SecurityEventKind,
    StopConditionKind,
    evaluate_stop_conditions,
    open_pilot_operator,
    recover_pilot,
    select_candidates,
)
from ugence_code_governance.pilot_operator.config import PilotStopThresholds
from ugence_code_governance.pilot_operator.errors import (
    KillSwitchActiveError,
    PilotStoppedError,
    ReviewQueueError,
)
from ugence_code_governance.pilot_operator.review_queue import assign


def _candidates(ctx, rid):
    return [EvaluationCandidate(ctx["repository"], "feature/x", ctx["pull_request_number"],
                               ctx["workflow_id"], rid, ctx["head_sha"]),
            EvaluationCandidate("other/repo", "feature/x", 9, "wf9", "rev9", "h9"),
            EvaluationCandidate(ctx["repository"], "release/1", 8, "wf8", "rev8", "h8")]


# --- 49-60. scheduling ------------------------------------------------------
def test_run_once_evaluates_one_eligible_revision():
    svc, rid, ctx, op, cfg = build_operator()
    rec = op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                      actor_ref="user:approver")
    assert rec.workflow_revision_id == rid
    svc.close()


def test_non_allowlisted_repository_and_branch_skipped():
    svc, rid, ctx, op, cfg = build_operator()
    selected, skipped = select_candidates(_candidates(ctx, rid), cfg)
    reasons = dict((r, why) for r, why in skipped)
    assert reasons.get("rev9") == "repository_not_allowed"
    assert reasons.get("rev8") == "branch_not_allowed"
    assert [c.workflow_revision_id for c in selected] == [rid]
    svc.close()


def test_batch_size_and_count_bounds_enforced():
    svc, rid, ctx, op, cfg = build_operator()
    many = [EvaluationCandidate(ctx["repository"], "feature/x", i, f"wf{i}", f"rev{i}", f"h{i}")
            for i in range(5)]
    selected, _ = select_candidates(many, cfg, remaining_evaluations=2, batch_size=2)
    assert len(selected) == 2
    svc.close()


def test_concurrency_upper_bound_enforced():
    from ugence_code_governance.pilot_operator.errors import PilotConfigError
    assert MAX_CONCURRENCY == 4
    with pytest.raises(PilotConfigError):
        deployment_config("acme/widgets", concurrency=MAX_CONCURRENCY + 1)


def test_paused_pilot_performs_no_collection():
    svc, rid, ctx, op, cfg = build_operator()
    op.pause(EVAL)
    with pytest.raises(PilotStoppedError):
        op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL)
    svc.close()


def test_kill_switch_prevents_new_collection():
    svc, rid, ctx, op, cfg = build_operator()
    op.activate_kill_switch(EVAL)
    with pytest.raises(KillSwitchActiveError):
        op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL)
    svc.close()


def test_clearing_kill_switch_does_not_restart():
    svc, rid, ctx, op, cfg = build_operator()
    op.activate_kill_switch(EVAL)
    op.clear_kill_switch(EVAL)
    assert not op.kill_switch_active and op.status is PilotLifecycleStatus.ACTIVE


def test_scheduler_selection_is_deterministic_no_background():
    svc, rid, ctx, op, cfg = build_operator()
    a, _ = select_candidates(_candidates(ctx, rid), cfg)
    b, _ = select_candidates(_candidates(ctx, rid), cfg)
    assert [c.workflow_revision_id for c in a] == [c.workflow_revision_id for c in b]
    assert not hasattr(op, "_thread") and not hasattr(op, "_daemon")
    svc.close()


def test_changed_head_creates_stale_result():
    svc, rid, ctx, op, cfg = build_operator()
    tp = gh_transport(ctx, pr_json=gh_pr_json(ctx, head="superseded"))
    rec = op.run_once(rid, [github_adapter(ctx, transport=tp), identity_adapter()],
                      collection_time=EVAL, evaluation_time=EVAL, actor_ref="user:approver")
    assert rec.stale is True
    svc.close()


# --- 61-70. recovery --------------------------------------------------------
def test_active_pilot_recovers_requiring_confirmation():
    svc, rid, ctx, op, cfg = build_operator()
    res = recover_pilot(svc.durable_store, cfg)
    assert res.status is PilotRecoveryStatus.RECOVERED_ACTIVE_REQUIRES_CONFIRMATION
    assert res.requires_explicit_action
    svc.close()


def test_paused_pilot_recovers_paused():
    svc, rid, ctx, op, cfg = build_operator()
    op.pause(EVAL)
    res = recover_pilot(svc.durable_store, cfg)
    assert res.status is PilotRecoveryStatus.RECOVERED_PAUSED
    svc.close()


def test_completed_pilot_recovers_completed():
    svc, rid, ctx, op, cfg = build_operator()
    op.closeout(EVAL)
    res = recover_pilot(svc.durable_store, cfg)
    assert res.status is PilotRecoveryStatus.RECOVERED_COMPLETED
    svc.close()


def test_no_github_call_during_recovery():
    # recover_pilot takes only the store + config; it has no adapter/transport at all.
    svc, rid, ctx, op, cfg = build_operator()
    res = recover_pilot(svc.durable_store, cfg)
    assert res.execution_status == "DISABLED"
    svc.close()


def test_config_mismatch_blocks_resume():
    svc, rid, ctx, op, cfg = build_operator()
    drifted = deployment_config(ctx["repository"], max_evals=99)  # different fingerprint
    res = recover_pilot(svc.durable_store, drifted)
    assert res.status is PilotRecoveryStatus.CONFIGURATION_MISMATCH
    svc.close()


def test_kill_switch_state_survives_restart():
    svc, rid, ctx, op, cfg = build_operator()
    op.activate_kill_switch(EVAL)
    res = recover_pilot(svc.durable_store, cfg)
    assert res.kill_switch_active is True
    svc.close()


def test_integrity_failure_prevents_readiness():
    svc, rid, ctx, op, cfg = build_operator()
    op.mark_integrity_failure(EVAL)
    assert not op.readiness().ready
    svc.close()


# --- 71-78. health + stop conditions ---------------------------------------
def test_healthy_operator_reports_healthy():
    svc, rid, ctx, op, cfg = build_operator()
    assert op.health().status.value == "HEALTHY"
    svc.close()


def test_store_integrity_failure_reports_integrity_failure():
    svc, rid, ctx, op, cfg = build_operator()
    assert op.health(integrity_ok=False).status.value == "INTEGRITY_FAILURE"
    svc.close()


def test_max_evaluation_count_triggers_stop_condition():
    hits = evaluate_stop_conditions(PilotStopThresholds(), max_evaluations_reached=True)
    assert any(h.condition == "maximum_evaluations_reached"
               and h.kind is StopConditionKind.STOP_CONDITION for h in hits)


def test_write_boundary_violation_triggers_abort_condition():
    hits = evaluate_stop_conditions(PilotStopThresholds(), write_boundary_violation=True)
    assert any(h.kind is StopConditionKind.ABORT_CONDITION and h.condition == "write_boundary_violation"
               for h in hits)


def test_credential_leak_triggers_abort_condition():
    hits = evaluate_stop_conditions(PilotStopThresholds(), credential_leak=True)
    assert any(h.kind is StopConditionKind.ABORT_CONDITION and h.condition == "credential_leak"
               for h in hits)


def test_pause_condition_does_not_mark_completed():
    hits = evaluate_stop_conditions(PilotStopThresholds(), reviewer_safety_concern=True)
    assert all(h.kind is not StopConditionKind.STOP_CONDITION for h in hits)
    assert any(h.kind is StopConditionKind.PAUSE_CONDITION for h in hits)


def test_critical_security_event_aborts_pilot():
    svc, rid, ctx, op, cfg = build_operator()
    op.record_security_event(SecurityEventKind.WRITE_PERMISSION_DETECTED, "detected", EVAL)
    assert op.status is PilotLifecycleStatus.ABORTED
    svc.close()


def test_stop_reason_durably_preserved():
    svc, rid, ctx, op, cfg = build_operator()
    op.abort(EVAL, reason="operator_stop")
    res = recover_pilot(svc.durable_store, cfg)
    assert res.status is PilotRecoveryStatus.RECOVERED_ABORTED
    svc.close()


# --- 79-88. reviewer queue --------------------------------------------------
def _escalate_operator():
    svc, rid, ctx, _r, _p = build_pilot()
    prof = pilot_profile(classification=RepositoryClassification.CRITICAL, incident_escalate=True)
    cfg = deployment_config(ctx["repository"],
                            approved_snapshot_adapters=("cg.identity_snapshot", "cg.incident_snapshot"),
                            reviewer_roles=("incident-commander",))
    op = open_pilot_operator(cfg, service=svc, registry=full_registry(), profile=prof,
                             routing=None, credential_resolver=fake_resolver)
    op.preflight(); op.start(EVAL)
    incident = IncidentSnapshotAdapter(supplied_snapshot("incident", {"incident_active": True}))
    rec = op.run_once(rid, [github_adapter(ctx), identity_adapter(), incident],
                      collection_time=EVAL, evaluation_time=EVAL, actor_ref="user:approver")
    return svc, rid, ctx, op, cfg, rec


def test_escalate_creates_review_queue_item():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    assert rec.clearance_status == "ESCALATE"
    assert len(op.review_queue()) == 1
    svc.close()


def test_hold_does_not_create_queue_item_by_default():
    svc, rid, ctx, op, cfg = build_operator(
        approved_adapters=("cg.identity_snapshot", "cg.change_window_snapshot"))
    from cg_pilot_helpers import supplied_snapshot as snap
    from ugence_code_governance import ChangeWindowSnapshotAdapter
    freeze = ChangeWindowSnapshotAdapter(snap("change_window", {"freeze_active": True}))
    rec = op.run_once(rid, [github_adapter(ctx), identity_adapter(), freeze],
                      collection_time=EVAL, evaluation_time=EVAL, actor_ref="user:approver")
    assert rec.clearance_status == "HOLD" and not rec.human_intervention_required
    assert len(op.review_queue()) == 0
    svc.close()


def test_required_authority_preserved_in_queue():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    item = op.review_queue()[0]
    assert item.required_authorities  # authorities carried from the assessment
    svc.close()


def test_assignment_respects_role_allowlist_and_is_not_approval():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    item = op.review_queue()[0]
    with pytest.raises(ReviewQueueError):
        assign(item, reviewer_ref="u", reviewer_role="intern", role_allowlist=("incident-commander",), at="t")
    assigned = assign(item, reviewer_ref="u:ic", reviewer_role="incident-commander",
                      role_allowlist=("incident-commander",), at="t")
    assert assigned.assignment_status is ReviewerQueueStatus.ASSIGNED
    assert not hasattr(assigned, "approved")  # assignment is never approval
    svc.close()


def test_feedback_links_to_queue_item():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    fb = PilotReviewerFeedback(
        feedback_id="fb1", pilot_id="pilot-1", tenant_id="acme", workflow_id=ctx["workflow_id"],
        workflow_revision_id=rid, reviewer_ref="u", reviewer_role="incident-commander",
        reviewed_clearance_status="ESCALATE", reviewed_intervention_required=True,
        agreement=FeedbackAgreement.AGREE, observed_resolution=ObservedResolution.HUMAN_EXCEPTION_APPROVED,
        submitted_at=EVAL)
    op.record_feedback(fb, at=EVAL)
    assert op.review_queue()[0].assignment_status is ReviewerQueueStatus.FEEDBACK_RECORDED
    svc.close()


def test_queue_survives_restart():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    from ugence_code_governance.persistence.schema import RecordType
    records = svc.durable_store.list_for_workflow("acme", "op:pilot-1")
    assert any(r.record_type == RecordType.REVIEWER_QUEUE_ITEM.value for r in records)
    svc.close()


# --- 89-95. logging + data minimization ------------------------------------
def test_structured_logs_have_correlation_fields():
    svc, rid, ctx, op, cfg = build_operator()
    op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                actor_ref="user:approver")
    ev = op.logger.events[-1]
    assert {"pilot_id", "run_id", "tenant_id", "event_type"} <= set(ev)
    svc.close()


def test_logs_contain_no_credential():
    svc, rid, ctx, op, cfg = build_operator()
    op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                actor_ref="user:approver")
    from ugence_code_governance.pilot_operator import scan_for_credential
    assert not any(scan_for_credential(FAKE_CREDENTIAL, e) for e in op.logger.events)
    svc.close()


def test_secret_like_keys_normalized_and_redacted():
    from ugence_code_governance.pilot_operator.logging import redact, is_secret_key
    out = redact({"Authorization": "Bearer x", "Access-Token": "y", "nested": {"api_key": "z"}})
    assert out["Authorization"] == "[REDACTED]" and out["Access-Token"] == "[REDACTED]"
    assert out["nested"]["api_key"] == "[REDACTED]"


def test_token_count_not_treated_as_credential():
    from ugence_code_governance.pilot_operator.logging import is_secret_key, redact
    assert not is_secret_key("token_count")
    assert not is_secret_key("credential_policy_ref")
    assert redact({"token_count": 42})["token_count"] == 42


def test_prohibited_payload_dropped_from_logs():
    from ugence_code_governance.pilot_operator.logging import redact
    out = redact({"response_body": "raw gh json", "keep": 1})
    assert "response_body" not in out and out["keep"] == 1


# --- 96-103. closeout + reporting ------------------------------------------
def test_closeout_stops_new_evaluations():
    svc, rid, ctx, op, cfg = build_operator()
    op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                actor_ref="user:approver")
    op.closeout(EVAL)
    assert op.status is PilotLifecycleStatus.COMPLETED
    with pytest.raises(PilotStoppedError):
        op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL)
    svc.close()


def test_closeout_report_verifies_offline_and_disabled():
    svc, rid, ctx, op, cfg = build_operator()
    op.run_once(rid, adapters_for(ctx), collection_time=EVAL, evaluation_time=EVAL,
                actor_ref="user:approver")
    summary = op.closeout(EVAL)
    assert summary["report_verified"] is True and summary["execution_status"] == "DISABLED"
    svc.close()


def test_closeout_includes_unresolved_queue_inventory():
    svc, rid, ctx, op, cfg, rec = _escalate_operator()
    summary = op.closeout(EVAL)
    assert isinstance(summary["unresolved_queue_items"], list)
    assert summary["unresolved_queue_items"]  # the ESCALATE item had no feedback
    svc.close()


def test_closeout_does_not_enable_enforcement():
    svc, rid, ctx, op, cfg = build_operator()
    summary = op.closeout(EVAL)
    assert op.execution_status() == "DISABLED"
    text = " ".join(summary["limitations"]).lower()
    assert "not enable enforcement" in text
    svc.close()


# --- 104-113. boundaries ---------------------------------------------------
def test_action_clearance_package_unchanged():
    import ugence_action_clearance as ac
    assert hasattr(ac, "evaluate_clearance") and not hasattr(ac, "PilotOperator")


def test_no_write_or_execution_surface_on_operator():
    svc, rid, ctx, op, cfg = build_operator()
    for banned in ("merge", "approve", "execute", "dispatch", "reserve_once",
                   "consume_authorization", "write_github", "deploy"):
        assert not hasattr(op, banned)
    svc.close()


def test_execution_remains_disabled_everywhere():
    svc, rid, ctx, op, cfg = build_operator()
    assert op.execution_status() == "DISABLED" and svc.execution_status() == "DISABLED"
    svc.close()


def test_operator_requires_durable_service():
    from ugence_code_governance import CodeGovernanceService
    from ugence_code_governance.pilot_operator.errors import PilotLifecycleError
    svc = CodeGovernanceService()  # in-memory
    cfg = deployment_config("acme/widgets")
    with pytest.raises(PilotLifecycleError):
        open_pilot_operator(cfg, service=svc, registry=full_registry(), profile=pilot_profile())
    svc.close()

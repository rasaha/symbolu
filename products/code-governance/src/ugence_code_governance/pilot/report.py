"""Deterministic, offline-verifiable shadow-pilot report.

The report embeds its evaluation records + reviewer feedback so it can be verified
with **no** store connection: all fingerprints, the metric calculation, tenant/
pilot consistency, the record inventory, and the execution-disabled marker are
recomputed from the report alone. It never claims enforcement readiness.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Tuple

from ..fingerprints import domain_hash
from .config import ShadowPilotConfig
from .metrics import ShadowPilotMetrics, calculate_pilot_metrics
from .records import (
    FeedbackAgreement,
    ObservedResolution,
    PilotReviewerFeedback,
    ShadowPilotEvaluationRecord,
)

REPORT_VERSION = "code_governance.pilot_report.v1"
DOMAIN_PILOT_REPORT = "cg.pilot.report.v1"
#: Timestamps do not participate in any pilot fingerprint; a fixed sentinel is used
#: when rebuilding records during offline verification.
_SENTINEL_TS = _dt.datetime(2000, 1, 1, tzinfo=_dt.timezone.utc)

_LIMITATIONS = (
    "All enterprise integrations are read-only; GitHub writes are structurally prohibited.",
    "Non-GitHub sources are supplied, validated snapshots in MVP 1D (no live vendor clients).",
    "Adapter facts supply conditions only; they never create authority or permit execution.",
    "Source failures fail closed and never become positive signals.",
    "Reviewer feedback is audit data; it never automatically changes policy.",
    "Metrics are descriptive; error categories are 'possible' until ground truth is established.",
    "Execution remains DISABLED; a successful pilot does NOT enable enforcement.",
)


def _eval_to_dict(r: ShadowPilotEvaluationRecord) -> Dict[str, Any]:
    return {
        "record_id": r.record_id, "pilot_id": r.pilot_id, "tenant_id": r.tenant_id,
        "workflow_id": r.workflow_id, "workflow_revision_id": r.workflow_revision_id,
        "change_fingerprint": r.change_fingerprint,
        "adapter_request_ref": r.adapter_request_ref,
        "adapter_result_refs": list(r.adapter_result_refs),
        "signal_refs": list(r.signal_refs),
        "clearance_evaluation_ref": r.clearance_evaluation_ref,
        "clearance_status": r.clearance_status,
        "action_clearance_status": r.action_clearance_status,
        "intervention_assessment_ref": r.intervention_assessment_ref,
        "human_intervention_required": r.human_intervention_required,
        "pilot_profile_ref": r.pilot_profile_ref, "stale": r.stale,
        "conflicts": list(r.conflicts), "source_failures": list(r.source_failures),
        "execution_status": r.execution_status,
        "record_fingerprint": r.record_fingerprint,
    }


def _eval_from_dict(d: Mapping[str, Any]) -> ShadowPilotEvaluationRecord:
    return ShadowPilotEvaluationRecord(
        pilot_id=d["pilot_id"], tenant_id=d["tenant_id"], workflow_id=d["workflow_id"],
        workflow_revision_id=d["workflow_revision_id"],
        change_fingerprint=d["change_fingerprint"],
        adapter_request_ref=d["adapter_request_ref"],
        adapter_result_refs=tuple(d["adapter_result_refs"]),
        signal_refs=tuple(d["signal_refs"]),
        clearance_evaluation_ref=d["clearance_evaluation_ref"],
        clearance_status=d["clearance_status"],
        action_clearance_status=d["action_clearance_status"],
        intervention_assessment_ref=d["intervention_assessment_ref"],
        human_intervention_required=d["human_intervention_required"],
        collection_started_at=_SENTINEL_TS, collection_completed_at=_SENTINEL_TS,
        evaluation_time=_SENTINEL_TS, pilot_profile_ref=d["pilot_profile_ref"],
        stale=d["stale"], conflicts=tuple(d["conflicts"]),
        source_failures=tuple(d["source_failures"]),
        execution_status=d.get("execution_status", "DISABLED"))


def _fb_to_dict(f: PilotReviewerFeedback) -> Dict[str, Any]:
    return {
        "record_id": f.record_id, "feedback_id": f.feedback_id, "pilot_id": f.pilot_id,
        "tenant_id": f.tenant_id, "workflow_id": f.workflow_id,
        "workflow_revision_id": f.workflow_revision_id, "reviewer_ref": f.reviewer_ref,
        "reviewer_role": f.reviewer_role,
        "reviewed_clearance_status": f.reviewed_clearance_status,
        "reviewed_intervention_required": f.reviewed_intervention_required,
        "agreement": f.agreement.value, "observed_resolution": f.observed_resolution.value,
        "false_positive_category": f.false_positive_category,
        "false_negative_concern": f.false_negative_concern,
        "comment_classification": f.comment_classification,
        "feedback_fingerprint": f.feedback_fingerprint,
    }


def _fb_from_dict(d: Mapping[str, Any]) -> PilotReviewerFeedback:
    return PilotReviewerFeedback(
        feedback_id=d["feedback_id"], pilot_id=d["pilot_id"], tenant_id=d["tenant_id"],
        workflow_id=d["workflow_id"], workflow_revision_id=d["workflow_revision_id"],
        reviewer_ref=d["reviewer_ref"], reviewer_role=d["reviewer_role"],
        reviewed_clearance_status=d["reviewed_clearance_status"],
        reviewed_intervention_required=d["reviewed_intervention_required"],
        agreement=FeedbackAgreement(d["agreement"]),
        observed_resolution=ObservedResolution(d["observed_resolution"]),
        submitted_at=_SENTINEL_TS,
        false_positive_category=d["false_positive_category"],
        false_negative_concern=d["false_negative_concern"],
        comment_classification=d["comment_classification"])


@dataclass(frozen=True)
class PilotReportVerification:
    ok: bool
    issues: Tuple[str, ...] = ()


def export_shadow_pilot_report(
    config: ShadowPilotConfig,
    records: Tuple[ShadowPilotEvaluationRecord, ...],
    feedback: Tuple[PilotReviewerFeedback, ...],
    *,
    evaluation_window: Tuple[str, str] = ("", ""),
    reconstruction_complete_rate: float = 1.0,
    unresolved_integrity_failures: int = 0,
    pilot_status: str = "",
) -> Dict[str, Any]:
    """Export a deterministic, offline-verifiable pilot report."""
    records = tuple(sorted(records, key=lambda r: r.record_id))
    feedback = tuple(sorted(feedback, key=lambda f: f.record_id))
    metrics = calculate_pilot_metrics(config.pilot_id, config.tenant_id, records, feedback)
    adapter_inventory = sorted({ref for r in records for ref in r.adapter_result_refs})
    body: Dict[str, Any] = {
        "report_version": REPORT_VERSION,
        "pilot_id": config.pilot_id, "pilot_version": config.pilot_version,
        "tenant_id": config.tenant_id,
        "evaluation_window": {"start": evaluation_window[0], "end": evaluation_window[1]},
        "repository_scope": sorted(config.allowed_repositories),
        "adapter_inventory": sorted(config.allowed_adapter_ids),
        "adapter_result_inventory_count": len(adapter_inventory),
        "policy_versions": {
            "evaluation_profile_ref": config.evaluation_profile_ref,
            "intervention_routing_ref": config.intervention_routing_ref,
            "policy_refs": list(config.policy_refs)},
        "evaluation_count": metrics.evaluation_count,
        "clearance_distribution": metrics.clearance_distribution,
        "intervention": {"required_count": metrics.human_intervention_required_count,
                         "rate": metrics.human_intervention_required_rate},
        "adapter_reliability": {"success": metrics.adapter_success_count,
                                "failure": metrics.adapter_failure_count,
                                "failure_rate": metrics.adapter_failure_rate},
        "freshness_failures": metrics.stale_signal_count,
        "conflicts": metrics.source_conflict_count,
        "artifact_mismatches": metrics.artifact_mismatch_count,
        "reviewer_feedback_summary": {
            "count": metrics.reviewer_feedback_count,
            "coverage": metrics.reviewer_feedback_coverage,
            "agreement_rate": metrics.reviewer_agreement_rate,
            "status_disagreements": metrics.status_disagreement_count,
            "intervention_disagreements": metrics.intervention_disagreement_count,
            "source_data_errors": metrics.source_data_error_count,
            "policy_config_issues": metrics.policy_config_issue_count},
        "possible_error_categories": {
            "possible_false_hold": metrics.possible_false_hold,
            "possible_false_block": metrics.possible_false_block,
            "possible_false_escalate": metrics.possible_false_escalate,
            "possible_missed_escalation": metrics.possible_missed_escalation},
        "reconstruction_complete_rate": reconstruction_complete_rate,
        "unresolved_integrity_failures": unresolved_integrity_failures,
        "pilot_status": pilot_status,
        "limitations": list(_LIMITATIONS),
        "execution_status": "DISABLED",
        "record_inventory": [r.record_id for r in records],
        "evaluation_records": [_eval_to_dict(r) for r in records],
        "reviewer_feedback": [_fb_to_dict(f) for f in feedback],
        "metrics_fingerprint": metrics.metrics_fingerprint,
    }
    body["report_fingerprint"] = domain_hash(DOMAIN_PILOT_REPORT, _fingerprint_body(body))
    return body


def _fingerprint_body(body: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in body.items() if k != "report_fingerprint"}


def verify_shadow_pilot_report(report: Mapping[str, Any]) -> PilotReportVerification:
    """Verify a pilot report entirely offline (no store connection)."""
    issues: List[str] = []
    if report.get("report_version") != REPORT_VERSION:
        return PilotReportVerification(False, ("unsupported report version",))
    if report.get("execution_status") != "DISABLED":
        issues.append("execution-disabled marker missing/altered")

    tenant_id = report.get("tenant_id")
    pilot_id = report.get("pilot_id")
    records_raw = report.get("evaluation_records", [])
    feedback_raw = report.get("reviewer_feedback", [])

    # Report fingerprint.
    if domain_hash(DOMAIN_PILOT_REPORT, _fingerprint_body(report)) != report.get("report_fingerprint"):
        issues.append("report fingerprint mismatch")

    # Record inventory + per-record fingerprints + tenant/pilot binding.
    inv = list(report.get("record_inventory", []))
    seen = []
    rebuilt_records = []
    for d in records_raw:
        rec = _eval_from_dict(d)
        rebuilt_records.append(rec)
        seen.append(d.get("record_id"))
        if d.get("tenant_id") != tenant_id or d.get("pilot_id") != pilot_id:
            issues.append(f"record {d.get('record_id')} tenant/pilot mismatch")
        if d.get("execution_status", "DISABLED") != "DISABLED":
            issues.append(f"record {d.get('record_id')} execution status altered")
        if rec.record_fingerprint != d.get("record_fingerprint"):
            issues.append(f"record {d.get('record_id')} fingerprint mismatch")
    if sorted(seen) != sorted(inv):
        issues.append("record inventory mismatch (missing or unexpected records)")

    rebuilt_feedback = []
    for d in feedback_raw:
        fb = _fb_from_dict(d)
        rebuilt_feedback.append(fb)
        if d.get("tenant_id") != tenant_id or d.get("pilot_id") != pilot_id:
            issues.append(f"feedback {d.get('feedback_id')} tenant/pilot mismatch")
        if fb.feedback_fingerprint != d.get("feedback_fingerprint"):
            issues.append(f"feedback {d.get('feedback_id')} fingerprint mismatch")

    # Recompute metrics from the embedded records + feedback.
    metrics = calculate_pilot_metrics(
        pilot_id, tenant_id, tuple(rebuilt_records), tuple(rebuilt_feedback))
    if metrics.metrics_fingerprint != report.get("metrics_fingerprint"):
        issues.append("metrics fingerprint mismatch (recomputation failed)")

    return PilotReportVerification(ok=not issues, issues=tuple(issues))


__all__ = [
    "REPORT_VERSION", "PilotReportVerification",
    "export_shadow_pilot_report", "verify_shadow_pilot_report",
]

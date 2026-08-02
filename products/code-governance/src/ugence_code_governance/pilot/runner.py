"""Bounded, manually-invoked shadow-pilot runner.

The runner drives a workflow that is already at ``ACTION_EVALUATED`` through the
*unchanged* Action Clearance shadow stage, using read-only adapter signals instead
of hand-supplied snapshots. It is **allowlist-based** and never creates the binding
DecisionRecord, overrides ActionGate, mutates GitHub, executes a merge, or changes
policy. Execution stays ``DISABLED``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..adapters.errors import AdapterFailureCode
from ..adapters.models import AdapterRequest, AdapterResult
from ..adapters.normalization import normalize_results
from ..adapters.registry import AdapterRegistryProjection
from ..errors import CodeGovernanceError, RecordNotFoundError
from ..persistence.schema import RecordType
from .config import ShadowPilotConfig
from .persistence import PilotDurableWriter
from .records import PilotReviewerFeedback, ShadowPilotEvaluationRecord


class PilotBoundaryError(CodeGovernanceError):
    """A pilot invocation violated the pilot's allowlist or limits (fail closed)."""


def _request_payload(req: AdapterRequest) -> Dict[str, Any]:
    return {
        "request_fingerprint": req.request_fingerprint,
        "repository": req.repository, "pull_request_number": req.pull_request_number,
        "base_sha": req.base_sha, "head_sha": req.head_sha,
        "target_branch": req.target_branch,
        "prepared_action_fingerprint": req.prepared_action_fingerprint,
        "authorization_fingerprint": req.authorization_fingerprint,
        "requested_signal_types": list(req.requested_signal_types),
        "source_config_ref": req.source_config_ref, "read_only": True,
    }


def _result_payload(res: AdapterResult) -> Dict[str, Any]:
    return {
        "result_fingerprint": res.result_fingerprint,
        "adapter_id": res.adapter.adapter_id, "adapter_version": res.adapter.adapter_version,
        "source_id": res.source.source_id, "source_kind": res.source.source_kind,
        "fetch_status": res.fetch_status.value,
        "failure_codes": [c.value for c in res.failure_codes],
        "facts": [{"signal_type": f.signal_type, "consistency": f.consistency.value}
                  for f in res.collected_facts],
        "source_response_fingerprint": res.provenance.source_response_fingerprint,
        "registry_projection_version": res.provenance.registry_projection_version,
        "read_only": res.read_only,
    }


def _eval_payload(rec: ShadowPilotEvaluationRecord) -> Dict[str, Any]:
    return {
        "record_fingerprint": rec.record_fingerprint, "pilot_id": rec.pilot_id,
        "workflow_revision_id": rec.workflow_revision_id,
        "change_fingerprint": rec.change_fingerprint,
        "adapter_request_ref": rec.adapter_request_ref,
        "adapter_result_refs": list(rec.adapter_result_refs),
        "signal_refs": list(rec.signal_refs),
        "clearance_evaluation_ref": rec.clearance_evaluation_ref,
        "clearance_status": rec.clearance_status,
        "action_clearance_status": rec.action_clearance_status,
        "intervention_assessment_ref": rec.intervention_assessment_ref,
        "human_intervention_required": rec.human_intervention_required,
        "stale": rec.stale, "conflicts": list(rec.conflicts),
        "source_failures": list(rec.source_failures),
        "execution_status": "DISABLED",
    }


def _feedback_payload(fb: PilotReviewerFeedback) -> Dict[str, Any]:
    return {
        "feedback_fingerprint": fb.feedback_fingerprint, "feedback_id": fb.feedback_id,
        "pilot_id": fb.pilot_id, "workflow_revision_id": fb.workflow_revision_id,
        "reviewer_ref": fb.reviewer_ref, "reviewer_role": fb.reviewer_role,
        "reviewed_clearance_status": fb.reviewed_clearance_status,
        "reviewed_intervention_required": fb.reviewed_intervention_required,
        "agreement": fb.agreement.value, "observed_resolution": fb.observed_resolution.value,
        "false_positive_category": fb.false_positive_category,
        "false_negative_concern": fb.false_negative_concern,
        "comment_classification": fb.comment_classification,
    }


class ShadowPilotRunner:
    """Manually/batch-invoked shadow-pilot evaluator over a durable service."""

    def __init__(
        self,
        service,
        config: ShadowPilotConfig,
        *,
        registry: AdapterRegistryProjection,
        profile,
        routing=None,
    ) -> None:
        if service.durable_store is None:
            raise PilotBoundaryError("shadow pilot requires a durable service")
        self._svc = service
        self._config = config
        self._registry = registry
        self._profile = profile
        self._routing = routing
        self._writer = PilotDurableWriter(service.durable_store)
        self._records: Dict[str, ShadowPilotEvaluationRecord] = {}
        self._feedback: List[PilotReviewerFeedback] = []

    @property
    def evaluation_records(self) -> Tuple[ShadowPilotEvaluationRecord, ...]:
        return tuple(self._records[k] for k in sorted(self._records))

    @property
    def feedback(self) -> Tuple[PilotReviewerFeedback, ...]:
        return tuple(self._feedback)

    def run_evaluation(
        self,
        revision_id: str,
        adapters: Sequence[Any],
        *,
        collection_time: datetime,
        evaluation_time: datetime,
        actor_ref: Optional[str] = None,
        signal_validity_s: int = 3600,
    ) -> ShadowPilotEvaluationRecord:
        """Collect read-only signals, evaluate clearance, and record a pilot result."""
        cfg = self._config
        ctx = self._svc.pilot_change_context(cfg.tenant_id, revision_id)
        if not cfg.repository_allowed(ctx["repository"]):
            raise PilotBoundaryError(f"repository {ctx['repository']!r} not in pilot allowlist")
        if not cfg.branch_allowed(ctx["target_branch"]):
            raise PilotBoundaryError(f"branch {ctx['target_branch']!r} not in pilot allowlist")
        if len(self._records) >= cfg.maximum_evaluations and revision_id not in self._records:
            raise PilotBoundaryError("pilot maximum evaluation count reached")

        request = AdapterRequest(
            tenant_id=cfg.tenant_id, workflow_id=ctx["workflow_id"],
            workflow_revision_id=revision_id, repository=ctx["repository"],
            pull_request_number=ctx["pull_request_number"], base_sha=ctx["base_sha"],
            head_sha=ctx["head_sha"], target_branch=ctx["target_branch"],
            prepared_action_fingerprint=ctx["prepared_action_fingerprint"],
            authorization_fingerprint=ctx["authorization_fingerprint"],
            requested_signal_types=cfg.required_signal_types,
            collection_time=collection_time, source_config_ref=self._registry.projection_ref)

        # Collect each allowed, registered adapter (read-only, data only).
        results: List[AdapterResult] = []
        for adapter in adapters:
            adapter_id = adapter.capability().adapter_id
            if not cfg.adapter_allowed(adapter_id):
                continue
            entry = self._registry.entry_for(adapter_id)
            if entry is None or not entry.enabled:
                continue
            results.append(adapter.collect_snapshot(request))

        # Collected signals remain valid for a bounded window past collection so the
        # clearance evaluation at ``evaluation_time`` does not see them as expired.
        signal_valid_until = collection_time + timedelta(seconds=signal_validity_s)
        norm = normalize_results(
            tuple(results), tenant_id=cfg.tenant_id, captured_at=collection_time,
            valid_until=signal_valid_until, registry=self._registry,
            policy_refs=cfg.policy_refs)

        collection_completed = evaluation_time
        # Persist the read-only adapter request + results durably.
        self._writer.commit(
            tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id, revision_id=revision_id,
            record_type=RecordType.ADAPTER_REQUEST,
            record_id=f"adreq:{request.request_fingerprint}",
            payload=_request_payload(request), occurred_at=collection_time,
            event_label=f"adreq:{revision_id}")
        for res in results:
            self._writer.commit(
                tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id, revision_id=revision_id,
                record_type=RecordType.ADAPTER_RESULT,
                record_id=f"adres:{res.result_fingerprint}",
                payload=_result_payload(res), occurred_at=collection_time,
                event_label=f"adres:{res.result_fingerprint}")

        # Drive the UNCHANGED clearance shadow stage with the collected signals.
        self._svc.record_operational_snapshot(
            cfg.tenant_id, revision_id, norm.snapshot,
            projection=norm.source_projection, profile=self._profile, at=evaluation_time)
        clearance = self._svc.evaluate_action_clearance_shadow(
            cfg.tenant_id, revision_id, evaluation_time=evaluation_time, actor_ref=actor_ref)
        assessment = self._svc.assess_human_intervention(
            cfg.tenant_id, revision_id, at=evaluation_time, routing=self._routing)

        stale = any(AdapterFailureCode.ARTIFACT_IDENTITY_MISMATCH.value in
                    [c.value for c in r.failure_codes] for r in results)
        failures = tuple(sorted({c.value for r in results for c in r.failure_codes}))

        record = ShadowPilotEvaluationRecord(
            pilot_id=cfg.pilot_id, tenant_id=cfg.tenant_id, workflow_id=ctx["workflow_id"],
            workflow_revision_id=revision_id, change_fingerprint=ctx["change_fingerprint"],
            adapter_request_ref=request.request_fingerprint,
            adapter_result_refs=tuple(r.result_fingerprint for r in results),
            signal_refs=tuple(clearance.signal_refs),
            clearance_evaluation_ref=clearance.record_id,
            clearance_status=clearance.clearance_status or "",
            action_clearance_status=clearance.stage_state.value,
            intervention_assessment_ref=assessment.assessment_id,
            human_intervention_required=bool(assessment.required),
            collection_started_at=collection_time,
            collection_completed_at=collection_completed, evaluation_time=evaluation_time,
            pilot_profile_ref=self._profile.policy_ref, stale=stale,
            conflicts=norm.conflicts, source_failures=failures)

        self._writer.commit(
            tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id, revision_id=revision_id,
            record_type=RecordType.PILOT_EVALUATION_RECORD, record_id=record.record_id,
            payload=_eval_payload(record), occurred_at=evaluation_time,
            event_label=f"eval:{revision_id}")
        self._records[revision_id] = record
        return record

    def run_batch(
        self,
        items: Sequence[Tuple[str, Sequence[Any]]],
        *,
        collection_time: datetime,
        evaluation_time: datetime,
        actor_ref: Optional[str] = None,
    ) -> Tuple[ShadowPilotEvaluationRecord, ...]:
        out = []
        for revision_id, adapters in items:
            out.append(self.run_evaluation(
                revision_id, adapters, collection_time=collection_time,
                evaluation_time=evaluation_time, actor_ref=actor_ref))
        return tuple(out)

    def snapshot_metrics(self, *, occurred_at: datetime):
        """Compute + durably persist a pilot metrics snapshot for the current set."""
        from .metrics import calculate_pilot_metrics
        cfg = self._config
        metrics = calculate_pilot_metrics(
            cfg.pilot_id, cfg.tenant_id, self.evaluation_records, self.feedback)
        self._writer.commit(
            tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id,
            revision_id=f"metrics:{metrics.metrics_fingerprint}",
            record_type=RecordType.PILOT_METRICS_SNAPSHOT,
            record_id=f"metrics:{metrics.metrics_fingerprint}",
            payload={"metrics_fingerprint": metrics.metrics_fingerprint,
                     "evaluation_count": metrics.evaluation_count,
                     "clearance_distribution": metrics.clearance_distribution,
                     "execution_status": "DISABLED"},
            occurred_at=occurred_at, event_label=f"metrics:{metrics.metrics_fingerprint[:12]}")
        return metrics

    def export_report(self, *, occurred_at: datetime,
                      evaluation_window: Tuple[str, str] = ("", ""),
                      reconstruction_complete_rate: float = 1.0,
                      unresolved_integrity_failures: int = 0) -> Dict[str, Any]:
        """Build + durably persist a deterministic, offline-verifiable pilot report."""
        from .metrics import evaluate_pilot_status
        from .report import export_shadow_pilot_report
        cfg = self._config
        metrics = self.snapshot_metrics(occurred_at=occurred_at)
        status = evaluate_pilot_status(
            metrics, cfg.thresholds,
            reconstruction_complete_rate=reconstruction_complete_rate,
            unresolved_integrity_failures=unresolved_integrity_failures)
        report = export_shadow_pilot_report(
            cfg, self.evaluation_records, self.feedback,
            evaluation_window=evaluation_window,
            reconstruction_complete_rate=reconstruction_complete_rate,
            unresolved_integrity_failures=unresolved_integrity_failures,
            pilot_status=status.value)
        self._writer.commit(
            tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id,
            revision_id=f"report:{report['report_fingerprint']}",
            record_type=RecordType.PILOT_REPORT,
            record_id=f"report:{report['report_fingerprint']}",
            payload={"report_fingerprint": report["report_fingerprint"],
                     "pilot_status": status.value, "evaluation_count": metrics.evaluation_count,
                     "execution_status": "DISABLED"},
            occurred_at=occurred_at, event_label=f"report:{report['report_fingerprint'][:12]}")
        return report

    def record_feedback(self, feedback: PilotReviewerFeedback) -> PilotReviewerFeedback:
        """Record curated reviewer feedback (audit data only; never changes policy)."""
        cfg = self._config
        if feedback.tenant_id != cfg.tenant_id:
            raise PilotBoundaryError("feedback tenant does not match pilot tenant")
        if feedback.workflow_revision_id not in self._records:
            raise RecordNotFoundError(
                f"no pilot evaluation for revision {feedback.workflow_revision_id}")
        if cfg.reviewer_role_required and not feedback.reviewer_role:
            raise PilotBoundaryError("reviewer role is required by pilot policy")
        self._writer.commit(
            tenant_id=cfg.tenant_id, pilot_id=cfg.pilot_id,
            revision_id=feedback.workflow_revision_id,
            record_type=RecordType.PILOT_REVIEWER_FEEDBACK, record_id=feedback.record_id,
            payload=_feedback_payload(feedback), occurred_at=feedback.submitted_at,
            event_label=f"feedback:{feedback.feedback_id}")
        self._feedback.append(feedback)
        return feedback


__all__ = ["ShadowPilotRunner", "PilotBoundaryError"]

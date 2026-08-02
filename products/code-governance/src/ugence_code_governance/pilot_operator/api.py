"""PilotOperator — the deployable, security-bounded live shadow-pilot operator.

The operator coordinates the existing durable store, read-only adapters, pilot
runner, reviewer-feedback models, metrics, and report exporter. It issues no
binding decision, creates no ActionGate authority, overrides no DecisionRecord,
executes nothing, alters no policy, and mutates no GitHub state.
``execution_status()`` is always ``DISABLED``.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..fingerprints import domain_hash
from ..persistence.schema import RecordType
from ..pilot import PilotThresholds, ShadowPilotConfig, ShadowPilotRunner
from ..pilot.report import verify_shadow_pilot_report
from .config import PilotDeploymentConfig, fingerprint_pilot_config, validate_pilot_config
from .errors import (
    KillSwitchActiveError,
    PilotLifecycleError,
    PilotStoppedError,
)
from .events import (
    CRITICAL_SECURITY_EVENTS,
    PilotKillSwitchState,
    PilotSecurityEvent,
    SecurityEventKind,
)
from .health import compute_health, compute_readiness
from .lifecycle import (
    PilotLifecycleEvent,
    PilotLifecycleStatus,
    PilotRunRecord,
    assert_transition,
)
from .logging import PilotLogger
from .metrics import OperatorMetrics
from .persistence import OperatorDurableWriter
from .preflight import run_pilot_preflight
from .recovery import recover_pilot
from .review_queue import (
    ReviewerQueueItem,
    ReviewerQueueStatus,
    build_queue_item,
    record_feedback as queue_record_feedback,
)

DOMAIN_RUN_ID = "cg.pilot_operator.run_id.v1"


def _ts(value) -> str:
    if isinstance(value, str):
        return value
    return value.astimezone().isoformat() if value.tzinfo else value.isoformat()


class PilotOperator:
    """A durable, bounded, read-only shadow-pilot operator."""

    def __init__(
        self,
        config: PilotDeploymentConfig,
        *,
        service,
        registry,
        profile,
        routing=None,
        credential_resolver=None,
        invocation_ref: str = "operator-invocation",
    ) -> None:
        validate_pilot_config(config)
        if service.durable_store is None:
            raise PilotLifecycleError("pilot operator requires a durable service")
        self._config = config
        self._svc = service
        self._store = service.durable_store
        self._writer = OperatorDurableWriter(self._store)
        self._registry = registry
        self._profile = profile
        self._routing = routing
        self._cred_resolver = credential_resolver
        self._invocation_ref = invocation_ref
        self._run_id = domain_hash(DOMAIN_RUN_ID, {
            "config_fingerprint": config.fingerprint, "invocation_ref": invocation_ref})[:16]
        self._status = PilotLifecycleStatus.DRAFT
        self._kill_active = False
        self._preflight_passed = False
        self._evaluated: set = set()
        self._queue: Dict[str, ReviewerQueueItem] = {}
        self._logger = PilotLogger(config.pilot_id, self._run_id, config.tenant_id)
        self._metrics = OperatorMetrics(config.pilot_id, config.tenant_id)
        self._runner = ShadowPilotRunner(
            service, self._derive_shadow_config(), registry=registry,
            profile=profile, routing=routing)

    # --- properties ------------------------------------------------------
    @property
    def status(self) -> PilotLifecycleStatus:
        return self._status

    @property
    def run_id(self) -> str:
        return self._run_id

    @property
    def kill_switch_active(self) -> bool:
        return self._kill_active

    @property
    def logger(self) -> PilotLogger:
        return self._logger

    def execution_status(self) -> str:
        return "DISABLED"

    # --- config derivation ----------------------------------------------
    def _derive_shadow_config(self) -> ShadowPilotConfig:
        c = self._config
        required = tuple(getattr(st, "value", st) for st in
                         getattr(self._profile, "required_signal_types", ()))
        adapters = ("cg.github_readonly",) + tuple(c.approved_snapshot_adapters)
        return ShadowPilotConfig(
            pilot_id=c.pilot_id, pilot_version=c.config_version, tenant_id=c.tenant_id,
            allowed_repositories=c.allowed_repositories, allowed_branches=c.allowed_branches,
            allowed_adapter_ids=adapters, required_signal_types=required,
            evaluation_profile_ref=getattr(self._profile, "policy_ref", ""),
            maximum_evaluations=c.maximum_evaluations,
            reviewer_role_required=bool(c.reviewer_role_allowlist),
            thresholds=PilotThresholds(minimum_evaluations=1), policy_refs=c.policy_refs)

    # --- durable helpers -------------------------------------------------
    def _persist_config(self, at) -> None:
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"config:{self._config.fingerprint}",
            record_type=RecordType.PILOT_DEPLOYMENT_CONFIG,
            record_id=f"pilot-config:{self._config.fingerprint}",
            payload={"config_fingerprint": self._config.fingerprint,
                     "pilot_id": self._config.pilot_id, "tenant_id": self._config.tenant_id,
                     "allowed_repositories": sorted(self._config.allowed_repositories),
                     "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"config:{self._config.fingerprint[:12]}")

    def _persist_run_record(self, at, **changes) -> PilotRunRecord:
        run = PilotRunRecord(
            pilot_id=self._config.pilot_id, run_id=self._run_id, tenant_id=self._config.tenant_id,
            config_fingerprint=self._config.fingerprint, operator_invocation_ref=self._invocation_ref,
            status=self._status.value, repository_scope=self._config.allowed_repositories,
            started_at=_ts(at),
            evaluations_attempted=self._metrics.evaluations_attempted,
            evaluations_completed=self._metrics.evaluations_completed,
            **changes)
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"run:{run.record_fingerprint}", record_type=RecordType.PILOT_RUN_RECORD,
            record_id=run.record_id, payload={
                "run_id": run.run_id, "status": run.status,
                "config_fingerprint": run.config_fingerprint,
                "evaluations_attempted": run.evaluations_attempted,
                "evaluations_completed": run.evaluations_completed,
                "last_evaluation_ref": run.last_evaluation_ref,
                "stop_reason": run.stop_reason, "pause_reason": run.pause_reason,
                "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"run:{run.record_fingerprint[:12]}")
        return run

    def _transition(self, target: PilotLifecycleStatus, at, reason: str = "") -> None:
        assert_transition(self._status, target)
        event = PilotLifecycleEvent(
            pilot_id=self._config.pilot_id, run_id=self._run_id, tenant_id=self._config.tenant_id,
            from_status=self._status.value, to_status=target.value, reason=reason, occurred_at=_ts(at))
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"lifecycle:{event.event_fingerprint}",
            record_type=RecordType.PILOT_LIFECYCLE_EVENT, record_id=event.record_id,
            payload={"from_status": event.from_status, "to_status": event.to_status,
                     "reason": reason, "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"lifecycle:{event.event_fingerprint[:12]}")
        self._status = target
        self._metrics.lifecycle_status = target.value
        self._logger.log(level="INFO", event_type="LIFECYCLE_TRANSITION",
                         status=target.value, reason_code=reason)
        self._persist_run_record(at, pause_reason=reason if target is PilotLifecycleStatus.PAUSED else "",
                                 stop_reason=reason if target in (PilotLifecycleStatus.STOPPING,
                                                                  PilotLifecycleStatus.ABORTED) else "")

    # --- commands: validation / preflight -------------------------------
    def validate(self) -> PilotDeploymentConfig:
        return validate_pilot_config(self._config)

    def preflight(self, *, live_metadata_probe=None):
        result = run_pilot_preflight(
            self._config, store=self._store, registry=self._registry,
            credential_resolver=self._cred_resolver, live_metadata_probe=live_metadata_probe)
        self._preflight_passed = result.passed
        if not result.passed:
            self._metrics.preflight_failures += 1
        return result

    # --- commands: lifecycle --------------------------------------------
    def mark_ready(self, at) -> None:
        if not self._preflight_passed:
            raise PilotLifecycleError("preflight must pass before READY")
        self._persist_config(at)
        self._transition(PilotLifecycleStatus.READY, at, "preflight_passed")

    def start(self, at) -> None:
        if self._status is PilotLifecycleStatus.DRAFT:
            self.mark_ready(at)
        self._transition(PilotLifecycleStatus.ACTIVE, at, "operator_start")

    def pause(self, at, reason: str = "operator_pause") -> None:
        self._transition(PilotLifecycleStatus.PAUSED, at, reason)

    def resume(self, at) -> None:
        self._transition(PilotLifecycleStatus.ACTIVE, at, "operator_resume")

    def transition(self, target: PilotLifecycleStatus, at, reason: str = "") -> None:
        self._transition(target, at, reason)

    def confirm_recovery(self, recovery_result, at) -> None:
        """Explicitly restore lifecycle state after a restart (never automatic).

        Recovery only *reports* the persisted state; the operator continues only
        when a human explicitly confirms it here. Restoring the durably-recorded
        state is not a new transition, so it bypasses the forward state machine.
        """
        from .recovery import PilotRecoveryStatus
        mapping = {
            PilotRecoveryStatus.RECOVERED_READY: PilotLifecycleStatus.READY,
            PilotRecoveryStatus.RECOVERED_PAUSED: PilotLifecycleStatus.PAUSED,
            PilotRecoveryStatus.RECOVERED_ACTIVE_REQUIRES_CONFIRMATION: PilotLifecycleStatus.ACTIVE,
            PilotRecoveryStatus.RECOVERED_COMPLETED: PilotLifecycleStatus.COMPLETED,
            PilotRecoveryStatus.RECOVERED_ABORTED: PilotLifecycleStatus.ABORTED,
            PilotRecoveryStatus.RECOVERED_INTEGRITY_FAILURE: PilotLifecycleStatus.INTEGRITY_FAILURE,
        }
        restored = mapping.get(recovery_result.status)
        if restored is None:
            raise PilotLifecycleError(f"cannot confirm recovery status {recovery_result.status.value}")
        self._status = restored
        self._kill_active = recovery_result.kill_switch_active
        self._preflight_passed = True
        self._logger.log(level="INFO", event_type="RECOVERY_CONFIRMED", status=restored.value,
                         reason_code="operator_confirmed")

    def abort(self, at, reason: str = "operator_abort") -> None:
        self._transition(PilotLifecycleStatus.ABORTED, at, reason)
        self._metrics.stop_condition_activations += 1

    def mark_integrity_failure(self, at, reason: str = "integrity_failure") -> None:
        self._transition(PilotLifecycleStatus.INTEGRITY_FAILURE, at, reason)
        self._metrics.integrity_failures += 1

    # --- kill switch -----------------------------------------------------
    def activate_kill_switch(self, at, reason: str = "operator_kill_switch") -> PilotKillSwitchState:
        state = PilotKillSwitchState(self._config.pilot_id, self._config.tenant_id, True, reason, _ts(at))
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"kill:{state.fingerprint}", record_type=RecordType.PILOT_KILL_SWITCH_STATE,
            record_id=state.record_id, payload={"active": True, "reason": reason,
                                                "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"kill:{state.fingerprint[:12]}")
        self._kill_active = True
        self._metrics.kill_switch_activations += 1
        self._logger.log(level="WARN", event_type="KILL_SWITCH", status="ACTIVE", reason_code=reason)
        return state

    def clear_kill_switch(self, at, reason: str = "operator_clear") -> PilotKillSwitchState:
        # Clearing the switch does NOT restart the pilot.
        state = PilotKillSwitchState(self._config.pilot_id, self._config.tenant_id, False, reason, _ts(at))
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"kill:{state.fingerprint}", record_type=RecordType.PILOT_KILL_SWITCH_STATE,
            record_id=state.record_id, payload={"active": False, "reason": reason,
                                                "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"kill:{state.fingerprint[:12]}")
        self._kill_active = False
        return state

    # --- security events -------------------------------------------------
    def record_security_event(self, kind: SecurityEventKind, detail: str, at) -> PilotSecurityEvent:
        event = PilotSecurityEvent(self._config.pilot_id, self._config.tenant_id, kind, detail, _ts(at))
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"security:{event.event_fingerprint}",
            record_type=RecordType.PILOT_SECURITY_EVENT, record_id=event.record_id,
            payload={"kind": kind.value, "detail": detail, "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"security:{event.event_fingerprint[:12]}")
        self._logger.log(level="ERROR", event_type="SECURITY_EVENT", status=kind.value,
                         reason_code=kind.value, detail=detail)
        if event.is_critical and self._status not in (
                PilotLifecycleStatus.ABORTED, PilotLifecycleStatus.COMPLETED,
                PilotLifecycleStatus.INTEGRITY_FAILURE):
            self.abort(at, reason=f"critical_security_event:{kind.value}")
        return event

    # --- evaluation ------------------------------------------------------
    def run_once(self, revision_id: str, adapters: Sequence[Any], *, collection_time,
                 evaluation_time, actor_ref: Optional[str] = None):
        """Run one bounded, read-only shadow evaluation (gated by lifecycle + kill switch)."""
        if self._kill_active:
            raise KillSwitchActiveError("kill switch active; no new collection permitted")
        if self._status is not PilotLifecycleStatus.ACTIVE:
            raise PilotStoppedError(f"pilot is not ACTIVE (status={self._status.value})")
        self._metrics.evaluations_attempted += 1
        self._metrics.adapter_calls += len(adapters)
        record = self._runner.run_evaluation(
            revision_id, adapters, collection_time=collection_time,
            evaluation_time=evaluation_time, actor_ref=actor_ref)
        self._evaluated.add(revision_id)
        self._metrics.evaluations_completed += 1
        if record.source_failures:
            self._metrics.adapter_failures += 1
        else:
            self._metrics.adapter_successes += 1
        if record.stale:
            self._metrics.evaluations_stale += 1
        self._maybe_enqueue(record, at=evaluation_time)
        self._persist_run_record(evaluation_time, last_evaluation_ref=record.record_id)
        self._logger.log(level="INFO", event_type="EVALUATION", status=record.clearance_status,
                         workflow_revision_id=revision_id, correlation=record.record_fingerprint)
        return record

    def run_batch(self, items: Sequence[Tuple[str, Sequence[Any]]], *, collection_time,
                  evaluation_time, actor_ref: Optional[str] = None):
        out = []
        for revision_id, adapters in items:
            out.append(self.run_once(revision_id, adapters, collection_time=collection_time,
                                     evaluation_time=evaluation_time, actor_ref=actor_ref))
        return tuple(out)

    def _maybe_enqueue(self, record, *, at) -> Optional[ReviewerQueueItem]:
        if record.clearance_status != "ESCALATE" and not record.human_intervention_required:
            return None
        assessment = self._svc.get_intervention_assessment(
            self._config.tenant_id, record.intervention_assessment_ref)
        intervention_types = tuple(getattr(assessment, "intervention_types", ()) or ())
        required_authorities = tuple(getattr(assessment, "required_authorities", ()) or ())
        ctx = self._svc.pilot_change_context(self._config.tenant_id, record.workflow_revision_id)
        item = build_queue_item(
            pilot_id=self._config.pilot_id, tenant_id=self._config.tenant_id,
            workflow_id=record.workflow_id, workflow_revision_id=record.workflow_revision_id,
            head_sha=ctx["head_sha"], clearance_status=record.clearance_status,
            intervention_types=tuple(str(t) for t in intervention_types),
            required_authorities=required_authorities, reason_codes=(), created_at=_ts(at))
        self._persist_queue_item(item, at)
        self._queue[item.queue_item_id] = item
        self._metrics.review_queue_size = len(self._queue)
        return item

    def _persist_queue_item(self, item: ReviewerQueueItem, at) -> None:
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"queue:{item.queue_fingerprint}", record_type=RecordType.REVIEWER_QUEUE_ITEM,
            record_id=item.record_id, payload={
                "queue_item_id": item.queue_item_id, "workflow_revision_id": item.workflow_revision_id,
                "clearance_status": item.clearance_status, "priority": item.priority.value,
                "assignment_status": item.assignment_status.value,
                "required_authorities": list(item.required_authorities),
                "head_sha": item.head_sha, "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"queue:{item.record_id[-16:]}")

    # --- reviewer queue + feedback --------------------------------------
    def review_queue(self) -> Tuple[ReviewerQueueItem, ...]:
        return tuple(self._queue[k] for k in sorted(self._queue))

    def record_feedback(self, feedback, *, at=None):
        fb = self._runner.record_feedback(feedback)
        item = next((i for i in self._queue.values()
                     if i.workflow_revision_id == feedback.workflow_revision_id), None)
        if item is not None:
            updated = queue_record_feedback(item, feedback_ref=fb.record_id, at=_ts(at or feedback.submitted_at))
            self._queue[item.queue_item_id] = updated
            self._persist_queue_item(updated, at or feedback.submitted_at)
        return fb

    # --- observability ---------------------------------------------------
    def health(self, *, integrity_ok: bool = True):
        rate = (self._metrics.adapter_failures / self._metrics.adapter_calls) \
            if self._metrics.adapter_calls else 0.0
        return compute_health(store=self._store, registry=self._registry,
                              lifecycle_status=self._status, recent_source_failure_rate=rate,
                              integrity_ok=integrity_ok)

    def readiness(self):
        store_ok = self._store.health_check().get("ok", False)
        adapter_ok = self._registry is not None and \
            self._registry.entry_for("cg.github_readonly") is not None
        return compute_readiness(
            config_valid=True, lifecycle_status=self._status, kill_switch_active=self._kill_active,
            store_integrity_ok=store_ok, required_adapter_available=adapter_ok)

    def metrics(self):
        self._metrics.review_queue_size = len(self._queue)
        return self._metrics

    def inspect(self) -> Dict[str, Any]:
        return {"pilot_id": self._config.pilot_id, "run_id": self._run_id,
                "status": self._status.value, "kill_switch_active": self._kill_active,
                "evaluations": self._metrics.evaluations_completed,
                "review_queue_size": len(self._queue), "execution_status": "DISABLED"}

    # --- closeout --------------------------------------------------------
    def closeout(self, at) -> Dict[str, Any]:
        if self._status in (PilotLifecycleStatus.ACTIVE, PilotLifecycleStatus.PAUSED):
            self._transition(PilotLifecycleStatus.STOPPING, at, "operator_closeout")
        report = self._runner.export_report(occurred_at=at)
        verification = verify_shadow_pilot_report(report)
        metrics_snapshot = self._metrics.snapshot()
        self._writer.commit(
            tenant_id=self._config.tenant_id, pilot_id=self._config.pilot_id,
            revision_id=f"opmetrics:{self._metrics.metrics_fingerprint}",
            record_type=RecordType.PILOT_OPERATOR_METRICS,
            record_id=f"opmetrics:{self._metrics.metrics_fingerprint}",
            payload={"metrics_fingerprint": self._metrics.metrics_fingerprint,
                     "evaluations_completed": self._metrics.evaluations_completed,
                     "execution_status": "DISABLED"},
            occurred_at=at, event_label=f"opmetrics:{self._metrics.metrics_fingerprint[:12]}")
        if self._status is PilotLifecycleStatus.STOPPING:
            self._transition(PilotLifecycleStatus.COMPLETED, at, "operator_closeout")
        unresolved = [i.queue_item_id for i in self._queue.values()
                      if i.assignment_status not in (ReviewerQueueStatus.FEEDBACK_RECORDED,
                                                     ReviewerQueueStatus.CLOSED)]
        return {"pilot_status": report.get("pilot_status"), "report_verified": verification.ok,
                "report_fingerprint": report["report_fingerprint"],
                "operator_metrics": metrics_snapshot, "unresolved_queue_items": unresolved,
                "final_lifecycle_status": self._status.value,
                "limitations": report.get("limitations", []), "execution_status": "DISABLED"}


def open_pilot_operator(config: PilotDeploymentConfig, *, service, registry, profile,
                        routing=None, credential_resolver=None,
                        invocation_ref: str = "operator-invocation") -> PilotOperator:
    """Open a durable pilot operator over an existing durable service."""
    return PilotOperator(config, service=service, registry=registry, profile=profile,
                         routing=routing, credential_resolver=credential_resolver,
                         invocation_ref=invocation_ref)


__all__ = ["PilotOperator", "open_pilot_operator", "recover_pilot"]

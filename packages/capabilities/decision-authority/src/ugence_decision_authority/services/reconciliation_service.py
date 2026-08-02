"""ReconciliationService — observes external outcomes and reconciles them.

Ingests observed external outcomes (from a status query or an external callback),
creates immutable ``ExecutionRecord``s from *observed* results only, and compares
the authorized intent against what was observed to produce an immutable
``ReconciliationResult``. It never fabricates an outcome, never treats dispatch as
success, and never mutates the source records. Unknown finality is indeterminate;
material mismatches and duplicates escalate.
"""

from __future__ import annotations

from typing import Mapping, Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..identity.actor import ActorType
from ..audit.events import AuditEventType
from ..execution.execution_intent import ExecutionIntent
from ..execution.execution_record import ExecutionRecord
from ..execution.external_system import ExternalExecutionPort
from ..execution.lifecycle import is_legal_transition
from ..execution.reconciliation import ReconciliationResult
from ..execution.status import (
    BUSINESS_OUTCOME_TO_STATUS,
    BusinessOutcome,
    ExecutionStatus,
    Finality,
    OutcomeSource,
    ReconciliationStatus,
)
from ..errors import (
    ExecutionOutcomeUnknownError,
    ExternalRequestMismatchError,
    InvalidExecutionTransitionError,
    ReconciliationIncompleteError,
)
from ..identity import IdentityProvider
from ..policy import EvidenceAccessPolicy, Permission
from ..repositories.execution_repository import ExecutionRepository
from ..audit import AuditService
from ._execution_authz import authorize_execution

_OUTCOME_EVENT = {
    BusinessOutcome.SUCCEEDED: AuditEventType.EXECUTION_SUCCEEDED,
    BusinessOutcome.FAILED: AuditEventType.EXECUTION_FAILED,
    BusinessOutcome.PARTIALLY_SUCCEEDED: AuditEventType.EXECUTION_PARTIALLY_SUCCEEDED,
    BusinessOutcome.DUPLICATE: AuditEventType.EXECUTION_DUPLICATE_DETECTED,
}


class ReconciliationService:
    def __init__(
        self,
        execution_repository: ExecutionRepository,
        external_port: ExternalExecutionPort,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._repo = execution_repository
        self._port = external_port
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    def _emit(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="execution", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def _dispatched_attempt(self, intent: ExecutionIntent):
        for attempt in reversed(self._repo.get_attempt_history(intent.execution_intent_id)):
            if attempt.external_request_id:
                return attempt
        return None

    # --- record observed outcome -----------------------------------------
    def record_external_outcome(
        self, *, intent_id: str, actor: str, business_outcome: BusinessOutcome,
        observed_parameters: Optional[Mapping[str, str]] = None,
        external_result_id: str = "", finality: Finality = Finality.UNKNOWN,
        reason_codes: tuple[str, ...] = (), source: OutcomeSource = OutcomeSource.MANUAL_ENTRY,
        external_request_id: Optional[str] = None,
    ) -> ExecutionRecord:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.RECORD_EXTERNAL_OUTCOME, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        attempt = self._dispatched_attempt(intent)
        if attempt is None:
            raise ReconciliationIncompleteError(
                "no dispatched attempt with an external request id exists")
        if external_request_id and external_request_id != attempt.external_request_id:
            raise ExternalRequestMismatchError(
                "observed outcome references a different external request id")
        return self._record(intent, attempt, business_outcome,
                            dict(observed_parameters or {}), external_result_id,
                            finality, reason_codes, source, actor, actor_type)

    def query_external_status(self, *, intent_id: str, actor: str) -> ExecutionRecord:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.QUERY_EXECUTION_STATUS, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        attempt = self._dispatched_attempt(intent)
        if attempt is None:
            raise ReconciliationIncompleteError(
                "no dispatched attempt to query")
        status = self._port.query_status(attempt.external_request_id)
        if status.external_request_id != attempt.external_request_id:
            raise ExternalRequestMismatchError(
                "external status references a different external request id")
        return self._record(
            intent, attempt, status.business_outcome, dict(status.observed_parameters),
            status.external_result_id, status.finality, status.reason_codes,
            OutcomeSource.ADAPTER_STATUS_QUERY, actor, actor_type)

    def _record(self, intent, attempt, business_outcome, observed_parameters,
                external_result_id, finality, reason_codes, source, actor, actor_type):
        # Duplicate detection: an already-observed result id for this external
        # request is surfaced, never silently collapsed.
        prior = self._repo.lookup_by_external_request_id(attempt.external_request_id)
        effective_outcome = business_outcome
        if external_result_id and any(
                r.external_result_id == external_result_id for r in prior):
            effective_outcome = BusinessOutcome.DUPLICATE

        record = ExecutionRecord(
            execution_record_id=self._new_id("exr"),
            execution_intent_id=intent.execution_intent_id,
            execution_attempt_id=attempt.execution_attempt_id, tenant_id=intent.tenant_id,
            external_system=intent.target_system,
            external_request_id=attempt.external_request_id,
            external_result_id=external_result_id, business_outcome=effective_outcome,
            observed_parameters=observed_parameters, observed_at=self._clock(),
            source=source, finality=finality, reason_codes=reason_codes,
            correlation_id=intent.correlation_id)
        record = record.model_copy(update={"content_hash": record.compute_hash()})
        self._repo.record_execution_record(record)

        target = BUSINESS_OUTCOME_TO_STATUS[effective_outcome]
        if is_legal_transition(intent.status, target):
            self._transition(intent, target)
        self._emit(AuditEventType.EXECUTION_OUTCOME_RECORDED,
                   intent.execution_intent_id, actor, actor_type, intent.correlation_id,
                   {"business_outcome": effective_outcome.value,
                    "finality": finality.value, "observed_hash": record.content_hash})
        event = _OUTCOME_EVENT.get(effective_outcome)
        if event is not None:
            self._emit(event, intent.execution_intent_id, actor, actor_type,
                       intent.correlation_id,
                       {"execution_record_id": record.execution_record_id})
        return record

    # --- reconciliation ---------------------------------------------------
    def reconcile_execution(self, *, intent_id: str, actor: str) -> ReconciliationResult:
        intent = self._repo.get_execution_intent(intent_id)
        actor_type = authorize_execution(
            self._identity, self._policy, self._audit, actor=actor,
            permission=Permission.RECONCILE_EXECUTION, tenant_id=intent.tenant_id,
            correlation_id=intent.correlation_id, entity_id=intent_id)
        records = self._repo.get_execution_records(intent_id)
        if not records:
            raise ReconciliationIncompleteError(
                "no observed execution records to reconcile")
        self._emit(AuditEventType.EXECUTION_RECONCILIATION_STARTED, intent_id, actor,
                   actor_type, intent.correlation_id, {"records": len(records)})
        if is_legal_transition(intent.status, ExecutionStatus.RECONCILIATION_PENDING):
            intent = self._transition(intent, ExecutionStatus.RECONCILIATION_PENDING)

        latest = records[-1]
        status, mismatch_codes, compensation = self._compare(intent, records, latest)

        result = ReconciliationResult(
            reconciliation_id=self._new_id("rec"), execution_intent_id=intent_id,
            tenant_id=intent.tenant_id,
            execution_record_ids=tuple(r.execution_record_id for r in records),
            expected_action_type=intent.action_type,
            expected_target_system=intent.target_system,
            expected_parameters=dict(intent.authorized_parameters),
            observed_outcome=latest.business_outcome,
            observed_parameters=dict(latest.observed_parameters), status=status,
            mismatch_codes=mismatch_codes, compensation_required=compensation,
            reconciled_by=actor, reconciled_at=self._clock(),
            correlation_id=intent.correlation_id)
        result = result.model_copy(update={"content_hash": result.compute_hash()})
        self._repo.record_reconciliation_result(result)

        final_status = {
            ReconciliationStatus.RECONCILED: ExecutionStatus.RECONCILED,
            ReconciliationStatus.MISMATCHED: ExecutionStatus.MISMATCHED,
            ReconciliationStatus.PARTIALLY_RECONCILED: ExecutionStatus.MANUAL_REVIEW_REQUIRED,
            ReconciliationStatus.INDETERMINATE: ExecutionStatus.MANUAL_REVIEW_REQUIRED,
            ReconciliationStatus.MANUAL_REVIEW_REQUIRED: ExecutionStatus.MANUAL_REVIEW_REQUIRED,
            ReconciliationStatus.COMPENSATION_REQUIRED: ExecutionStatus.COMPENSATION_REQUIRED,
        }[status]
        if is_legal_transition(intent.status, final_status):
            self._transition(intent, final_status)

        if status is ReconciliationStatus.RECONCILED:
            self._emit(AuditEventType.EXECUTION_RECONCILED, intent_id, actor, actor_type,
                       intent.correlation_id, {"status": status.value})
        elif status in (ReconciliationStatus.MISMATCHED,
                        ReconciliationStatus.COMPENSATION_REQUIRED):
            self._emit(AuditEventType.EXECUTION_MISMATCH_DETECTED, intent_id, actor,
                       actor_type, intent.correlation_id,
                       {"status": status.value, "mismatch_codes": list(mismatch_codes)})
        else:
            self._emit(AuditEventType.EXECUTION_MANUAL_REVIEW_REQUIRED, intent_id, actor,
                       actor_type, intent.correlation_id, {"status": status.value})
        return result

    def _compare(self, intent, records, latest):
        """Deterministically compare authorized intent against observed effects."""
        mismatch: list[str] = []
        # Duplicate effects across records escalate to manual review.
        success_like = [r for r in records if r.business_outcome in (
            BusinessOutcome.SUCCEEDED, BusinessOutcome.PARTIALLY_SUCCEEDED)]
        distinct_results = {r.external_result_id for r in success_like if r.external_result_id}
        if any(r.business_outcome is BusinessOutcome.DUPLICATE for r in records) \
                or len(distinct_results) > 1:
            mismatch.append("DUPLICATE_EFFECT")
            return ReconciliationStatus.MANUAL_REVIEW_REQUIRED, tuple(mismatch), True

        if latest.business_outcome is BusinessOutcome.UNKNOWN \
                or latest.finality is Finality.UNKNOWN:
            return ReconciliationStatus.INDETERMINATE, (), False

        if latest.business_outcome in (BusinessOutcome.FAILED,
                                       BusinessOutcome.REJECTED,
                                       BusinessOutcome.CANCELLED_EXTERNALLY):
            mismatch.append(f"OUTCOME_{latest.business_outcome.value}")
            return ReconciliationStatus.COMPENSATION_REQUIRED, tuple(mismatch), True

        if latest.business_outcome is BusinessOutcome.PARTIALLY_SUCCEEDED:
            return ReconciliationStatus.PARTIALLY_RECONCILED, ("PARTIAL_COMPLETION",), True

        # SUCCEEDED: compare observed parameters to the authorized ones.
        expected = dict(intent.authorized_parameters)
        observed = dict(latest.observed_parameters)
        for key, value in expected.items():
            if key in observed and observed[key] != value:
                mismatch.append(f"PARAM_MISMATCH:{key}")
        if mismatch:
            return ReconciliationStatus.MISMATCHED, tuple(mismatch), True
        return ReconciliationStatus.RECONCILED, (), False

    def _transition(self, intent, target):
        evolved = intent.evolve(intent_version_id=self._new_id("iv"), status=target)
        return self._repo.save_execution_snapshot(evolved)

    # --- reads ------------------------------------------------------------
    def get_execution_records(self, intent_id: str) -> tuple[ExecutionRecord, ...]:
        return self._repo.get_execution_records(intent_id)

    def get_reconciliation_history(self, intent_id: str) -> tuple[ReconciliationResult, ...]:
        return self._repo.get_reconciliation_history(intent_id)

"""Callable Execution API facade + optional FastAPI adapter.

A framework-agnostic surface over the Phase-4C services. Every operation is
authorized and audited inside the services; this facade only shapes typed requests.
It exposes unknown and partial outcomes explicitly, requires explicit retry, and
provides **no endpoint that rewrites history** and no way to fabricate an outcome.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ugence_decision_authority.api.contracts import (
    BusinessOutcome,
    CompensationApprovalStatus,
    CompensationRequirement,
    CompensationType,
    ExecutionAttempt,
    ExecutionIntent,
    ExecutionRecord,
    ExecutionValidationResult,
    Finality,
    OutcomeSource,
    ReconciliationResult,
    RetryClassification,
)
from ugence_decision_authority.api.identity import IdentityProvider
from ugence_decision_authority.api.services import (
    CompensationService,
    ExecutionService,
    ReconciliationService,
)


class CreateExecutionIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    action_request_id: str
    execution_parameters: Optional[dict[str, str]] = None
    execution_idempotency_key: str = ""


class ExecutionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    intent_id: str


class RetryExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    intent_id: str
    retry_classification: RetryClassification
    second_approver: Optional[str] = None


class RecordOutcomeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    intent_id: str
    business_outcome: BusinessOutcome
    observed_parameters: Optional[dict[str, str]] = None
    external_result_id: str = ""
    finality: Finality = Finality.UNKNOWN
    reason_codes: tuple[str, ...] = ()
    source: OutcomeSource = OutcomeSource.EXTERNAL_CALLBACK
    external_request_id: Optional[str] = None


class CreateCompensationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    intent_id: str
    reconciliation_id: str
    reason_codes: tuple[str, ...]
    proposed_compensation_type: CompensationType = CompensationType.MANUAL_INTERVENTION
    affected_effects: tuple[str, ...] = ()
    required_authority: str = ""


class ResolveCompensationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    compensation_id: str
    resolution_ref: str
    status: CompensationApprovalStatus = CompensationApprovalStatus.RESOLVED


class ExecutionAPI:
    """Thin typed facade over the Phase-4C services. No history-rewriting surface."""

    def __init__(
        self,
        execution_service: ExecutionService,
        reconciliation_service: ReconciliationService,
        compensation_service: CompensationService,
        identity_provider: IdentityProvider,
    ) -> None:
        self._exec = execution_service
        self._recon = reconciliation_service
        self._comp = compensation_service
        self._identity = identity_provider

    # intent + dispatch
    def create_execution_intent(self, request: CreateExecutionIntentRequest) -> ExecutionIntent:
        return self._exec.create_execution_intent(
            action_request_id=request.action_request_id, created_by=request.principal_id,
            execution_parameters=request.execution_parameters,
            execution_idempotency_key=request.execution_idempotency_key)

    def get_execution_intent(self, intent_id: str) -> ExecutionIntent:
        return self._exec.get_execution_intent(intent_id)

    def get_execution_history(self, intent_id: str) -> tuple[ExecutionIntent, ...]:
        return self._exec.get_execution_history(intent_id)

    def validate_execution(self, request: ExecutionActionRequest) -> ExecutionValidationResult:
        return self._exec.validate_execution(
            intent_id=request.intent_id, actor=request.principal_id)

    def dispatch_execution(self, request: ExecutionActionRequest) -> ExecutionAttempt:
        return self._exec.dispatch_execution(
            intent_id=request.intent_id, actor=request.principal_id)

    def retry_execution(self, request: RetryExecutionRequest) -> ExecutionAttempt:
        return self._exec.retry_execution(
            intent_id=request.intent_id, actor=request.principal_id,
            retry_classification=request.retry_classification,
            second_approver=request.second_approver)

    def get_execution_attempts(self, intent_id: str) -> tuple[ExecutionAttempt, ...]:
        return self._exec.get_execution_attempts(intent_id)

    # observed outcomes + reconciliation
    def record_external_outcome(self, request: RecordOutcomeRequest) -> ExecutionRecord:
        return self._recon.record_external_outcome(
            intent_id=request.intent_id, actor=request.principal_id,
            business_outcome=request.business_outcome,
            observed_parameters=request.observed_parameters,
            external_result_id=request.external_result_id, finality=request.finality,
            reason_codes=request.reason_codes, source=request.source,
            external_request_id=request.external_request_id)

    def query_external_status(self, request: ExecutionActionRequest) -> ExecutionRecord:
        return self._recon.query_external_status(
            intent_id=request.intent_id, actor=request.principal_id)

    def get_execution_records(self, intent_id: str) -> tuple[ExecutionRecord, ...]:
        return self._recon.get_execution_records(intent_id)

    def reconcile_execution(self, request: ExecutionActionRequest) -> ReconciliationResult:
        return self._recon.reconcile_execution(
            intent_id=request.intent_id, actor=request.principal_id)

    def get_reconciliation_history(self, intent_id: str) -> tuple[ReconciliationResult, ...]:
        return self._recon.get_reconciliation_history(intent_id)

    # compensation
    def create_compensation_requirement(self, request: CreateCompensationRequest
                                        ) -> CompensationRequirement:
        return self._comp.create_compensation_requirement(
            intent_id=request.intent_id, reconciliation_id=request.reconciliation_id,
            actor=request.principal_id, reason_codes=request.reason_codes,
            proposed_compensation_type=request.proposed_compensation_type,
            affected_effects=request.affected_effects,
            required_authority=request.required_authority)

    def resolve_compensation_requirement(self, request: ResolveCompensationRequest
                                         ) -> CompensationRequirement:
        return self._comp.resolve_compensation_requirement(
            compensation_id=request.compensation_id, actor=request.principal_id,
            resolution_ref=request.resolution_ref, status=request.status)

    def get_compensation_history(self, intent_id: str) -> tuple[CompensationRequirement, ...]:
        return self._comp.get_compensation_history(intent_id)


def build_execution_router(api: ExecutionAPI):  # pragma: no cover - optional adapter
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/executions", tags=["executions"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("")
    def _create(request: CreateExecutionIntentRequest):
        return _guard(lambda: api.create_execution_intent(request))

    @router.get("/{intent_id}")
    def _get(intent_id: str):
        return _guard(lambda: api.get_execution_intent(intent_id))

    @router.get("/{intent_id}/history")
    def _history(intent_id: str):
        return _guard(lambda: api.get_execution_history(intent_id))

    @router.post("/validate")
    def _validate(request: ExecutionActionRequest):
        return _guard(lambda: api.validate_execution(request))

    @router.post("/dispatch")
    def _dispatch(request: ExecutionActionRequest):
        return _guard(lambda: api.dispatch_execution(request))

    @router.post("/retry")
    def _retry(request: RetryExecutionRequest):
        return _guard(lambda: api.retry_execution(request))

    @router.get("/{intent_id}/attempts")
    def _attempts(intent_id: str):
        return _guard(lambda: api.get_execution_attempts(intent_id))

    @router.post("/outcomes")
    def _record(request: RecordOutcomeRequest):
        return _guard(lambda: api.record_external_outcome(request))

    @router.post("/query-status")
    def _query(request: ExecutionActionRequest):
        return _guard(lambda: api.query_external_status(request))

    @router.get("/{intent_id}/records")
    def _records(intent_id: str):
        return _guard(lambda: api.get_execution_records(intent_id))

    @router.post("/reconcile")
    def _reconcile(request: ExecutionActionRequest):
        return _guard(lambda: api.reconcile_execution(request))

    @router.get("/{intent_id}/reconciliations")
    def _recons(intent_id: str):
        return _guard(lambda: api.get_reconciliation_history(intent_id))

    @router.post("/compensations")
    def _create_comp(request: CreateCompensationRequest):
        return _guard(lambda: api.create_compensation_requirement(request))

    @router.post("/compensations/resolve")
    def _resolve_comp(request: ResolveCompensationRequest):
        return _guard(lambda: api.resolve_compensation_requirement(request))

    @router.get("/{intent_id}/compensations")
    def _comp_history(intent_id: str):
        return _guard(lambda: api.get_compensation_history(intent_id))

    return router

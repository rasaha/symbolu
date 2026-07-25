"""Callable assessment API facade + optional FastAPI adapter.

A framework-agnostic surface over the deterministic assessment runtime
(:class:`~ai_hiring.services.assessment_service.AssessmentService`). The service
authorizes and audits every operation itself, so this facade is a thin, typed
request mapper — it does not add policy.

The surface is deliberately incomplete by design: there are **no** endpoints that
score, rank, compare, recommend, approve, reject, or hire. Phase 3B executes the
published evaluation constitution deterministically and produces advisory
assessment records only. Interpretation of evidence by an AI system is out of
scope and is not reachable through this API.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

from ..assessments.assessment import Assessment
from ..assessments.status import BindingProvenance, SupplierType
from ..assessments.workspace import AssessmentWorkspace
from ..ontology.taxonomy import EvidenceType, ReasonCode
from decision_governance.identity import IdentityProvider
from ..rubrics.conflicts import ConflictSeverity, ConflictSource
from ..rubrics.evidence_rules import MissingEvidenceStatus
from ..rubrics.scoring_scale import ScaleType
from ..rubrics.uncertainty import UncertaintyLevel
from ..services.assessment_service import AssessmentService


class CreateWorkspaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    tenant_id: str
    subject_id: str
    decision_type: str
    rubric_id: str
    correlation_id: Optional[str] = None


class BindEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    workspace_id: str
    criterion_id: str
    evidence_id: str
    evidence_type: EvidenceType
    provenance: BindingProvenance = BindingProvenance.MANUAL_AUTHORIZED


class RecordMissingEvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    workspace_id: str
    criterion_id: str
    status: MissingEvidenceStatus
    expected_evidence_type: Optional[EvidenceType] = None
    reason_codes: tuple[ReasonCode, ...] = ()


class SubmitObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    workspace_id: str
    criterion_id: str
    value: str
    scale_type: ScaleType
    supplier_type: SupplierType
    evidence_binding_ids: tuple[str, ...] = ()
    uncertainty: Optional[UncertaintyLevel] = None
    reason_codes: tuple[ReasonCode, ...] = ()
    explanation_reference: str = ""


class RecordConflictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    workspace_id: str
    criterion_id: str
    sources: tuple[ConflictSource, ...]
    severity: ConflictSeverity
    reason: str


class WorkspaceActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    principal_id: str
    workspace_id: str


class AssessmentAPI:
    """Thin typed facade over :class:`AssessmentService`.

    Authorization, audit, and determinism are enforced inside the service; this
    class only shapes requests. It exposes no scoring, ranking, recommendation,
    or decision operation.
    """

    def __init__(self, assessment_service: AssessmentService,
                 identity_provider: IdentityProvider) -> None:
        self._svc = assessment_service
        self._identity = identity_provider

    # POST /assessments/workspaces
    def create_workspace(self, request: CreateWorkspaceRequest) -> AssessmentWorkspace:
        return self._svc.create_workspace(
            tenant_id=request.tenant_id, subject_id=request.subject_id,
            decision_type=request.decision_type, rubric_id=request.rubric_id,
            created_by=request.principal_id, correlation_id=request.correlation_id)

    # GET /assessments/workspaces/{id}
    def get_workspace(self, workspace_id: str) -> AssessmentWorkspace:
        return self._svc.get_workspace(workspace_id)

    # POST /assessments/workspaces/{id}/evidence
    def bind_evidence(self, request: BindEvidenceRequest):
        return self._svc.bind_evidence(
            workspace_id=request.workspace_id, criterion_id=request.criterion_id,
            evidence_id=request.evidence_id, evidence_type=request.evidence_type,
            bound_by=request.principal_id, provenance=request.provenance)

    # POST /assessments/workspaces/{id}/missing-evidence
    def record_missing_evidence(self, request: RecordMissingEvidenceRequest):
        return self._svc.record_missing_evidence(
            workspace_id=request.workspace_id, criterion_id=request.criterion_id,
            status=request.status, expected_evidence_type=request.expected_evidence_type,
            reason_codes=request.reason_codes, actor=request.principal_id)

    # POST /assessments/workspaces/{id}/observations
    def submit_observation(self, request: SubmitObservationRequest):
        return self._svc.submit_observation(
            workspace_id=request.workspace_id, criterion_id=request.criterion_id,
            value=request.value, scale_type=request.scale_type,
            supplier_type=request.supplier_type, supplied_by=request.principal_id,
            evidence_binding_ids=request.evidence_binding_ids,
            uncertainty=request.uncertainty, reason_codes=request.reason_codes,
            explanation_reference=request.explanation_reference)

    # POST /assessments/workspaces/{id}/conflicts
    def record_conflict(self, request: RecordConflictRequest):
        return self._svc.record_conflict(
            workspace_id=request.workspace_id, criterion_id=request.criterion_id,
            sources=request.sources, severity=request.severity, reason=request.reason,
            actor=request.principal_id)

    # POST /assessments/workspaces/{id}/validate
    def validate_assessment(self, request: WorkspaceActionRequest):
        return self._svc.validate_assessment(
            workspace_id=request.workspace_id, actor=request.principal_id)

    # POST /assessments/workspaces/{id}/finalize
    def finalize_assessment(self, request: WorkspaceActionRequest) -> Assessment:
        return self._svc.finalize_assessment(
            workspace_id=request.workspace_id, actor=request.principal_id)

    # POST /assessments/workspaces/{id}/supersede
    def supersede_assessment(self, request: WorkspaceActionRequest) -> AssessmentWorkspace:
        return self._svc.supersede_assessment(
            workspace_id=request.workspace_id, actor=request.principal_id)

    # POST /assessments/workspaces/{id}/cancel
    def cancel_assessment(self, request: WorkspaceActionRequest) -> AssessmentWorkspace:
        return self._svc.cancel_assessment(
            workspace_id=request.workspace_id, actor=request.principal_id)

    # GET /assessments/{id}
    def get_assessment(self, assessment_id: str) -> Assessment:
        return self._svc.get_assessment(assessment_id)

    # GET /assessments/workspaces/{id}/history
    def get_assessment_history(self, workspace_id: str) -> tuple[Assessment, ...]:
        return self._svc.get_assessment_history(workspace_id)


def build_assessment_router(api: AssessmentAPI):  # pragma: no cover - optional adapter
    from fastapi import APIRouter, HTTPException

    from ..errors import HiringError

    router = APIRouter(prefix="/ai-hiring/assessments", tags=["assessments"])

    def _guard(fn):
        try:
            return fn()
        except HiringError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/workspaces")
    def _create_workspace(request: CreateWorkspaceRequest):
        return _guard(lambda: api.create_workspace(request))

    @router.get("/workspaces/{workspace_id}")
    def _get_workspace(workspace_id: str):
        return _guard(lambda: api.get_workspace(workspace_id))

    @router.post("/workspaces/evidence")
    def _bind_evidence(request: BindEvidenceRequest):
        return _guard(lambda: api.bind_evidence(request))

    @router.post("/workspaces/missing-evidence")
    def _record_missing(request: RecordMissingEvidenceRequest):
        return _guard(lambda: api.record_missing_evidence(request))

    @router.post("/workspaces/observations")
    def _submit_observation(request: SubmitObservationRequest):
        return _guard(lambda: api.submit_observation(request))

    @router.post("/workspaces/conflicts")
    def _record_conflict(request: RecordConflictRequest):
        return _guard(lambda: api.record_conflict(request))

    @router.post("/workspaces/validate")
    def _validate(request: WorkspaceActionRequest):
        return _guard(lambda: api.validate_assessment(request))

    @router.post("/workspaces/finalize")
    def _finalize(request: WorkspaceActionRequest):
        return _guard(lambda: api.finalize_assessment(request))

    @router.post("/workspaces/supersede")
    def _supersede(request: WorkspaceActionRequest):
        return _guard(lambda: api.supersede_assessment(request))

    @router.post("/workspaces/cancel")
    def _cancel(request: WorkspaceActionRequest):
        return _guard(lambda: api.cancel_assessment(request))

    @router.get("/{assessment_id}")
    def _get_assessment(assessment_id: str):
        return _guard(lambda: api.get_assessment(assessment_id))

    @router.get("/workspaces/{workspace_id}/history")
    def _history(workspace_id: str):
        return _guard(lambda: api.get_assessment_history(workspace_id))

    return router

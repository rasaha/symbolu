"""Assessment service — orchestrates the deterministic assessment runtime.

Coordinates workspace creation, evidence binding, missing-evidence recording,
observation submission, conflict recording, validation, and advisory finalization
— always authorized and audited. It **does not evaluate evidence**: it validates,
binds, records, and assembles. No inference, scoring, ranking, recommendation, or
decision occurs here.
"""

from __future__ import annotations

from typing import Optional

from ..common import Clock, IdFactory, new_id, utc_now
from ..assessments.assessment import Assessment, CapabilityAssessment
from ..assessments.evidence_binding import EvidenceBinding
from ..assessments.missing_evidence import MissingEvidenceRecord
from ..assessments.observation import Observation
from ..assessments.status import (
    AssessmentStatus,
    BindingProvenance,
    ObservationValidationStatus,
    SupplierType,
    WorkspaceStatus,
)
from ..assessments.validation import ValidationResult
from ..assessments.workspace import AssessmentWorkspace, CapabilityBinding
from ..domain.enums import ActorType, AuditEventType
from ..errors import (
    AIObservationNotAllowedError,
    AssessmentAlreadyFinalizedError,
    AssessmentAuthorizationError,
    AssessmentError,
    AssessmentIncompleteError,
    AssessmentSupersededError,
    BlockingConflictError,
    CapabilityVersionMismatchError,
    ObservationScaleMismatchError,
    ObservationSupplierNotAuthorizedError,
    ObservationValidationError,
    ObservationValueOutOfRangeError,
    PublishedRubricRequiredError,
    ReasonCodeNotPermittedError,
    RequiredUncertaintyMissingError,
)
from ..ontology.capability import CapabilityStatus
from ..ontology.taxonomy import EvidenceType, ReasonCode
from ugence_decision_authority.api.policy import AccessRequest, EvidenceAccessPolicy, Permission
from ugence_decision_authority.api.identity import IdentityProvider
from ..repositories.assessment_repository import AssessmentRepository
from ..repositories.assessment_workspace_repository import AssessmentWorkspaceRepository
from ..repositories.ontology_repository import OntologyRepository
from ..repositories.rubric_repository import RubricRepository
from ..rubrics.approval import RubricStatus
from ..rubrics.conflicts import Conflict, ConflictSeverity, ConflictSource
from ..rubrics.scoring_scale import ScaleType
from ..rubrics.uncertainty import UncertaintyLevel
from .assessment_completeness_service import AssessmentCompletenessService
from .assessment_validation_service import AssessmentValidationService
from .audit_service import AuditService
from .evidence_binding_service import BindingResult, EvidenceBindingService

_CLOSED = {WorkspaceStatus.FINALIZED_ADVISORY, WorkspaceStatus.SUPERSEDED,
           WorkspaceStatus.CANCELLED}

_ERR_FOR_CODE = {
    "OBSERVATION_SCALE_MISMATCH": ObservationScaleMismatchError,
    "OBSERVATION_VALUE_OUT_OF_RANGE": ObservationValueOutOfRangeError,
    "OBSERVATION_VALUE_NOT_INTEGER": ObservationValueOutOfRangeError,
    "OBSERVATION_VALUE_NOT_NUMERIC": ObservationValueOutOfRangeError,
    "OBSERVATION_VALUE_NOT_BINARY": ObservationValueOutOfRangeError,
    "OBSERVATION_VALUE_NOT_PASS_FAIL": ObservationValueOutOfRangeError,
    "OBSERVATION_VALUE_NOT_IN_CUSTOM_SCALE": ObservationValueOutOfRangeError,
    "REASON_CODE_NOT_PERMITTED": ReasonCodeNotPermittedError,
    "REASON_CODE_UNKNOWN": ReasonCodeNotPermittedError,
    "REQUIRED_UNCERTAINTY_MISSING": RequiredUncertaintyMissingError,
    "UNCERTAINTY_LEVEL_NOT_ALLOWED": RequiredUncertaintyMissingError,
    "OBSERVATION_SUPPLIER_NOT_AUTHORIZED": ObservationSupplierNotAuthorizedError,
    "AI_OBSERVATION_NOT_ALLOWED": AIObservationNotAllowedError,
}


class AssessmentService:
    def __init__(
        self,
        workspace_repository: AssessmentWorkspaceRepository,
        assessment_repository: AssessmentRepository,
        rubric_repository: RubricRepository,
        ontology_repository: OntologyRepository,
        evidence_binding_service: EvidenceBindingService,
        validation_service: AssessmentValidationService,
        completeness_service: AssessmentCompletenessService,
        audit_service: AuditService,
        identity_provider: IdentityProvider,
        access_policy: EvidenceAccessPolicy,
        *,
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._ws = workspace_repository
        self._assessments = assessment_repository
        self._rubrics = rubric_repository
        self._ontology = ontology_repository
        self._binding = evidence_binding_service
        self._validation = validation_service
        self._completeness = completeness_service
        self._audit = audit_service
        self._identity = identity_provider
        self._policy = access_policy
        self._new_id = id_factory
        self._clock = clock

    # --- authorization + audit --------------------------------------------
    def _authorize(self, actor: str, permission: Permission, tenant_id: str,
                   subject_id: Optional[str], correlation_id: str) -> ActorType:
        identity = self._identity.authenticate(actor)
        denied = None
        if not identity.authenticated:
            denied = "unauthenticated"
        else:
            decision = self._policy.authorize(AccessRequest(
                principal_id=actor, tenant_id=tenant_id, operation=permission,
                candidate_id=subject_id))
            if not decision.allowed:
                denied = decision.reason
        if denied is not None:
            self._audit.record(
                event_type=AuditEventType.ASSESSMENT_ACCESS_DENIED, entity_type="assessment",
                entity_id=tenant_id or "unknown", actor_type=identity.actor_type,
                actor_id=actor, correlation_id=correlation_id,
                payload={"operation": permission.value, "reason": denied})
            raise AssessmentAuthorizationError(
                f"actor '{actor}' not authorized for {permission.value}: {denied}")
        return identity.actor_type

    def _audit_service_record(self, event_type, entity_id, actor, actor_type, corr, payload):
        self._audit.record(
            event_type=event_type, entity_type="assessment", entity_id=entity_id,
            actor_type=actor_type, actor_id=actor, correlation_id=corr, payload=payload)

    def _ensure_open(self, ws: AssessmentWorkspace) -> None:
        if ws.status is WorkspaceStatus.SUPERSEDED:
            raise AssessmentSupersededError(f"workspace '{ws.workspace_id}' is superseded")
        if ws.status in (WorkspaceStatus.FINALIZED_ADVISORY, WorkspaceStatus.CANCELLED):
            raise AssessmentAlreadyFinalizedError(
                f"workspace '{ws.workspace_id}' is {ws.status.value}")

    def _pinned_rubric(self, ws: AssessmentWorkspace):
        for snap in self._rubrics.history(ws.rubric_id):
            if snap.version == ws.rubric_version and snap.status is RubricStatus.PUBLISHED:
                return snap
        raise PublishedRubricRequiredError(
            f"published rubric '{ws.rubric_id}' v{ws.rubric_version} not retrievable")

    # --- lifecycle ---------------------------------------------------------
    def create_workspace(self, *, tenant_id: str, subject_id: str, decision_type: str,
                         rubric_id: str, created_by: str,
                         correlation_id: Optional[str] = None) -> AssessmentWorkspace:
        corr = correlation_id or self._new_id("corr")
        actor_type = self._authorize(created_by, Permission.CREATE_ASSESSMENT_WORKSPACE,
                                     tenant_id, subject_id, corr)
        rubric = self._rubrics.published(rubric_id)
        if rubric is None:
            raise PublishedRubricRequiredError(f"no published rubric '{rubric_id}'")

        bindings: list[CapabilityBinding] = []
        uncertainty_rules = []
        for rc in rubric.capabilities:
            if not self._ontology.exists(rc.capability_id):
                raise CapabilityVersionMismatchError(
                    f"capability '{rc.capability_id}' not found")
            cap = self._ontology.get_version(rc.capability_id, rc.capability_version)
            if cap.status is not CapabilityStatus.PUBLISHED:
                raise CapabilityVersionMismatchError(
                    f"capability '{rc.capability_id}' v{rc.capability_version} not PUBLISHED")
            required = (rc.evidence_rule.minimum_count >= 1
                        or bool(rc.evidence_rule.required_types))
            bindings.append(CapabilityBinding(
                criterion_id=rc.capability_id, capability_id=rc.capability_id,
                capability_version=rc.capability_version, scoring_scale_id=rc.scoring_scale_id,
                evidence_rule=rc.evidence_rule, allowed_reason_codes=rc.allowed_reason_codes,
                required=required))
            if rc.uncertainty_rule is not None:
                uncertainty_rules.append(rc.uncertainty_rule)

        ws = AssessmentWorkspace(
            workspace_id=self._new_id("ws"), tenant_id=tenant_id, subject_id=subject_id,
            decision_type=decision_type, rubric_id=rubric_id, rubric_version=rubric.version,
            capability_bindings=tuple(bindings), uncertainty_rules=tuple(uncertainty_rules),
            created_by=created_by, status=WorkspaceStatus.EVIDENCE_BINDING,
            created_at=self._clock(), correlation_id=corr)
        self._ws.create_workspace(ws)
        self._audit_service_record(
            AuditEventType.ASSESSMENT_WORKSPACE_CREATED, ws.workspace_id, created_by,
            actor_type, corr, {"rubric_id": rubric_id, "rubric_version": rubric.version,
                               "criteria": len(bindings)})
        return ws

    def bind_evidence(self, *, workspace_id: str, criterion_id: str, evidence_id: str,
                      evidence_type: EvidenceType, bound_by: str,
                      provenance: BindingProvenance = BindingProvenance.MANUAL_AUTHORIZED
                      ) -> BindingResult:
        ws = self._ws.get_workspace(workspace_id)
        self._ensure_open(ws)
        actor_type = self._authorize(bound_by, Permission.BIND_EVIDENCE, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        criterion = ws.binding_for(criterion_id)
        if criterion is None:
            raise AssessmentError(f"unknown criterion '{criterion_id}'")
        result = self._binding.bind(ws, criterion, evidence_id=evidence_id,
                                    evidence_type=evidence_type, bound_by=bound_by,
                                    provenance=provenance)
        if result.admissible:
            self._ws.add_binding(result.binding)
            self._audit_service_record(
                AuditEventType.ASSESSMENT_EVIDENCE_BOUND, workspace_id, bound_by, actor_type,
                ws.correlation_id, {"binding_id": result.binding.binding_id,
                                    "criterion": criterion_id, "evidence_id": evidence_id})
        else:
            self._ws.add_excluded(result.exclusion)
            self._audit_service_record(
                AuditEventType.ASSESSMENT_EVIDENCE_EXCLUDED, workspace_id, bound_by,
                actor_type, ws.correlation_id,
                {"criterion": criterion_id, "evidence_id": evidence_id,
                 "outcome": result.exclusion.admissibility_outcome.value})
        return result

    def record_missing_evidence(self, *, workspace_id: str, criterion_id: str, status,
                                expected_evidence_type: Optional[EvidenceType] = None,
                                reason_codes: tuple[ReasonCode, ...] = (),
                                actor: str) -> MissingEvidenceRecord:
        ws = self._ws.get_workspace(workspace_id)
        self._ensure_open(ws)
        actor_type = self._authorize(actor, Permission.BIND_EVIDENCE, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        if ws.binding_for(criterion_id) is None:
            raise AssessmentError(f"unknown criterion '{criterion_id}'")
        record = MissingEvidenceRecord(
            record_id=self._new_id("miss"), workspace_id=workspace_id, criterion_id=criterion_id,
            capability_id=criterion_id, expected_evidence_type=expected_evidence_type,
            status=status, reason_codes=reason_codes, detected_at=self._clock())
        self._ws.add_missing(record)
        self._audit_service_record(
            AuditEventType.ASSESSMENT_MISSING_EVIDENCE_RECORDED, workspace_id, actor,
            actor_type, ws.correlation_id, {"criterion": criterion_id, "status": status.value})
        return record

    def submit_observation(self, *, workspace_id: str, criterion_id: str, value: str,
                           scale_type: ScaleType, supplier_type: SupplierType,
                           supplied_by: str, evidence_binding_ids: tuple[str, ...] = (),
                           uncertainty: Optional[UncertaintyLevel] = None,
                           reason_codes: tuple[ReasonCode, ...] = (),
                           explanation_reference: str = "") -> Observation:
        ws = self._ws.get_workspace(workspace_id)
        self._ensure_open(ws)
        actor_type = self._authorize(supplied_by, Permission.SUBMIT_OBSERVATION,
                                     ws.tenant_id, ws.subject_id, ws.correlation_id)
        criterion = ws.binding_for(criterion_id)
        if criterion is None:
            raise AssessmentError(f"unknown criterion '{criterion_id}'")
        rubric = self._pinned_rubric(ws)
        bindings_by_id = {b.binding_id: b for b in self._ws.list_bindings(workspace_id)}

        result = self._validation.validate_observation(
            ws, rubric, criterion, value=value, scale_type=scale_type,
            supplier_type=supplier_type, uncertainty=uncertainty, reason_codes=reason_codes,
            evidence_binding_ids=evidence_binding_ids, bindings_by_id=bindings_by_id)

        if not result.valid:
            self._audit_service_record(
                AuditEventType.ASSESSMENT_OBSERVATION_REJECTED, workspace_id, supplied_by,
                actor_type, ws.correlation_id,
                {"criterion": criterion_id, "issues": list(result.error_codes)})
            first = result.error_codes[0]
            raise _ERR_FOR_CODE.get(first, ObservationValidationError)(
                f"observation rejected: {result.error_codes}")

        obs = Observation(
            observation_id=self._new_id("obs"), workspace_id=workspace_id,
            criterion_id=criterion_id, capability_id=criterion.capability_id,
            capability_version=criterion.capability_version, value=value, scale_type=scale_type,
            supplied_by=supplied_by, supplier_type=supplier_type, supplied_at=self._clock(),
            evidence_binding_ids=evidence_binding_ids, uncertainty=uncertainty,
            reason_codes=reason_codes, explanation_reference=explanation_reference)
        self._ws.add_observation(obs)
        self._audit_service_record(
            AuditEventType.ASSESSMENT_OBSERVATION_SUBMITTED, workspace_id, supplied_by,
            actor_type, ws.correlation_id, {"criterion": criterion_id, "observation_id": obs.observation_id})
        return obs

    def record_conflict(self, *, workspace_id: str, criterion_id: str,
                        sources: tuple[ConflictSource, ...], severity: ConflictSeverity,
                        reason: str, actor: str) -> Conflict:
        ws = self._ws.get_workspace(workspace_id)
        self._ensure_open(ws)
        actor_type = self._authorize(actor, Permission.SUBMIT_OBSERVATION, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        conflict = Conflict(conflict_id=self._new_id("conf"), capability_id=criterion_id,
                            sources=sources, severity=severity, reason=reason)
        self._ws.add_conflict(conflict, workspace_id)
        self._audit_service_record(
            AuditEventType.ASSESSMENT_CONFLICT_RECORDED, workspace_id, actor, actor_type,
            ws.correlation_id, {"criterion": criterion_id, "severity": severity.value})
        return conflict

    def validate_assessment(self, *, workspace_id: str, actor: str) -> ValidationResult:
        ws = self._ws.get_workspace(workspace_id)
        actor_type = self._authorize(actor, Permission.VALIDATE_ASSESSMENT, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        completeness = self._compute_completeness(ws)
        valid = completeness.status.value not in ("BLOCKED",)
        self._audit_service_record(
            AuditEventType.ASSESSMENT_VALIDATED if valid
            else AuditEventType.ASSESSMENT_VALIDATION_FAILED,
            workspace_id, actor, actor_type, ws.correlation_id,
            {"completeness": completeness.status.value})
        from ..assessments.validation import ValidationResult as VR
        return VR(valid=valid, blocking_conditions=completeness.blocking_conditions)

    def finalize_assessment(self, *, workspace_id: str, actor: str) -> Assessment:
        ws = self._ws.get_workspace(workspace_id)
        self._ensure_open(ws)
        actor_type = self._authorize(actor, Permission.FINALIZE_ASSESSMENT, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        completeness = self._compute_completeness(ws)
        if completeness.status.value == "BLOCKED":
            raise BlockingConflictError(
                f"cannot finalize: {completeness.blocking_conditions}")
        if not completeness.finalizable:
            raise AssessmentIncompleteError(
                f"cannot finalize: {completeness.status.value} "
                f"{completeness.blocking_conditions}")

        capability_assessments = self._assemble(ws)
        prior = self._assessments.get_latest_assessment(workspace_id)
        version = (prior.version + 1) if prior else 1
        assessment = Assessment(
            assessment_id=self._new_id("asmt"), workspace_id=workspace_id,
            tenant_id=ws.tenant_id, subject_id=ws.subject_id, rubric_id=ws.rubric_id,
            rubric_version=ws.rubric_version, capability_assessments=capability_assessments,
            completeness=completeness, status=AssessmentStatus.FINALIZED_ADVISORY,
            created_by=actor, created_at=self._clock(),
            supersedes_assessment_id=prior.assessment_id if prior else None,
            version=version, correlation_id=ws.correlation_id)
        self._assessments.create_assessment(assessment)
        self._ws.save_workspace_version(ws.with_status(WorkspaceStatus.FINALIZED_ADVISORY))
        self._audit_service_record(
            AuditEventType.ASSESSMENT_FINALIZED_ADVISORY, assessment.assessment_id, actor,
            actor_type, ws.correlation_id,
            {"workspace_id": workspace_id, "completeness": completeness.status.value,
             "version": version})
        if prior is not None:
            self._audit_service_record(
                AuditEventType.ASSESSMENT_SUPERSEDED, prior.assessment_id, actor, actor_type,
                ws.correlation_id, {"superseded_by": assessment.assessment_id})
        return assessment

    def supersede_assessment(self, *, workspace_id: str, actor: str) -> AssessmentWorkspace:
        """Reopen a finalized workspace for a superseding revision (append-only)."""
        ws = self._ws.get_workspace(workspace_id)
        actor_type = self._authorize(actor, Permission.SUPERSEDE_ASSESSMENT, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        if ws.status is not WorkspaceStatus.FINALIZED_ADVISORY:
            raise AssessmentError("only a finalized workspace can be superseded")
        reopened = self._ws.save_workspace_version(ws.with_status(WorkspaceStatus.IN_PROGRESS))
        self._audit_service_record(
            AuditEventType.ASSESSMENT_SUPERSEDED, workspace_id, actor, actor_type,
            ws.correlation_id, {"reopened": True})
        return reopened

    def cancel_assessment(self, *, workspace_id: str, actor: str) -> AssessmentWorkspace:
        ws = self._ws.get_workspace(workspace_id)
        actor_type = self._authorize(actor, Permission.CANCEL_ASSESSMENT, ws.tenant_id,
                                     ws.subject_id, ws.correlation_id)
        cancelled = self._ws.save_workspace_version(ws.with_status(WorkspaceStatus.CANCELLED))
        self._audit_service_record(
            AuditEventType.ASSESSMENT_CANCELLED, workspace_id, actor, actor_type,
            ws.correlation_id, {})
        return cancelled

    # --- helpers -----------------------------------------------------------
    def _compute_completeness(self, ws: AssessmentWorkspace):
        return self._completeness.compute(
            ws, bindings=self._ws.list_bindings(ws.workspace_id),
            observations=self._ws.list_observations(ws.workspace_id),
            missing=self._ws.list_missing(ws.workspace_id),
            conflicts=self._ws.list_conflicts(ws.workspace_id))

    def _assemble(self, ws: AssessmentWorkspace) -> tuple[CapabilityAssessment, ...]:
        bindings = self._ws.list_bindings(ws.workspace_id)
        excluded = self._ws.list_excluded(ws.workspace_id)
        observations = {o.criterion_id: o for o in self._ws.list_observations(ws.workspace_id)}
        missing = self._ws.list_missing(ws.workspace_id)
        conflicts = self._ws.list_conflicts(ws.workspace_id)
        out: list[CapabilityAssessment] = []
        for b in ws.capability_bindings:
            crit = b.criterion_id
            obs = observations.get(crit)
            out.append(CapabilityAssessment(
                capability_id=b.capability_id, capability_version=b.capability_version,
                criterion_id=crit,
                admitted_evidence_ids=tuple(x.evidence_id for x in bindings
                                            if x.criterion_id == crit),
                excluded_evidence_records=tuple(x for x in excluded if x.criterion_id == crit),
                observation=obs,
                missing_evidence_records=tuple(m for m in missing if m.criterion_id == crit),
                uncertainty=obs.uncertainty if obs else None,
                conflicts=tuple(c for c in conflicts if c.capability_id == crit),
                reason_codes=obs.reason_codes if obs else (),
                validation_status=ObservationValidationStatus.VALID))
        return tuple(out)

    # --- reads -------------------------------------------------------------
    def get_workspace(self, workspace_id: str) -> AssessmentWorkspace:
        return self._ws.get_workspace(workspace_id)

    def get_assessment(self, assessment_id: str) -> Assessment:
        return self._assessments.get_assessment(assessment_id)

    def get_assessment_history(self, workspace_id: str) -> tuple[Assessment, ...]:
        return self._assessments.get_assessment_history(workspace_id)

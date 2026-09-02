"""§3.3 pilot observation at Slice 1's aggregation boundary, §3.4 quality evaluation
record and the validation operation that receives every object it checks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from ugence_governance_contracts.api import MetricClaim, TransformationMethod
from ugence_reasoning_method_advisor.api import ReasoningMethodAdvisory
from ugence_reasoning_method_governance.api import (
    AggregationRef,
    AttestationEnvelope,
    BindingRef,
    ContractError,
    ContractErrorCode,
    QualityResult,
    ReasoningMethodExecutionRecord,
    ReasoningMethodRef,
    ResearchComparisonPlan,
)

from .._canon import digest_of, require_digest, require_nonblank, require_tzaware, settle_digest
from ..errors import PilotError, PilotErrorCode
from .benchmark import BenchmarkManifest, require_count
from .evaluator import INDEPENDENCE_DECLARED_UNVERIFIED
from .manifest import LLM_CALLS_FIELD, PilotRole, PilotStudyManifest, ValidatedManifest, sorted_roles

PILOT_OBSERVATION_SCHEMA_VERSION = "workflow_fit_pilot.observation.v1"
QUALITY_EVALUATION_SCHEMA_VERSION = "workflow_fit_pilot.quality_evaluation.v1"
RUNTIME_REPORTED_DIAGNOSTIC = "RUNTIME_REPORTED_DIAGNOSTIC"


def claim_digest(claim: MetricClaim) -> str:
    """MetricClaim has no self-digest; the pilot canonicalizes its fields."""
    return digest_of(claim)


def quality_result_digest(result: QualityResult) -> str:
    return digest_of(result)


@dataclass(frozen=True)
class WorkflowReportedDiagnostics:
    total_llm_calls_reported: Optional[int]
    harness_observed_calls: Optional[int]
    label: str = RUNTIME_REPORTED_DIAGNOSTIC

    def __post_init__(self) -> None:
        for name in ("total_llm_calls_reported", "harness_observed_calls"):
            v = getattr(self, name)
            if v is not None:
                require_count(v, f"WorkflowReportedDiagnostics.{name}")
        if self.label != RUNTIME_REPORTED_DIAGNOSTIC:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"diagnostics label is fixed at {RUNTIME_REPORTED_DIAGNOSTIC}")


@dataclass(frozen=True)
class QualityEvaluationRecord:
    schema_version: str
    evaluation_id: str
    manifest_digest: str
    method: ReasoningMethodRef
    record_digest: str
    case_set_digest: str
    evaluator_declaration_digest: str
    scoring_instruction_digest: str
    quality_aggregation: AggregationRef
    claim_digest: str
    quality_result_digest: str
    evaluated_by: str
    evaluated_at: datetime
    independence_status: str = INDEPENDENCE_DECLARED_UNVERIFIED
    evaluation_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "QualityEvaluationRecord.schema_version")
        require_nonblank(self.evaluation_id, "QualityEvaluationRecord.evaluation_id")
        for name in ("manifest_digest", "record_digest", "case_set_digest", "evaluator_declaration_digest", "scoring_instruction_digest", "claim_digest", "quality_result_digest"):
            require_digest(getattr(self, name), f"QualityEvaluationRecord.{name}")
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualityEvaluationRecord.method must be a ReasoningMethodRef")
        if not isinstance(self.quality_aggregation, AggregationRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "QualityEvaluationRecord.quality_aggregation must be an AggregationRef")
        require_nonblank(self.evaluated_by, "QualityEvaluationRecord.evaluated_by")
        require_tzaware(self.evaluated_at, "QualityEvaluationRecord.evaluated_at")
        if self.independence_status != INDEPENDENCE_DECLARED_UNVERIFIED:
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"independence_status is fixed at {INDEPENDENCE_DECLARED_UNVERIFIED} in 4A")
        settle_digest(self, "evaluation_digest", digest_of(self, exclude=("evaluation_digest",)))


@dataclass(frozen=True)
class PilotObservation:
    schema_version: str
    observation_id: str
    manifest_digest: str
    method: ReasoningMethodRef
    roles: Tuple[PilotRole, ...]
    task_class_digest: str
    binding: BindingRef
    model_ref: str
    case_set_digest: str
    case_count: int
    resource_aggregation: AggregationRef
    quality_aggregation: AggregationRef
    record_digest: str
    attestation_envelope_digest: Optional[str]
    quality_evaluation_digest: str
    diagnostics: WorkflowReportedDiagnostics
    observed_at: datetime
    observation_digest: str = ""

    def __post_init__(self) -> None:
        require_nonblank(self.schema_version, "PilotObservation.schema_version")
        require_nonblank(self.observation_id, "PilotObservation.observation_id")
        for name in ("manifest_digest", "task_class_digest", "case_set_digest", "record_digest", "quality_evaluation_digest"):
            require_digest(getattr(self, name), f"PilotObservation.{name}")
        if self.attestation_envelope_digest is not None:
            require_digest(self.attestation_envelope_digest, "PilotObservation.attestation_envelope_digest")
        if not isinstance(self.method, ReasoningMethodRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotObservation.method must be a ReasoningMethodRef")
        if not isinstance(self.roles, tuple) or not self.roles or self.roles != sorted_roles(self.roles):
            raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "roles must be a non-empty member-ordered tuple")
        if not isinstance(self.binding, BindingRef):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotObservation.binding must be a BindingRef")
        require_nonblank(self.model_ref, "PilotObservation.model_ref")
        require_count(self.case_count, "PilotObservation.case_count", positive=True)
        for name in ("resource_aggregation", "quality_aggregation"):
            if not isinstance(getattr(self, name), AggregationRef):
                raise ContractError(ContractErrorCode.REF_BLANK_FIELD, f"PilotObservation.{name} must be an AggregationRef")
        if not isinstance(self.diagnostics, WorkflowReportedDiagnostics):
            raise ContractError(ContractErrorCode.REF_BLANK_FIELD, "PilotObservation.diagnostics must be a WorkflowReportedDiagnostics")
        require_tzaware(self.observed_at, "PilotObservation.observed_at")
        settle_digest(self, "observation_digest", digest_of(self, exclude=("observation_digest",)))


def capture_boundary_ref_of(capture_refs: Tuple[str, ...]) -> str:
    """The envelope's capture_boundary_ref: JCS digest of the ordered capture fingerprints
    (record.telemetry.capture_refs without its leading manifest-digest stamp)."""
    return digest_of(list(capture_refs[1:]))


def validate_observation(
    observation: PilotObservation,
    *,
    validated: ValidatedManifest,
    manifest: PilotStudyManifest,
    plan: ResearchComparisonPlan,
    record: ReasoningMethodExecutionRecord,
    benchmark: BenchmarkManifest,
    evaluation: QualityEvaluationRecord,
    quality_claim: MetricClaim,
    quality_result: QualityResult,
    advisory: Optional[ReasoningMethodAdvisory] = None,
    attestation: Optional[AttestationEnvelope] = None,
) -> None:
    """§3.4. Refuses any missing or mismatched object; infers nothing from digests alone."""
    for obj, cls, name in (
        (observation, PilotObservation, "observation"), (validated, ValidatedManifest, "validated"), (manifest, PilotStudyManifest, "manifest"),
        (plan, ResearchComparisonPlan, "plan"), (record, ReasoningMethodExecutionRecord, "record"), (benchmark, BenchmarkManifest, "benchmark"),
        (evaluation, QualityEvaluationRecord, "evaluation"), (quality_claim, MetricClaim, "quality_claim"), (quality_result, QualityResult, "quality_result"),
    ):
        if not isinstance(obj, cls):
            raise TypeError(f"validate_observation: {name} must be a {cls.__name__}")
    if validated.manifest_digest != manifest.manifest_digest or validated.advisory_digest != manifest.advisory_digest:
        raise PilotError(PilotErrorCode.MANIFEST_NOT_VALIDATED, "the ValidatedManifest is not for this manifest")
    if observation.manifest_digest != manifest.manifest_digest or manifest.plan != plan:
        raise PilotError(PilotErrorCode.MANIFEST_MISMATCH, "observation, manifest and plan disagree")
    if record.record_digest != observation.record_digest or record.method != observation.method:
        raise PilotError(PilotErrorCode.RECORD_MISMATCH, "record digest or method differs from the observation's")
    if record.task_class_digest != observation.task_class_digest or observation.task_class_digest != plan.task_class.task_class_digest:
        raise PilotError(PilotErrorCode.RECORD_MISMATCH, "task class digest differs")
    if record.binding != observation.binding or observation.binding != plan.binding:
        raise PilotError(PilotErrorCode.RECORD_MISMATCH, "binding differs")
    if record.model_ref != observation.model_ref:
        raise PilotError(PilotErrorCode.RECORD_MISMATCH, "model_ref differs")
    if benchmark.benchmark_manifest_digest != observation.case_set_digest or observation.case_set_digest != plan.task_class.benchmark_set_digest or benchmark.case_count != observation.case_count:
        raise PilotError(PilotErrorCode.BENCHMARK_MANIFEST_MISMATCH, "benchmark manifest, observation and task class disagree on the case set")
    if observation.resource_aggregation != manifest.resource_aggregation or observation.quality_aggregation != manifest.quality_aggregation:
        raise PilotError(PilotErrorCode.AGGREGATION_MISMATCH, "aggregation references differ from the manifest's")
    if (
        evaluation.evaluation_digest != observation.quality_evaluation_digest
        or evaluation.manifest_digest != manifest.manifest_digest
        or evaluation.record_digest != record.record_digest
        or evaluation.method != observation.method
        or evaluation.case_set_digest != benchmark.benchmark_manifest_digest
        or evaluation.evaluator_declaration_digest != manifest.evaluator.declaration_digest
        or evaluation.scoring_instruction_digest != manifest.evaluator.scoring_instruction_digest
        or evaluation.quality_aggregation != manifest.quality_aggregation
        or evaluation.evaluated_by != manifest.evaluator.evaluator_identity
        or claim_digest(quality_claim) != evaluation.claim_digest
        or evaluation.evaluation_id not in quality_claim.evidence_refs
        or quality_claim.transformation_method is not TransformationMethod.CALCULATED
    ):
        raise PilotError(PilotErrorCode.QUALITY_EVALUATION_MISMATCH, "evaluation record, claim and manifest evaluator disagree")
    if (
        quality_result_digest(quality_result) != evaluation.quality_result_digest
        or quality_result.method != observation.method
        or quality_result.claim_ref != quality_claim.claim_id
        or quality_result.value != quality_claim.value
        or quality_result.aggregation != manifest.quality_aggregation
    ):
        raise PilotError(PilotErrorCode.QUALITY_RESULT_MISMATCH, "quality result disagrees with the evaluation record or claim")
    assignment = manifest.assignment(observation.method)
    if assignment is None or assignment.roles != observation.roles:
        raise PilotError(PilotErrorCode.ROLE_INCONSISTENT, "observation roles differ from the manifest assignment")
    if PilotRole.ADVISOR_QUALIFIED in observation.roles:
        if advisory is None:
            raise PilotError(PilotErrorCode.ADVISORY_REQUIRED, "an ADVISOR_QUALIFIED observation requires the advisory")
        if advisory.advisory_digest != manifest.advisory_digest or observation.method not in {q.method for q in advisory.qualifying}:
            raise PilotError(PilotErrorCode.ADVISORY_MISMATCH, "the advisory did not qualify this method")
    if observation.attestation_envelope_digest is not None:
        if attestation is None or not isinstance(attestation, AttestationEnvelope):
            raise PilotError(PilotErrorCode.ATTESTATION_MISMATCH, "observation names an attestation that was not supplied")
        allowed = set(manifest.capture_boundary.allowed_attested_fields)
        if (
            attestation.envelope_digest != observation.attestation_envelope_digest
            or attestation.record_digest != record.record_digest
            or attestation.attester_identity != manifest.capture_boundary.boundary_identity
            or not attestation.attested_fields
            or not set(attestation.attested_fields) <= allowed
            or LLM_CALLS_FIELD not in attestation.attested_fields
            or attestation.capture_boundary_ref != capture_boundary_ref_of(record.telemetry.capture_refs)
        ):
            raise PilotError(PilotErrorCode.ATTESTATION_MISMATCH, "attestation disagrees with the record, declaration or observation")
    if not record.telemetry.capture_refs or record.telemetry.capture_refs[0] != observation.manifest_digest:
        raise PilotError(PilotErrorCode.MANIFEST_NOT_PRIOR, "record capture_refs do not stamp this manifest digest")
    if record.captured_at < manifest.preregistered_at or observation.observed_at < manifest.preregistered_at:
        raise PilotError(PilotErrorCode.MANIFEST_NOT_PRIOR, "record or observation precedes the manifest (local chronology check, not proof)")


__all__ = [
    "PILOT_OBSERVATION_SCHEMA_VERSION", "QUALITY_EVALUATION_SCHEMA_VERSION", "RUNTIME_REPORTED_DIAGNOSTIC",
    "claim_digest", "quality_result_digest", "capture_boundary_ref_of",
    "WorkflowReportedDiagnostics", "QualityEvaluationRecord", "PilotObservation", "validate_observation",
]

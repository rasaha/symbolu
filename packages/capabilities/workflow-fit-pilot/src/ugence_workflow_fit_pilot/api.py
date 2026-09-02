"""Curated public API of ugence-workflow-fit-pilot (Phase 4A, research-only)."""

from .boundary.attestation import canonical_order, envelope_id_for, issue_attestation, record_canonical_payload, recompute_telemetry, supported_attested_fields
from .boundary.client import BoundaryConnection, GatewayStubClient
from .boundary.process import BoundaryProcess
from .boundary.transport import STDIO_ENDPOINT, UNIX_SOCKETS_AVAILABLE
from .boundary.frames import CaptureAttemptStatus, CaptureRecord, GatewayRequest, GatewayResponse, ProviderPort, ProviderResult, RunControlFrame
from .contracts.benchmark import BENCHMARK_MANIFEST_SCHEMA_VERSION, BenchmarkManifest, case_list_digest
from .contracts.coverage import ChallengerCoverageReport, SuccessSummary, build_coverage_report, success_summary
from .contracts.evaluator import INDEPENDENCE_DECLARED_UNVERIFIED, EvaluatorKind, QualityEvaluatorDeclaration
from .contracts.lifecycle import (
    APPROVAL_STATUS_NONE,
    PILOT_STATE_SCHEMA_VERSION,
    LifecycleEvent,
    PilotConfigurationState,
    PilotConfigurationStateRecord,
    RevisionScope,
    derive_revision_scope,
    propose,
    transition,
    validate_lineage,
)
from .contracts.manifest import (
    ATTESTABLE_TELEMETRY_FIELDS,
    LLM_CALLS_FIELD,
    PILOT_MANIFEST_SCHEMA_VERSION,
    PREREGISTRATION_DECLARED_UNVERIFIED,
    CaptureBoundaryDeclaration,
    PilotMethodAssignment,
    PilotRole,
    PilotStudyManifest,
    PreregistrationStatus,
    ValidatedManifest,
    admissible_methods,
    validate_manifest,
)
from .contracts.observation import (
    PILOT_OBSERVATION_SCHEMA_VERSION,
    QUALITY_EVALUATION_SCHEMA_VERSION,
    RUNTIME_REPORTED_DIAGNOSTIC,
    PilotObservation,
    QualityEvaluationRecord,
    WorkflowReportedDiagnostics,
    capture_boundary_ref_of,
    claim_digest,
    quality_result_digest,
    validate_observation,
)
from .errors import PilotError, PilotErrorCode
from .report import FORBIDDEN_RENDERINGS, render
from .runner import ExecutionOutcome, MethodRun, PilotCase, PilotIdentity, PilotRunResult, QualityScorerPort, WorkflowExecutorPort, check_evaluator_identity, run_pilot
from .version import __version__

__all__ = [
    "__version__", "PilotError", "PilotErrorCode",
    "PILOT_MANIFEST_SCHEMA_VERSION", "PREREGISTRATION_DECLARED_UNVERIFIED", "ATTESTABLE_TELEMETRY_FIELDS", "LLM_CALLS_FIELD",
    "PilotRole", "PreregistrationStatus", "PilotMethodAssignment", "CaptureBoundaryDeclaration", "PilotStudyManifest", "ValidatedManifest", "admissible_methods", "validate_manifest",
    "BENCHMARK_MANIFEST_SCHEMA_VERSION", "BenchmarkManifest", "case_list_digest",
    "INDEPENDENCE_DECLARED_UNVERIFIED", "EvaluatorKind", "QualityEvaluatorDeclaration",
    "PILOT_OBSERVATION_SCHEMA_VERSION", "QUALITY_EVALUATION_SCHEMA_VERSION", "RUNTIME_REPORTED_DIAGNOSTIC",
    "WorkflowReportedDiagnostics", "QualityEvaluationRecord", "PilotObservation", "validate_observation", "claim_digest", "quality_result_digest", "capture_boundary_ref_of",
    "ChallengerCoverageReport", "SuccessSummary", "build_coverage_report", "success_summary",
    "PILOT_STATE_SCHEMA_VERSION", "APPROVAL_STATUS_NONE", "PilotConfigurationState", "RevisionScope", "LifecycleEvent",
    "derive_revision_scope", "PilotConfigurationStateRecord", "propose", "transition", "validate_lineage",
    "CaptureAttemptStatus", "RunControlFrame", "ProviderPort", "ProviderResult", "GatewayRequest", "GatewayResponse", "CaptureRecord",
    "canonical_order", "recompute_telemetry", "supported_attested_fields", "record_canonical_payload", "envelope_id_for", "issue_attestation",
    "BoundaryConnection", "GatewayStubClient", "BoundaryProcess", "STDIO_ENDPOINT", "UNIX_SOCKETS_AVAILABLE",
    "PilotCase", "ExecutionOutcome", "WorkflowExecutorPort", "QualityScorerPort", "PilotIdentity", "MethodRun", "PilotRunResult", "run_pilot", "check_evaluator_identity",
    "render", "FORBIDDEN_RENDERINGS",
]

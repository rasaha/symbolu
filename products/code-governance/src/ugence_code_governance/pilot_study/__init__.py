"""Bounded shadow-pilot validation study (MVP 1F).

Runs the MVP 1E pilot operator against a tightly bounded environment, collects
honest reviewer feedback, measures whether Ugence catches governance conditions
beyond ordinary CI, analyzes disagreements and policy/source problems, and produces
an evidence-based enforcement-readiness verdict. Execution stays DISABLED; supplied
snapshots and synthetic scenarios are never described as live enterprise evidence;
reviewer feedback never changes policy automatically; a verdict never enables
execution.
"""
from __future__ import annotations

from .adverse import PilotAdverseCase, collect_adverse_cases
from .analysis import PilotStudyEvaluation, PilotStudyMetrics, analyze_pilot_results
from .annotation import PilotEvaluationAnnotation
from .calibration import (
    PilotCalibrationRecommendation,
    PilotReplayResult,
    generate_calibration_recommendations,
    replay_pilot_policy,
)
from .candidates import (
    PilotCandidate,
    PilotCandidateSelectionRecord,
    select_pilot_candidates,
)
from .checkpoints import PilotCheckpointRecord, create_pilot_checkpoint
from .errors import (
    AnnotationError,
    EvidencePackError,
    PilotSafetyBlocked,
    PilotStudyError,
    StudyAmendmentError,
    StudyManifestError,
)
from .evidence_pack import (
    EvidencePackVerification,
    PACK_VERSION,
    build_pilot_evidence_pack,
    verify_pilot_evidence_pack,
)
from .manifest import (
    MANIFEST_SCHEMA_VERSION,
    PilotAmendmentRecord,
    PilotPrePilotFreezeRecord,
    PilotStudyManifest,
    freeze_pilot_study,
    validate_study_manifest,
)
from .readiness import PilotReadinessAssessment, assess_enforcement_readiness
from .security import PilotSecurityVerification, run_pilot_security_verification
from .vocab import (
    ActualOutcome,
    AdverseCaseKind,
    AmendmentReason,
    CalibrationAdjustment,
    CheckpointKind,
    CheckpointRecommendation,
    EvidenceStatus,
    IncrementalValue,
    IncrementalValueLabel,
    InterventionAssessment,
    LIVE_EVIDENCE_CLASSES,
    NON_LIVE_EVIDENCE_CLASSES,
    PilotCohort,
    PilotEvidenceClass,
    PilotReadinessVerdict,
    ReviewMode,
    RootCause,
    StatusAssessment,
)

__all__ = [
    # manifest + freeze + amendments
    "PilotStudyManifest", "validate_study_manifest", "MANIFEST_SCHEMA_VERSION",
    "PilotPrePilotFreezeRecord", "freeze_pilot_study", "PilotAmendmentRecord",
    # evidence classes + cohorts + vocab
    "PilotEvidenceClass", "LIVE_EVIDENCE_CLASSES", "NON_LIVE_EVIDENCE_CLASSES", "PilotCohort",
    "ReviewMode", "StatusAssessment", "InterventionAssessment", "RootCause",
    "IncrementalValue", "IncrementalValueLabel", "ActualOutcome", "AmendmentReason",
    "CalibrationAdjustment", "AdverseCaseKind", "CheckpointKind", "CheckpointRecommendation",
    "PilotReadinessVerdict", "EvidenceStatus",
    # candidates
    "PilotCandidate", "PilotCandidateSelectionRecord", "select_pilot_candidates",
    # annotations
    "PilotEvaluationAnnotation",
    # analysis
    "PilotStudyEvaluation", "PilotStudyMetrics", "analyze_pilot_results",
    # calibration + replay
    "PilotCalibrationRecommendation", "generate_calibration_recommendations",
    "PilotReplayResult", "replay_pilot_policy",
    # adverse cases + checkpoints
    "PilotAdverseCase", "collect_adverse_cases",
    "PilotCheckpointRecord", "create_pilot_checkpoint",
    # evidence pack
    "PACK_VERSION", "build_pilot_evidence_pack", "verify_pilot_evidence_pack",
    "EvidencePackVerification",
    # readiness
    "PilotReadinessAssessment", "assess_enforcement_readiness",
    # security
    "PilotSecurityVerification", "run_pilot_security_verification",
    # errors
    "PilotStudyError", "StudyManifestError", "StudyAmendmentError", "AnnotationError",
    "EvidencePackError", "PilotSafetyBlocked",
]

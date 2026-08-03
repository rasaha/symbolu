"""Deterministic Assessment Runtime (Phase 3B).

Executes the Phase-3A evaluation constitution *without any model inference*. It
binds eligible evidence to criteria, records missing evidence, validates
externally-supplied observations against immutable scales, records uncertainty
and conflicts, computes *structural* completeness, and produces immutable,
advisory-only assessment snapshots. It never scores, ranks, recommends, decides,
or interprets evidence.
"""

from __future__ import annotations

from .assessment import Assessment, CapabilityAssessment
from .completeness import CompletenessResult
from .evidence_binding import EvidenceBinding, ExcludedEvidenceRecord
from .missing_evidence import MissingEvidenceRecord
from .observation import Observation
from .status import (
    PERMITTED_SUPPLIERS,
    AssessmentStatus,
    BindingProvenance,
    CompletenessStatus,
    ObservationValidationStatus,
    SupplierType,
    WorkspaceStatus,
)
from .validation import ValidationIssue, ValidationResult, validate_value_against_scale
from .workspace import AssessmentWorkspace, CapabilityBinding

__all__ = [
    "AssessmentWorkspace",
    "CapabilityBinding",
    "Assessment",
    "CapabilityAssessment",
    "EvidenceBinding",
    "ExcludedEvidenceRecord",
    "MissingEvidenceRecord",
    "Observation",
    "CompletenessResult",
    "ValidationIssue",
    "ValidationResult",
    "validate_value_against_scale",
    "WorkspaceStatus",
    "AssessmentStatus",
    "CompletenessStatus",
    "BindingProvenance",
    "SupplierType",
    "PERMITTED_SUPPLIERS",
    "ObservationValidationStatus",
]

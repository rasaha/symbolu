"""Rubric contracts (Phase 3A) — how a role is assessed, frozen before any AI.

Immutable rubric specifications: capability mappings + weights, scoring scales,
evidence-admissibility rules, reason codes, uncertainty contracts, conflict
representation, and the approval lifecycle. No candidate data, no scores.
"""

from __future__ import annotations

from .approval import (
    ALLOWED_TRANSITIONS,
    ApprovalAction,
    ApprovalRecord,
    ApprovalRole,
    RubricStatus,
    role_for_target,
    validate_transition,
)
from .capability_mapping import RubricCapability
from .conflicts import Conflict, ConflictSeverity, ConflictSource, ConflictStatus
from .evidence_rules import (
    DEFAULT_ADMISSIBILITY_POLICY,
    AdmissibilityPolicy,
    EvidenceAdmissibility,
    EvidenceDescriptor,
    EvidenceRule,
    MissingEvidenceStatus,
)
from .rubric import Rubric
from .scoring_scale import (
    STANDARD_SCALES,
    ScaleType,
    ScoringScale,
    is_standard_scale,
)
from .uncertainty import UncertaintyLevel, UncertaintyRule

__all__ = [
    "Rubric",
    "RubricStatus",
    "RubricCapability",
    "ApprovalRecord",
    "ApprovalRole",
    "ApprovalAction",
    "ALLOWED_TRANSITIONS",
    "validate_transition",
    "role_for_target",
    "ScoringScale",
    "ScaleType",
    "STANDARD_SCALES",
    "is_standard_scale",
    "EvidenceRule",
    "EvidenceDescriptor",
    "EvidenceAdmissibility",
    "MissingEvidenceStatus",
    "AdmissibilityPolicy",
    "DEFAULT_ADMISSIBILITY_POLICY",
    "UncertaintyLevel",
    "UncertaintyRule",
    "Conflict",
    "ConflictSource",
    "ConflictSeverity",
    "ConflictStatus",
]

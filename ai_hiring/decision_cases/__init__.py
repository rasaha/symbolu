"""DecisionCase aggregate and lifecycle contracts (Phase 4A).

The governed case container that links evidence, assessments, recommendations,
human authority, and decisions **without collapsing them into one object**.
Assessment, recommendation, decision, authorization, and execution are distinct
records with distinct authority; Phase 4A implements the first three relationships
and never executes an action.
"""

from __future__ import annotations

from .authority import AuthorityContext
from .case import DecisionCase
from .decision import DecisionRecord
from .lifecycle import ALLOWED_TRANSITIONS, is_legal_transition
from .override import OverrideRecord
from .recommendation import RecommendationRecord
from .review import ReviewTask
from .status import (
    AuthorityType,
    CaseStatus,
    DecisionOutcome,
    EffectiveStatus,
    GeneratorType,
    HUMAN_AUTHORITIES,
    OperatingMode,
    ProposedOutcome,
    RecommendationStatus,
    ReviewTaskStatus,
    ReviewTaskType,
    TERMINAL_CASE_STATUSES,
)
from .subject import SubjectRef, VersionedRef
from .validation import (
    CaseValidationIssue,
    CaseValidationResult,
    DecisionReadinessResult,
)

__all__ = [
    # contracts
    "DecisionCase",
    "RecommendationRecord",
    "DecisionRecord",
    "OverrideRecord",
    "ReviewTask",
    "AuthorityContext",
    "SubjectRef",
    "VersionedRef",
    # vocabularies
    "CaseStatus",
    "OperatingMode",
    "ProposedOutcome",
    "GeneratorType",
    "RecommendationStatus",
    "DecisionOutcome",
    "AuthorityType",
    "EffectiveStatus",
    "ReviewTaskType",
    "ReviewTaskStatus",
    "HUMAN_AUTHORITIES",
    "TERMINAL_CASE_STATUSES",
    # lifecycle + validation
    "ALLOWED_TRANSITIONS",
    "is_legal_transition",
    "CaseValidationIssue",
    "CaseValidationResult",
    "DecisionReadinessResult",
]

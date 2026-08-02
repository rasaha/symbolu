"""MVP 1B — shadow Action Clearance integration for Code Governance.

Composes the canonical Action Clearance capability through its public API only.
The canonical package is never modified; Code Governance owns the adapter, the
operational-signal boundary, the company policy projection, and the deterministic
human-intervention routing.
"""
from __future__ import annotations

from .adapter import (
    ActionClearanceShadowAdapter,
    ELIGIBLE_ACTIONGATE_OUTCOMES,
    is_eligible,
)
from .intervention import (
    AuthorityRole,
    HumanInterventionAssessment,
    InterventionRoutingPolicy,
    InterventionType,
    RouteEntry,
    assess_intervention,
)
from .profile import CodeGovernanceClearanceProfile, RepositoryClassification
from .records import ActionClearanceEvaluationRecord, evaluation_record_id
from .signal_adapter import ClearanceInputError, build_trusted_signals
from .snapshot import CodeGovernanceOperationalSnapshot
from .source_projection import SignalSourceEntry, TrustedSignalSourceProjection

__all__ = [
    "ActionClearanceShadowAdapter",
    "is_eligible",
    "ELIGIBLE_ACTIONGATE_OUTCOMES",
    "CodeGovernanceClearanceProfile",
    "RepositoryClassification",
    "CodeGovernanceOperationalSnapshot",
    "TrustedSignalSourceProjection",
    "SignalSourceEntry",
    "build_trusted_signals",
    "ClearanceInputError",
    "ActionClearanceEvaluationRecord",
    "evaluation_record_id",
    "HumanInterventionAssessment",
    "InterventionRoutingPolicy",
    "InterventionType",
    "AuthorityRole",
    "RouteEntry",
    "assess_intervention",
]

"""Autonomous Control Plane (ACP) — Phase 0 scaffolding.

Additive, independently importable, and DISABLED BY DEFAULT: no existing
robotics or BCVF call site imports this package, so importing it changes no
runtime behaviour. It provides frozen canonical envelopes, deterministic
interfaces, reference fail-closed implementations, canonical identity, a
structured decision trace, and the failure-state scaffolding described in the
approved ``acp/`` architecture documents.

Standard library only — no numpy, no ROS, no hardware dependency in the core.

This is Phase 0 (interface freeze). It does NOT replace any BCVF call site and is
not wired into the runtime; see ``Project_documentation/control_plane/acp/ACP_PHASE1_READINESS.md`` for what comes
next.
"""
from __future__ import annotations

__version__ = "0.1.0-phase0"

from .errors import (ACPError, AuthorizationBindingError, AuthorizationError,
                     ConfigurationError, IdentityError, IllegalTransitionError,
                     NonFiniteValueError, SchemaValidationError,
                     StaleAuthorizationError)
from .identity import canonical_json, canonicalize, identity, normalize_float
from .world_state import (CanonicalWorldState, FreshnessSummary, OperatingMode,
                          Pose, Velocity)
from .predictor_evidence import (BCVFAdvisory, CalibrationState, DropoutState,
                                 PredictorEvidence, ReliabilityState,
                                 VarianceState)
from .constraints import (ConstraintKind, ConstraintResult,
                          NoConfiguredConstraintsEvaluator)
from .envelopes import (ActionDecision, ActionType, CanonicalActionCandidate)
from .authorization import (ControlAuthorization, ReferenceCommitRevalidator,
                            ReferenceControlAuthorizer)
from .action_selection import (AdmissibilityResult, DeterministicActionSelector,
                               LexicographicActionSelector, SelectionOutcome,
                               SoftObjective, filter_admissible)
from .decision_trace import (DecisionTrace, InMemoryDecisionTraceSink,
                             RejectedCandidate)
from .failure_state import (FailureState, FailureStateMachine, TransitionRecord,
                            LEGAL_TRANSITIONS, MANUAL_RESET_TRANSITIONS,
                            is_legal, requires_manual_reset)
# Phase 1 — hard-constraint library, call-site adapters, shadow evaluation.
from .constraint_library import (SafeFallbackConstraint, ThresholdConstraint,
                                 conflict_constraints, deliberative_constraints,
                                 evaluate_constraint_set, task_allocation_constraints)
from .adapters import (AdaptedSet, adapt_conflict, adapt_deliberative,
                       adapt_task_allocation)
from .shadow import ShadowClass, ShadowRecord, acp_evaluate, classify
# Phase 2 — physical-evidence contract (stdlib core; adapters live in the
# safety_adapters/ subpackage and are imported on demand, not here).
from .physical_evidence import PhysicalEvidence, PhysicalValidity

__all__ = [
    "__version__",
    # errors
    "ACPError", "SchemaValidationError", "NonFiniteValueError", "IdentityError",
    "IllegalTransitionError", "AuthorizationError", "StaleAuthorizationError",
    "AuthorizationBindingError", "ConfigurationError",
    # identity
    "identity", "canonicalize", "canonical_json", "normalize_float",
    # world state
    "CanonicalWorldState", "Pose", "Velocity", "FreshnessSummary", "OperatingMode",
    # predictor evidence
    "PredictorEvidence", "BCVFAdvisory", "ReliabilityState", "VarianceState",
    "DropoutState", "CalibrationState",
    # constraints
    "ConstraintResult", "ConstraintKind", "NoConfiguredConstraintsEvaluator",
    # action envelopes
    "CanonicalActionCandidate", "ActionType", "ActionDecision",
    # authorization
    "ControlAuthorization", "ReferenceControlAuthorizer",
    "ReferenceCommitRevalidator",
    # selection
    "DeterministicActionSelector", "LexicographicActionSelector", "SoftObjective",
    "SelectionOutcome", "AdmissibilityResult", "filter_admissible",
    # trace
    "DecisionTrace", "RejectedCandidate", "InMemoryDecisionTraceSink",
    # failure state
    "FailureState", "FailureStateMachine", "TransitionRecord",
    "LEGAL_TRANSITIONS", "MANUAL_RESET_TRANSITIONS", "is_legal",
    "requires_manual_reset",
    # Phase 1
    "ThresholdConstraint", "SafeFallbackConstraint", "evaluate_constraint_set",
    "deliberative_constraints", "conflict_constraints", "task_allocation_constraints",
    "AdaptedSet", "adapt_deliberative", "adapt_conflict", "adapt_task_allocation",
    "ShadowClass", "ShadowRecord", "acp_evaluate", "classify",
]

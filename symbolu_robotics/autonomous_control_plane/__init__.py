"""Autonomous Control Plane (ACP) — Phase 0 scaffolding.

Additive, independently importable, and DISABLED BY DEFAULT: no existing
robotics or BCVF call site imports this package, so importing it changes no
runtime behaviour. It provides frozen canonical envelopes, deterministic
interfaces, reference fail-closed implementations, canonical identity, a
structured decision trace, and the failure-state scaffolding described in the
approved ``acp/`` architecture documents.

Standard library only — no numpy, no ROS, no hardware dependency in the core.

This is Phase 0 (interface freeze). It does NOT replace any BCVF call site and is
not wired into the runtime; see ``acp/ACP_PHASE1_READINESS.md`` for what comes
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
from .action_selection import (DeterministicActionSelector, SelectionOutcome,
                               SoftObjective)
from .decision_trace import (DecisionTrace, InMemoryDecisionTraceSink,
                             RejectedCandidate)
from .failure_state import (FailureState, FailureStateMachine, TransitionRecord,
                            LEGAL_TRANSITIONS, MANUAL_RESET_TRANSITIONS,
                            is_legal, requires_manual_reset)

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
    "DeterministicActionSelector", "SoftObjective", "SelectionOutcome",
    # trace
    "DecisionTrace", "RejectedCandidate", "InMemoryDecisionTraceSink",
    # failure state
    "FailureState", "FailureStateMachine", "TransitionRecord",
    "LEGAL_TRANSITIONS", "MANUAL_RESET_TRANSITIONS", "is_legal",
    "requires_manual_reset",
]

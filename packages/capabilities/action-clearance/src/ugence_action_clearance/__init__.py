"""Ugence Action Clearance — deterministic, domain-neutral clearance evaluator.

> Action Clearance may preserve, narrow, hold, escalate, or block an existing
> authorization. It may never create authority, broaden authorization, replace
> ActionGate, dispatch execution, or own authoritative one-time consumption.

This package answers exactly one question: given an existing exact-action
authorization and a set of trusted current-state signals, is that exact action
**clear to execute at this evaluation time**? It performs no external calls,
stores nothing, reserves no execution, and implements no domain adapters.

The public API is curated in :mod:`ugence_action_clearance.api` and re-exported
here for convenience.
"""
from __future__ import annotations

from .api import (
    ActionClearanceError,
    ActionClearanceEvaluator,
    AuthorizationContext,
    AuthorizationOutcome,
    AuthorizedActionIdentity,
    ClearanceObligation,
    ClearancePolicy,
    ClearancePolicyContext,
    ClearanceReasonCode,
    ClearanceReceiptBody,
    ClearanceRequest,
    ClearanceResult,
    ClearanceStatus,
    ConstraintKind,
    ConsumptionStatus,
    CONTRACT_VERSION,
    EffectiveConstraint,
    FingerprintError,
    SignalBundle,
    SignalProvenance,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    TrustedSignal,
    UnsupportedVersionError,
    ValidationError,
    __version__,
    evaluate_clearance,
)

__all__ = [
    "__version__",
    "CONTRACT_VERSION",
    "ActionClearanceEvaluator",
    "evaluate_clearance",
    "ClearanceRequest",
    "ClearancePolicyContext",
    "ClearanceResult",
    "ClearanceReceiptBody",
    "ClearanceStatus",
    "ClearanceReasonCode",
    "AuthorizationContext",
    "AuthorizedActionIdentity",
    "AuthorizationOutcome",
    "TrustedSignal",
    "SignalProvenance",
    "SignalBundle",
    "SignalTrustLevel",
    "SignalStatus",
    "SignalType",
    "ConsumptionStatus",
    "ClearancePolicy",
    "EffectiveConstraint",
    "ConstraintKind",
    "ClearanceObligation",
    "ActionClearanceError",
    "ValidationError",
    "FingerprintError",
    "UnsupportedVersionError",
]

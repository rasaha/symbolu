"""Neutral public models for Action Clearance."""
from __future__ import annotations

from .authorization import AuthorizationContext, AuthorizedActionIdentity
from .constraints import (
    ClearanceObligation,
    ConstraintKind,
    ConstraintOutcome,
    EffectiveConstraint,
    IntersectionResult,
    intersect,
)
from .enums import (
    AuthorizationOutcome,
    ClearanceStatus,
    ConsumptionStatus,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
    combine_statuses,
    trust_at_least,
)
from .request import ClearancePolicyContext, ClearanceRequest
from .result import ClearanceReceiptBody, ClearanceResult
from .signals import SignalBundle, SignalProvenance, TrustedSignal

__all__ = [
    "AuthorizationContext",
    "AuthorizedActionIdentity",
    "EffectiveConstraint",
    "ConstraintKind",
    "ConstraintOutcome",
    "IntersectionResult",
    "intersect",
    "ClearanceObligation",
    "ClearanceStatus",
    "SignalStatus",
    "SignalType",
    "SignalTrustLevel",
    "ConsumptionStatus",
    "AuthorizationOutcome",
    "combine_statuses",
    "trust_at_least",
    "ClearancePolicyContext",
    "ClearanceRequest",
    "ClearanceResult",
    "ClearanceReceiptBody",
    "SignalBundle",
    "SignalProvenance",
    "TrustedSignal",
]

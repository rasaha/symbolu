"""Curated public API for Action Clearance.

Only intentional, stable symbols are exported. Internal canonicalization helpers
and private policy implementation details are not part of this surface.
"""
from __future__ import annotations

from .errors import (
    ActionClearanceError,
    FingerprintError,
    UnsupportedVersionError,
    ValidationError,
)
from .evaluation import ActionClearanceEvaluator, evaluate_clearance
from .models.authorization import AuthorizationContext, AuthorizedActionIdentity
from .models.constraints import (
    ClearanceObligation,
    ConstraintKind,
    EffectiveConstraint,
)
from .models.enums import (
    AuthorizationOutcome,
    ClearanceStatus,
    ConsumptionStatus,
    SignalStatus,
    SignalTrustLevel,
    SignalType,
)
from .models.request import ClearancePolicyContext, ClearanceRequest
from .models.result import ClearanceReceiptBody, ClearanceResult
from .models.signals import SignalBundle, SignalProvenance, TrustedSignal
from .policy import ClearancePolicy
from .reason_codes import ClearanceReasonCode
from .version import CONTRACT_VERSION, __version__

__all__ = [
    "__version__",
    "CONTRACT_VERSION",
    # evaluator
    "ActionClearanceEvaluator",
    "evaluate_clearance",
    # request / result
    "ClearanceRequest",
    "ClearancePolicyContext",
    "ClearanceResult",
    "ClearanceReceiptBody",
    # status / reasons
    "ClearanceStatus",
    "ClearanceReasonCode",
    # authorization / action identity
    "AuthorizationContext",
    "AuthorizedActionIdentity",
    "AuthorizationOutcome",
    # signals
    "TrustedSignal",
    "SignalProvenance",
    "SignalBundle",
    "SignalTrustLevel",
    "SignalStatus",
    "SignalType",
    "ConsumptionStatus",
    # policy / constraints
    "ClearancePolicy",
    "EffectiveConstraint",
    "ConstraintKind",
    "ClearanceObligation",
    # errors
    "ActionClearanceError",
    "ValidationError",
    "FingerprintError",
    "UnsupportedVersionError",
]

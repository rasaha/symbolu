"""Curated public API for Context Minimization.

Import stable names from here:

    from ugence_context_minimization.api import (
        Context, ContextUnit, minimize_context, structural_minimize, InvarianceOracle,
    )

This surface is deliberately small. It does NOT export benchmark corpora, ActionGate
internals, model clients, detector-training utilities, or internal ranking helpers.
"""

from __future__ import annotations

from . import reasons
from .errors import (
    ContextMinimizationError,
    InvalidRequestError,
    InvalidUnitError,
    OracleRequiredError,
)
from .models import (
    Context,
    ContextUnit,
    EquivalenceStatus,
    MinimizationMode,
    MinimizationRequest,
    MinimizationResult,
    OracleEvaluation,
    ProtectionResult,
    default_token_count,
)
from .oracle import minimize, minimize_context
from .policy import DEFAULT_POLICY, MinimizationPolicy
from .protocols import InvarianceOracle, ProtectionProvider, TokenCounter
from .structural import deduplicate_context, structural_minimize
from .version import CONTRACT_VERSION, __version__

#: The curated public reason-code vocabulary.
REASON_CODES = reasons.ALL_REASON_CODES

__all__ = [
    # versions
    "__version__",
    "CONTRACT_VERSION",
    # context models
    "Context",
    "ContextUnit",
    # request / result
    "MinimizationRequest",
    "MinimizationResult",
    "MinimizationMode",
    "MinimizationPolicy",
    "DEFAULT_POLICY",
    "EquivalenceStatus",
    # protection + oracle
    "ProtectionResult",
    "ProtectionProvider",
    "InvarianceOracle",
    "OracleEvaluation",
    "TokenCounter",
    # entry points
    "structural_minimize",
    "deduplicate_context",
    "minimize_context",
    "minimize",
    # helpers + vocab
    "default_token_count",
    "REASON_CODES",
    # errors
    "ContextMinimizationError",
    "InvalidRequestError",
    "OracleRequiredError",
    "InvalidUnitError",
]

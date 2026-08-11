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
from .token_accounting import (
    ApiCallTokenRecord,
    AttemptStatus,
    DefaultApproximateRequestCounter,
    InMemoryTokenAccountingSink,
    LogicalRequestTokenSummary,
    PreparedApiCall,
    ProviderTokenUsage,
    RequestAttribution,
    RequestComponents,
    RequestTokenCounter,
    RequestTokenEstimate,
    TokenAccountingSink,
    TokenCountBasis,
    TokenUsageSink,
    ExplicitAttemptReference,
    UsageAvailability,
    aggregate_logical_request_usage,
    canonical_tenant_namespace,
    prepare_api_call_measurement,
    reconcile_api_call_measurement,
)
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
    # token accounting (CM-TA1) — three distinct measurements
    "TokenCountBasis",
    "AttemptStatus",
    "UsageAvailability",
    "RequestComponents",
    "RequestTokenEstimate",
    "ProviderTokenUsage",
    "RequestAttribution",
    "canonical_tenant_namespace",
    "ExplicitAttemptReference",
    "ApiCallTokenRecord",
    "LogicalRequestTokenSummary",
    "RequestTokenCounter",
    "TokenAccountingSink",
    "TokenUsageSink",
    "DefaultApproximateRequestCounter",
    "InMemoryTokenAccountingSink",
    "PreparedApiCall",
    "prepare_api_call_measurement",
    "reconcile_api_call_measurement",
    "aggregate_logical_request_usage",
    # errors
    "ContextMinimizationError",
    "InvalidRequestError",
    "OracleRequiredError",
    "InvalidUnitError",
]

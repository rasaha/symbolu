"""Read-only shadow-validation harness for Cloud Scaling Operations.

Environment-independent infrastructure for a *later* real-environment, read-only
Kubernetes shadow validation. This package implements the harness only: it observes
through injected read-only clients, enforces a hard read-only transport barrier, produces
proposed-only :class:`ShadowDecision` objects, validates synthetic authorizations, and
emits clearly-labelled fake/local fixture evidence.

It establishes nothing about a real cluster. Importing it has no side effects: it loads
no kubeconfig, reads no credentials, contacts no endpoint, starts no thread/listener, and
never imports or invokes a live executor. Real Kubernetes shadow validation remains a
separate, resource-gated task.
"""

from __future__ import annotations

from .config import ShadowValidationConfig, ShadowConfigError
from .contracts import (
    SHADOW_SCHEMA_VERSION,
    EVIDENCE_CLASS_FIXTURE,
    AUTHORIZED_FOR_SHADOW_PLAN,
    Destination,
    StaleClassification,
    HpaInteraction,
    TransportDecision,
    LedgerEntry,
    DeploymentObservation,
    HorizontalPodAutoscalerObservation,
    ShadowDecision,
)
from .transport import (
    ReadOnlyTransportBarrier,
    ReadOnlyHTTPClient,
    ReadOnlyViolation,
    RequestMethodLedger,
    ALLOWED_METHODS,
    BLOCKED_METHODS,
)
from .allowlist import TargetAllowlist, TargetRef, AllowlistDecision
from .observer import (
    ShadowObserver,
    RetryPolicy,
    FakeReadOnlyKubernetesClient,
    FakeReadOnlyMetricsClient,
    RealEnvironmentAdapter,
    refuse_auto_discovery,
)
from .authorization_scenarios import (
    evaluate_shadow_authorization,
    run_all_scenarios,
    ShadowAuthorizationResult,
)
from .stale_state import StaleStateEvaluator, StaleResult
from .hpa_analysis import HpaInteractionAnalyzer, HpaInteractionResult
from .session import (
    ShadowSession,
    ShadowSessionResult,
    FixtureTarget,
    build_fixture_observer,
    default_fixture_targets,
)

__all__ = [
    "SHADOW_SCHEMA_VERSION",
    "EVIDENCE_CLASS_FIXTURE",
    "AUTHORIZED_FOR_SHADOW_PLAN",
    "ShadowValidationConfig",
    "ShadowConfigError",
    "Destination",
    "StaleClassification",
    "HpaInteraction",
    "TransportDecision",
    "LedgerEntry",
    "DeploymentObservation",
    "HorizontalPodAutoscalerObservation",
    "ShadowDecision",
    "ReadOnlyTransportBarrier",
    "ReadOnlyHTTPClient",
    "ReadOnlyViolation",
    "RequestMethodLedger",
    "ALLOWED_METHODS",
    "BLOCKED_METHODS",
    "TargetAllowlist",
    "TargetRef",
    "AllowlistDecision",
    "ShadowObserver",
    "RetryPolicy",
    "FakeReadOnlyKubernetesClient",
    "FakeReadOnlyMetricsClient",
    "RealEnvironmentAdapter",
    "refuse_auto_discovery",
    "evaluate_shadow_authorization",
    "run_all_scenarios",
    "ShadowAuthorizationResult",
    "StaleStateEvaluator",
    "StaleResult",
    "HpaInteractionAnalyzer",
    "HpaInteractionResult",
    "ShadowSession",
    "ShadowSessionResult",
    "FixtureTarget",
    "build_fixture_observer",
    "default_fixture_targets",
]

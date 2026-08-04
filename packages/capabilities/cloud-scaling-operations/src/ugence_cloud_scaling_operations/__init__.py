"""Ugence Cloud Scaling Operations — controlled-execution capability.

This package is **execution-capable**: in LIVE mode, with credentials and an explicit
external authorization, it can patch Kubernetes deployment scale and trigger ArgoCD
syncs. It is NOT advisory-only. Dry-run is the default runtime mode — a mode, not an
absence of capability.

Authority model: every infrastructure change requires an immutable
:class:`ExecutionAuthorization` minted by an external authority. A recommendation, an
approval Boolean, or a confidence score is NOT execution authority. All mutation paths
fail closed.

Dependency direction: this package imports ``ugence_cloud_scaling_controller`` (the
advisory recommendation engine); the advisory package never imports this one.

Importing this package has no side effects: no listener, orchestrator loop, thread,
subprocess, network request, credential discovery, or kubeconfig load occurs at import.
"""

from .version import __version__
from .contracts import (
    SCHEMA_VERSION,
    ExecutionMode,
    ExecutionOutcome,
    ExecutionAction,
    ExecutionAuthorization,
    ExecutionRequest,
    ExecutionReceipt,
    ExecutionResult,
    ExecutionDenied,
    ExecutionIntegrityError,
)
from .config import OperationsConfig, TargetPolicy
from .authority import AuthorityVerifier, ReferenceAuthorityVerifier
from .idempotency import IdempotencyStore, InMemoryIdempotencyStore, IdempotencyRecord
from .audit import AuditSink, InMemoryAuditSink, AuditEvent
from .executors import (
    ControlledScalingExecutor,
    ScalingBackend,
    FakeScalingBackend,
    ConcurrencyConflict,
    ReadinessEvaluator,
    OutcomeRecorder,
)
from .k8s_executor import KubernetesScalingExecutor
from .gate_executor import GateExecutor, GateOutcome
from .rollback_coordinator import (
    RollbackCoordinator,
    RollbackPlan,
    RollbackAuthorization,
    RollbackResult,
    RollbackPolicy,
)

__all__ = [
    # contracts
    "ExecutionAuthorization",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionReceipt",
    "ExecutionDenied",
    "ExecutionIntegrityError",
    "ExecutionMode",
    "ExecutionOutcome",
    "ExecutionAction",
    "SCHEMA_VERSION",
    # config
    "OperationsConfig",
    "TargetPolicy",
    # authority
    "AuthorityVerifier",
    "ReferenceAuthorityVerifier",
    # idempotency / audit
    "IdempotencyStore",
    "InMemoryIdempotencyStore",
    "IdempotencyRecord",
    "AuditSink",
    "InMemoryAuditSink",
    "AuditEvent",
    # executors
    "ControlledScalingExecutor",
    "KubernetesScalingExecutor",
    "GateExecutor",
    "GateOutcome",
    "ScalingBackend",
    "FakeScalingBackend",
    "ConcurrencyConflict",
    "ReadinessEvaluator",
    "OutcomeRecorder",
    # rollback
    "RollbackCoordinator",
    "RollbackPlan",
    "RollbackAuthorization",
    "RollbackResult",
    "RollbackPolicy",
    "__version__",
]

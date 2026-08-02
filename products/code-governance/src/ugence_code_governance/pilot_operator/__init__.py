"""Deployable, security-bounded live shadow-pilot operator (MVP 1E).

An operator can configure, start, pause, resume, inspect, and stop a tightly
bounded read-only Code Governance pilot against a narrowly allowlisted GitHub
environment. It has no GitHub write path, isolates credentials, fails closed, and
produces reconstructable, verifiable audit + pilot reports. Execution stays
``DISABLED``; a successful pilot never enables enforcement.
"""
from __future__ import annotations

from .api import PilotOperator, open_pilot_operator
from .config import (
    CONFIG_SCHEMA_VERSION,
    MAX_CONCURRENCY,
    PilotDeploymentConfig,
    PilotStopThresholds,
    fingerprint_pilot_config,
    load_pilot_config,
    load_pilot_config_json,
    validate_pilot_config,
)
from .errors import (
    CredentialBoundaryError,
    KillSwitchActiveError,
    PilotConfigError,
    PilotLifecycleError,
    PilotOperatorError,
    PilotSecurityError,
    PilotStoppedError,
    ReviewQueueError,
)
from .events import PilotKillSwitchState, PilotSecurityEvent, SecurityEventKind
from .health import (
    PilotHealth,
    PilotHealthStatus,
    PilotReadiness,
    compute_health,
    compute_readiness,
)
from .lifecycle import (
    PilotLifecycleEvent,
    PilotLifecycleStatus,
    PilotRunRecord,
    can_transition,
)
from .metrics import OperatorMetrics
from .preflight import (
    PermissionVerification,
    PilotPreflightResult,
    PreflightOutcome,
    run_pilot_preflight,
)
from .recovery import PilotRecoveryResult, PilotRecoveryStatus, recover_pilot
from .review_queue import (
    ReviewerQueueItem,
    ReviewerQueueStatus,
    ReviewPriority,
    build_queue_item,
)
from .scheduler import (
    EvaluationCandidate,
    StopConditionHit,
    StopConditionKind,
    evaluate_stop_conditions,
    select_candidates,
)
from .security import (
    CredentialReference,
    ResolverKind,
    SecurityFinding,
    SecurityScanResult,
    scan_for_credential,
    scan_paths,
    scan_source,
)

__all__ = [
    # operator
    "PilotOperator", "open_pilot_operator",
    # config
    "PilotDeploymentConfig", "PilotStopThresholds", "validate_pilot_config",
    "fingerprint_pilot_config", "load_pilot_config", "load_pilot_config_json",
    "CONFIG_SCHEMA_VERSION", "MAX_CONCURRENCY",
    # lifecycle
    "PilotLifecycleStatus", "PilotLifecycleEvent", "PilotRunRecord", "can_transition",
    # preflight
    "PilotPreflightResult", "PreflightOutcome", "PermissionVerification", "run_pilot_preflight",
    # health
    "PilotHealthStatus", "PilotHealth", "PilotReadiness", "compute_health", "compute_readiness",
    # recovery
    "PilotRecoveryStatus", "PilotRecoveryResult", "recover_pilot",
    # scheduler + stop conditions
    "EvaluationCandidate", "select_candidates", "StopConditionKind", "StopConditionHit",
    "evaluate_stop_conditions",
    # review queue
    "ReviewerQueueItem", "ReviewerQueueStatus", "ReviewPriority", "build_queue_item",
    # metrics
    "OperatorMetrics",
    # security
    "CredentialReference", "ResolverKind", "scan_for_credential", "scan_source", "scan_paths",
    "SecurityFinding", "SecurityScanResult",
    "SecurityEventKind", "PilotSecurityEvent", "PilotKillSwitchState",
    # errors
    "PilotOperatorError", "PilotConfigError", "PilotLifecycleError", "PilotSecurityError",
    "CredentialBoundaryError", "KillSwitchActiveError", "PilotStoppedError", "ReviewQueueError",
]

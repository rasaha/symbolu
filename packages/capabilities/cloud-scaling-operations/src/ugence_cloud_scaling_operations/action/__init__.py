"""Action layer — actuators, policy, rollback, readiness, outcome tracking.

Modules:
  - K8sActuator: Reference scaling actuator over an injected client; dry-run by
    default, refused by the recommendation engine in any mutating mode
  - GateActuator: Dry-run recorder of deployment-gate decisions (no ArgoCD access)
  - PolicyEngine: Customer-configurable safety limits (max replicas, blackout windows)
  - RollbackMonitor: Auto-reverts scaling if metrics degrade post-action
  - ReadinessChecker: Exposes system readiness for ArgoCD pre-hooks
  - OutcomeTracker: Post-action metric evaluation for learning feedback
"""

from ugence_cloud_scaling_operations.action.k8s_actuator import (
    ActuatorConfig,
    ActuatorMode,
    ExecutionResult,
    K8sActuator,
)
from ugence_cloud_scaling_operations.action.gate_actuator import (
    GateAction,
    GateConfig,
    GateMode,
    GateResult,
    GateActuator,
)
from ugence_cloud_scaling_operations.action.rollback import (
    MutatingRollbackRefused,
    RollbackConfig,
    RollbackMonitor,
    RollbackVerdict,
    RollbackWatch,
)
from ugence_cloud_scaling_operations.action.policy import (
    BlackoutWindow,
    DeploymentPolicy,
    PolicyCheckResult,
    PolicyConfig,
    PolicyEngine,
)
from ugence_cloud_scaling_operations.action.readiness import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)
from ugence_cloud_scaling_operations.action.outcome import (
    OutcomeConfig,
    OutcomeRecord,
    OutcomeTracker,
    OutcomeVerdict,
)
from ugence_cloud_scaling_operations.action.feedback import (
    FeedbackAdjustment,
    FeedbackConfig,
    FeedbackCycleResult,
    FeedbackLoop,
    FeedbackSignal,
)

__all__ = [
    # K8s Actuator
    "ActuatorConfig",
    "ActuatorMode",
    "ExecutionResult",
    "K8sActuator",
    # Gate Actuator
    "GateAction",
    "GateConfig",
    "GateMode",
    "GateResult",
    "GateActuator",
    # Rollback
    "MutatingRollbackRefused",
    "RollbackConfig",
    "RollbackMonitor",
    "RollbackVerdict",
    "RollbackWatch",
    # Policy
    "BlackoutWindow",
    "DeploymentPolicy",
    "PolicyCheckResult",
    "PolicyConfig",
    "PolicyEngine",
    # Readiness
    "ReadinessChecker",
    "ReadinessConfig",
    "ReadinessResult",
    "ReadinessStatus",
    # Outcome
    "OutcomeConfig",
    "OutcomeRecord",
    "OutcomeTracker",
    "OutcomeVerdict",
    # Feedback
    "FeedbackAdjustment",
    "FeedbackConfig",
    "FeedbackCycleResult",
    "FeedbackLoop",
    "FeedbackSignal",
]

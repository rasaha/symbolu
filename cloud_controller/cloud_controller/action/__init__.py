"""Action layer — actuators, policy, rollback, readiness, outcome tracking.

Modules:
  - K8sActuator: Scales deployments via K8s API (replica patch or HPA metric)
  - GateActuator: Controls deployment gates via ArgoCD or admission webhooks
  - PolicyEngine: Customer-configurable safety limits (max replicas, blackout windows)
  - RollbackMonitor: Auto-reverts scaling if metrics degrade post-action
  - ReadinessChecker: Exposes system readiness for ArgoCD pre-hooks
  - OutcomeTracker: Post-action metric evaluation for learning feedback
"""

from cloud_controller.action.k8s_actuator import (
    ActuatorConfig,
    ActuatorMode,
    ExecutionResult,
    K8sActuator,
)
from cloud_controller.action.gate_actuator import (
    GateAction,
    GateConfig,
    GateMode,
    GateResult,
    GateActuator,
)
from cloud_controller.action.rollback import (
    RollbackConfig,
    RollbackMonitor,
    RollbackVerdict,
    RollbackWatch,
)
from cloud_controller.action.policy import (
    BlackoutWindow,
    DeploymentPolicy,
    PolicyCheckResult,
    PolicyConfig,
    PolicyEngine,
)
from cloud_controller.action.readiness import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)
from cloud_controller.action.outcome import (
    OutcomeConfig,
    OutcomeRecord,
    OutcomeTracker,
    OutcomeVerdict,
)
from cloud_controller.action.feedback import (
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

"""
Cloud Governance — Governance facades for cloud_controller safety logic.

Re-exports governance-relevant modules from symbolu_core.cloud_controller:

  - PolicyEngine: Customer-configurable safety limits (max replicas,
    blackout windows, rate limits). Runs BEFORE actuator; blocks actions.
  - SafetyBounds: Hard limits on scaling (+50%/-25%), cooldown enforcement,
    minimum replica floors. Always enforced, even after human approval.
  - ApprovalManager: Human-in-the-loop recommendation lifecycle
    (PENDING → APPROVED/DISMISSED/EXPIRED).
  - ReadinessChecker: Gates deployments based on plasticity threshold.
    Blocks ArgoCD syncs when system unstable.
  - RollbackMonitor: Auto-reverts scaling if metrics degrade post-action.
  - PlasticityGate: Permission-to-act gate (sigmoid gate over stability
    and misalignment signals).
"""

from symbolu_core.cloud_controller.action.policy import (
    PolicyEngine,
    DeploymentPolicy,
    BlackoutWindow,
    PolicyCheckResult,
)
from symbolu_core.cloud_controller.recommend.safety import (
    SafetyBounds,
    SafetyConfig,
    SafetyResult,
)
from symbolu_core.cloud_controller.recommend.approval import (
    ApprovalManager,
    ApprovalState,
    Recommendation,
)
from symbolu_core.cloud_controller.action.readiness import (
    ReadinessChecker,
    ReadinessStatus,
    ReadinessResult,
)
from symbolu_core.cloud_controller.action.rollback import (
    RollbackMonitor,
    RollbackVerdict,
)
from symbolu_core.cloud_controller.core.plasticity_gate import (
    PlasticityGate,
    PlasticityResult,
)

__all__ = [
    # Policy
    "PolicyEngine",
    "DeploymentPolicy",
    "BlackoutWindow",
    "PolicyCheckResult",
    # Safety bounds
    "SafetyBounds",
    "SafetyConfig",
    "SafetyResult",
    # Approval
    "ApprovalManager",
    "ApprovalState",
    "Recommendation",
    # Readiness
    "ReadinessChecker",
    "ReadinessStatus",
    "ReadinessResult",
    # Rollback
    "RollbackMonitor",
    "RollbackVerdict",
    # Plasticity
    "PlasticityGate",
    "PlasticityResult",
]

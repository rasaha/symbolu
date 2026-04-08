"""
Agentic Governance Patterns — Standalone governance primitives for AI agents.

Six design patterns extracted from infrastructure governance and rewritten
for AI agent governance with no external dependencies:

    PolicyEngine      — Configurable allow/deny enforcement (O1, O6)
    SafetyBounds      — Hard non-negotiable action limits (O3, O4)
    ApprovalManager   — Human-in-the-loop decision lifecycle (O8, O9)
    PlasticityGate    — Sigmoid permission-to-act gate (O5, O10)
    ReadinessChecker  — Multi-criterion readiness gate (O9, O7)
    RollbackMonitor   — Post-action degradation rollback (O12, O11)

These compose a multi-layer governance pipeline:

    PolicyEngine → SafetyBounds → PlasticityGate → ReadinessChecker
                                                        ↓
                                                  ApprovalManager
                                                        ↓
                                                  [ACTION EXECUTES]
                                                        ↓
                                                  RollbackMonitor
"""

from agentic.safety.governance_patterns.policy_engine import (
    PolicyEngine,
    PolicyConfig,
    AgentPolicy,
    BlackoutWindow,
    PolicyCheckResult,
)
from agentic.safety.governance_patterns.safety_bounds import (
    SafetyBounds,
    SafetyConfig,
    SafetyResult,
)
from agentic.safety.governance_patterns.approval_manager import (
    ApprovalManager,
    ApprovalState,
    GovernanceDecision,
)
from agentic.safety.governance_patterns.plasticity_gate import (
    PlasticityGate,
    PlasticityResult,
)
from agentic.safety.governance_patterns.readiness_checker import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)
from agentic.safety.governance_patterns.rollback_monitor import (
    RollbackMonitor,
    RollbackConfig,
    RollbackWatch,
    RollbackVerdict,
)

__all__ = [
    # Policy
    "PolicyEngine",
    "PolicyConfig",
    "AgentPolicy",
    "BlackoutWindow",
    "PolicyCheckResult",
    # Safety
    "SafetyBounds",
    "SafetyConfig",
    "SafetyResult",
    # Approval
    "ApprovalManager",
    "ApprovalState",
    "GovernanceDecision",
    # Plasticity
    "PlasticityGate",
    "PlasticityResult",
    # Readiness
    "ReadinessChecker",
    "ReadinessConfig",
    "ReadinessResult",
    "ReadinessStatus",
    # Rollback
    "RollbackMonitor",
    "RollbackConfig",
    "RollbackWatch",
    "RollbackVerdict",
]

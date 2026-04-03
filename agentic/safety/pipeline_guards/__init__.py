"""
Pipeline Guards — Governance facades for mechanical pipeline safety phases.

Re-exports governance-critical pipeline phases from symbolu_core.mechanical:

Guards (active enforcement):
  - PlannerGate: Action filtering with ALLOW/FORBID per observation mode
  - P15RegressionGuard: Authority preservation (intent/regime/posture immutable after P15)
  - P16RegressionGuard: Hash-based mutation detection (PO1-P15 integrity)
  - P55 authorize_execution: Deny-by-default execution boundary

Compliance:
  - RendererComplianceChecker: Validates renderers against P13 safety envelope
  - RendererInputContract: Non-negotiable pipeline-renderer contract
"""

# PlannerGate — action filtering
from symbolu_core.mechanical.pipeline.governance.planner_gate import (
    PlannerGate,
    ActionClass,
    GatedPlanResult,
    GatedPlanStep,
)

# P15 — authority regression guard
from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_regression_guard import (
    P15RegressionGuard,
)
from symbolu_core.mechanical.pipeline.p15_authority_guard.p15_regression_schema import (
    P15AuthoritySnapshot,
    P15RegressionViolation,
)

# P16 — contract regression guard
from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_contract_schema import (
    ViolationType as P16ViolationType,
    HashSnapshot,
    ContractViolation,
)
from symbolu_core.mechanical.pipeline.p16_regression_guard.p16_regression_guard import (
    P16RegressionGuard,
)

# P55 — execution authorization boundary
from symbolu_core.mechanical.pipeline.p55_execution_boundary.p55_schema import (
    ExecutionAuthorizationDecision,
    ExecutionProposalEnvelope,
)
from symbolu_core.mechanical.pipeline.p55_execution_boundary.p55_authorizer import (
    authorize_execution,
    ALLOWED_ACTION_TYPES,
)

# Renderer compliance
from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_contract import (
    RendererInputContract,
    ComplianceResult,
    ComplianceViolation,
)
from symbolu_core.mechanical.pipeline.renderer_compliance.renderer_compliance_checker import (
    RendererComplianceChecker,
)

__all__ = [
    # PlannerGate
    "PlannerGate",
    "ActionClass",
    "GatedPlanResult",
    "GatedPlanStep",
    # P15
    "P15RegressionGuard",
    "P15AuthoritySnapshot",
    "P15RegressionViolation",
    # P16
    "P16RegressionGuard",
    "P16ViolationType",
    "HashSnapshot",
    "ContractViolation",
    # P55
    "ExecutionAuthorizationDecision",
    "ExecutionProposalEnvelope",
    "ALLOWED_ACTION_TYPES",
    "authorize_execution",
    # Renderer compliance
    "RendererComplianceChecker",
    "RendererInputContract",
    "ComplianceResult",
    "ComplianceViolation",
]

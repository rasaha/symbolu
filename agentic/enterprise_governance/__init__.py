"""
Enterprise Governance Evidence Model — the NEUTRAL capability architecture
extracted from the two-stage ontology research.

This package deliberately carries NO ontology terminology (no twelve layers, no
sequence). It is the candidate product architecture: typed governance evidence +
provenance/authority + a set of reusable invariants, evaluated in read-only
SHADOW mode over source-schema-shaped records.

Honesty boundary (important): this is a shadow-mode pilot over REALISTIC SOURCE
SCHEMAS with SYNTHETIC fixtures and a strong-controls baseline. It is NOT real
operational validation — it makes no claim of real-world efficacy, and nothing
here connects to a production system. Real Phase-3 validation requires real
(or anonymized-from-real) artifacts and domain owners.

Self-contained and read-only: imports no production ActionGate / healthcare /
trading / JEPA / sovereign code, and does not import the ontology research
package either (the concepts are re-expressed neutrally).
"""

from agentic.enterprise_governance.model import (
    AuthorityRole,
    CapabilityGroup,
    Disposition,
    EvidenceStatus,
    GovernanceDecision,
    GovernanceEvidence,
    GovernanceExecution,
    GovernanceFinding,
    PromotionLevel,
    Verification,
    WorkflowDependency,
    WorkflowEvidence,
)
from agentic.enterprise_governance.invariants import (
    INVARIANTS, run_invariants,
)
from agentic.enterprise_governance.baseline import StrongControlsBaseline
from agentic.enterprise_governance.shadow import ShadowEvaluator, shadow_report
from agentic.enterprise_governance.workflows import all_workflows

__all__ = [
    "AuthorityRole", "CapabilityGroup", "Disposition", "EvidenceStatus",
    "GovernanceDecision", "GovernanceEvidence", "GovernanceExecution",
    "GovernanceFinding", "PromotionLevel", "Verification", "WorkflowDependency",
    "WorkflowEvidence", "INVARIANTS", "run_invariants", "StrongControlsBaseline",
    "ShadowEvaluator", "shadow_report", "all_workflows",
]

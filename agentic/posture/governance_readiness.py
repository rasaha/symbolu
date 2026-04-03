"""
Governance Readiness — Facade for P51 readiness assessment.

Re-exports P51 governance readiness from symbolu_core.mechanical.pipeline.
P51 evaluates whether the pipeline is structurally ready for governance
(phase completeness, determinism, authority integrity, explainability).
"""

from symbolu_core.mechanical.pipeline.p51_governance_readiness.p51_schema import (
    GovernanceReadinessEnvelope,
    ReadinessLevel,
)
from symbolu_core.mechanical.pipeline.p51_governance_readiness.p51_analyzer import (
    compute_governance_readiness,
)

__all__ = [
    "GovernanceReadinessEnvelope",
    "ReadinessLevel",
    "compute_governance_readiness",
]

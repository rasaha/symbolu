"""
Governance Adapter — Facade for P52 governance request assembly.

Re-exports P52 governance adapter from symbolu_core.mechanical.pipeline.
P52 assembles GovernanceRequest from pipeline state for the external
governance engine (POST /authorize).
"""

from symbolu_core.mechanical.pipeline.p52_governance_adapter.p52_schema import (
    GovernanceRequest,
    GovernanceResponse,
)
from symbolu_core.mechanical.pipeline.p52_governance_adapter.p52_assembler import (
    assemble_governance_request,
)

__all__ = [
    "GovernanceRequest",
    "GovernanceResponse",
    "assemble_governance_request",
]

"""
Symbol-U Pipeline Governance Module

Enforces Phase −1 grounding constraints on downstream pipeline stages.

Components:
- PlannerGate: Filters/blocks planner actions based on grounding constraints

Authority Model:
- Authority flows downward from Phase −1
- PlannerGate enforces constraints established by grounding analysis
- Violations are logged but cannot override grounding decisions
"""

from .planner_gate import (
    PlannerGate,
    GatedPlanResult,
    ActionClass,
)

__all__ = [
    "PlannerGate",
    "GatedPlanResult",
    "ActionClass",
]

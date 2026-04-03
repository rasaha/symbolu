"""
Symbol-U Pipeline Governance Module

Enforces PO1 (Observer–Observed Grounding) constraints on downstream pipeline stages.

PO phases are pre-acoustic governance layers and precede symbolic processing (P1+).

Components:
- PlannerGate: Filters/blocks planner actions based on grounding constraints

Authority Model:
- Authority flows downward from PO1
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

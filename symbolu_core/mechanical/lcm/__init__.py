"""
LCM (Low-Context Mapper) Module v1.0

A deterministic, LLM-free sub-engine that produces minimal structural summaries
for simple task-like queries where deep symbolic fusion is unnecessary.

LCM runs only when:
    - TTOR sets `use_lcm=True` in the RoutingPlan
    - Usually in LOWER tier, task domains, or low/medium entropy

Typical use cases:
    - "Sort this list"
    - "What is 2+2?"
    - "Convert this to JSON"
    - "Find the error in this code snippet"
    - "Where is the file located?"

Usage:
    from symbolu_core.mechanical.lcm import LCMEngine, LCMInput, LowContextMap

    engine = LCMEngine()
    lcm_input = LCMInput(
        text="Sort this list alphabetically",
        domain="task",
        aspect_probs={"Execution": 0.8, "Form": 0.2},
        anchor_scores={"Needs": 0.7, "Exchange": 0.3},
        H_D=0.5,
        H_G=0.3,
        H_K=0.4,
        tier="lower",
        flow_mode="outer_only",
    )
    lcm_map = engine.build_map(lcm_input)
"""

from .models import LCMInput, LowContextMap
from .lcm_engine import LCMEngine, get_lcm_engine

__all__ = [
    "LCMEngine",
    "LCMInput",
    "LowContextMap",
    "get_lcm_engine",
]

__version__ = "1.0.0"

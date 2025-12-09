"""
HRM (High-Resolution Mapper) Module v1.0

A deterministic, LLM-free sub-engine that produces high-resolution cognitive maps
for deeper but still deterministic reasoning by Fusion/DHA engines.

HRM runs only when:
    - TTOR sets `use_hrm=True` in the RoutingPlan
    - Usually in UPPER or HYBRID tier, reflective domains, or high entropy

Usage:
    from symbolu.mechanical.hrm import HRMEngine, HRMInput, HighResolutionMap

    engine = HRMEngine()
    hrm_input = HRMInput(
        aspect_probs={"Execution": 0.3, "Purpose": 0.7, ...},
        anchor_scores={"Needs": 0.4, "Meaning": 0.8, ...},
        H_D=1.5,
        H_G=0.8,
        H_K=1.2,
        domain="therapy",
        tier="upper",
        flow_mode="inner_priority",
    )
    hrm_map = engine.build_map(hrm_input)
"""

from .models import HRMInput, HighResolutionMap
from .hrm_engine import HRMEngine

__all__ = [
    "HRMEngine",
    "HRMInput",
    "HighResolutionMap",
]

__version__ = "1.0.0"

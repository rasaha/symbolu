"""
Renderer Submodule
===================

Contains:
- FusionRenderer: Combines rule-based and LLM rendering
- RulesRenderer: Deterministic rule-based rendering
- LLMRenderer: LLM-enhanced rendering

All renderers follow "stylist not thinker" principle.
"""

from symbolu.mechanical.renderer.fusion_renderer import FusionRenderer
from symbolu.mechanical.renderer.rules_renderer import RulesRenderer
from symbolu.mechanical.renderer.llm_renderer import LLMRenderer

__all__ = [
    "FusionRenderer",
    "RulesRenderer",
    "LLMRenderer",
]

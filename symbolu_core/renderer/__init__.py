"""
Renderer Module
================

Test package for SOULPI Renderer components.

Re-exports from mechanical.renderer for convenient testing access.
"""

# Re-export from mechanical.renderer
from symbolu_core.mechanical.renderer import (
    # Core classes
    FusionRenderer,
    FusionOutput,
    RenderedOutput,
    SymbolicLayer,
    PracticalLayer,
    MirrorTruthLayer,

    # Enums
    RenderMode,
    Domain,

    # Constants
    REGULATED_DOMAINS,
    MODE_WEIGHTS,

    # Functions
    render_fusion_output
)

# Import additional renderers
from symbolu_core.mechanical.renderer.rules_renderer import RulesRenderer
from symbolu_core.mechanical.renderer.llm_renderer import LLMRenderer

__all__ = [
    # Core classes
    "FusionRenderer",
    "FusionOutput",
    "RenderedOutput",
    "SymbolicLayer",
    "PracticalLayer",
    "MirrorTruthLayer",

    # Enums
    "RenderMode",
    "Domain",

    # Constants
    "REGULATED_DOMAINS",
    "MODE_WEIGHTS",

    # Functions
    "render_fusion_output",

    # Additional renderers
    "RulesRenderer",
    "LLMRenderer"
]

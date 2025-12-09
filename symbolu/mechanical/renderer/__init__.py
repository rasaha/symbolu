"""
SOULPI Fusion Renderer v3.0
============================

The deterministic bridge between FusionEngine cognition and presentation layers.

Public API:
-----------
Classes:
    - FusionRenderer: Main rendering class
    - FusionOutput: Input data structure
    - RenderedOutput: Output data structure
    - SymbolicLayer: The "WHY" layer
    - PracticalLayer: The "WHAT/HOW" layer
    - MirrorTruthLayer: Reflective synthesis layer

Enums:
    - RenderMode: Operating modes
    - Domain: Application domains

Functions:
    - render_fusion_output: Convenience rendering function

Example:
--------
    from symbolu.mechanical.renderer import (
        FusionRenderer,
        FusionOutput,
        RenderMode,
        Domain
    )
    
    # Create renderer
    renderer = FusionRenderer(
        mode=RenderMode.STANDARD,
        domain=Domain.GENERAL
    )
    
    # Render output
    output = renderer.render(fusion_output)
    
    # Access layers
    print(output.symbolic_layer.theme)
    print(output.practical_layer.key_facts)
    print(output.mirror_truth_layer.alignment_score)

Version: 3.0
Author: Rakesh Mohan (Symbol-U AGI)
"""

from .fusion_renderer import (
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
    
    # Convenience function
    render_fusion_output
)

__version__ = "3.0"
__author__ = "Rakesh Mohan"
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
]

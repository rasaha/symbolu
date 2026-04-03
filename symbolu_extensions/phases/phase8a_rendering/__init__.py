"""
Phase-8A Rendering Layer

One-way projection from Phase-7 outputs to human-perceivable artifacts.
Deterministic, non-semantic, non-selective rendering.

Contract: docs/contracts/PHASE_8A_RENDERING_CONTRACT.md
"""

from symbolu_extensions.phases.phase8a_rendering.types import (
    RenderModality,
    RenderErrorType,
    RendererConfig,
    RenderInput,
    RenderError,
    ValidationResult,
    PhoneticArtifact,
    AcousticArtifact,
    VisualElement,
    VisualArtifact,
    SymbolicArtifact,
    NumericArtifact,
    RenderMetadata,
    RenderOutput,
    compute_input_hash,
)

from symbolu_extensions.phases.phase8a_rendering.renderer import Renderer
from symbolu_extensions.phases.phase8a_rendering.symbolic_renderer import SymbolicRenderer

__all__ = [
    # Enums
    "RenderModality",
    "RenderErrorType",
    # Config and Input
    "RendererConfig",
    "RenderInput",
    # Results
    "ValidationResult",
    "RenderError",
    "RenderMetadata",
    "RenderOutput",
    # Artifacts
    "PhoneticArtifact",
    "AcousticArtifact",
    "VisualElement",
    "VisualArtifact",
    "SymbolicArtifact",
    "NumericArtifact",
    # Renderer
    "Renderer",
    "SymbolicRenderer",
    # Utilities
    "compute_input_hash",
]

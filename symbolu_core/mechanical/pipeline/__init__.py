"""
Symbol-U Pipeline Package (v3.0)

Linear pipeline orchestrator with Option C router hooks for the Symbol-U AGI system.

This package provides:
- SymbolUPipeline: Main orchestrator for the v3.0 linear pipeline
- UserRequest: Input model for pipeline requests
- RenderedOutput: Output model with final text and metadata
- PipelineRouter: Router abstraction for future adaptive flows

Pipeline Sequence:
    Persona -> MLCR -> Fusion -> DHA -> Renderer

Quick Start:
    from mechanical.pipeline import SymbolUPipeline, UserRequest

    pipeline = SymbolUPipeline()
    request = UserRequest(text="Why do I feel stuck?")
    result = pipeline.run(request)
    print(result.raw_text)

Version: 3.0
"""

# Models - Data structures for pipeline stages
from .models import (
    DhaDecision,
    FusionResult,
    MlcrResult,
    PersonaContext,
    PipelineContext,
    RenderedOutput,
    UserRequest,
)

# Router - Execution path decision engine
from .routing import (
    PipelineRouter,
    get_default_router,
)

# Orchestrator - Main pipeline engine
from .orchestrator import (
    SymbolUPipeline,
    run_pipeline,
)

# Validators - Stage validation utilities
from .validators import (
    ensure_dha,
    ensure_fusion,
    ensure_mlcr,
    ensure_persona,
    ensure_rendered,
    validate_request,
    validate_stage_sequence,
)


__version__ = "3.0.0"

__all__ = [
    # Core orchestrator
    "SymbolUPipeline",
    "run_pipeline",
    # Models
    "UserRequest",
    "RenderedOutput",
    "PipelineContext",
    "PersonaContext",
    "MlcrResult",
    "FusionResult",
    "DhaDecision",
    # Router
    "PipelineRouter",
    "get_default_router",
    # Validators
    "validate_request",
    "ensure_persona",
    "ensure_mlcr",
    "ensure_fusion",
    "ensure_dha",
    "ensure_rendered",
    "validate_stage_sequence",
]

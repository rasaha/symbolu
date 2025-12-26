#!/usr/bin/env python3
"""
Symbol-U Image Generation Module
=================================

Coherent image generation using Symbol-U's 12-layer ontological model
integrated with FLUX diffusion models.

Key Components:
- SymbolUFluxPipeline: Main generation pipeline
- CoherenceMonitor: Real-time coherence tracking
- BCVFImageEngine: Bidirectional verification
- USEImageEngine: Phase synchronization
- SCCImageEngine: Semantic coherence

Quick Start:
------------
    from symbolu.image_gen import generate

    # Quick generation
    result = generate("A beautiful sunset over mountains")

    if result.success:
        result.image.save("output.png")
        print(f"Confidence: {result.confidence}")

Advanced Usage:
---------------
    from symbolu.image_gen import (
        SymbolUFluxPipeline,
        ImageGenConfig,
        GenerationMode,
    )

    # Create pipeline with custom config
    config = ImageGenConfig(
        mode=GenerationMode.QUALITY,
        num_inference_steps=50,
    )

    pipeline = SymbolUFluxPipeline.from_pretrained(config=config)

    # Generate with full coherence monitoring
    result = pipeline.generate(
        prompt="A majestic eagle soaring above clouds",
        guidance_scale=4.0,
    )

    # Analyze coherence
    print(f"Global coherence: {result.metrics.global_coherence:.2f}")
    print(f"Prompt alignment: {result.metrics.prompt_alignment:.2f}")
    print(f"Quality score: {result.metrics.quality_score:.2f}")
"""

# Version
__version__ = "0.1.0"

# =============================================================================
# CONFIGURATION
# =============================================================================

from symbolu.image_gen.config import (
    # Enums
    FluxVariant,
    GenerationMode,
    OutputFormat,
    # Config classes
    FluxConfig,
    CoherenceConfig,
    BCVFImageConfig,
    USEImageConfig,
    SCCImageConfig,
    LayerMappingConfig,
    CoherenceMatrixConfig,
    ImageGenConfig,
    # Result classes
    LayerCoherenceResult,
    ImageGenMetrics,
    ImageGenResult,
)

# =============================================================================
# LAYER MAPPING
# =============================================================================

from symbolu.image_gen.layer_mapper import (
    OntologicalLayer,
    LayerMapper,
    LayerBlockMapping,
    LayerState,
    GenerationLayerStates,
    LAYER_NAMES,
    LAYER_BHAVA,
    LAYER_CONFIG,
)

# =============================================================================
# ENGINES
# =============================================================================

# BCVF - Bidirectional Consistency Verification
from symbolu.image_gen.bcvf_image import (
    BCVFImageEngine,
    BCVFImageScore,
    ForwardImageScorer,
    BackwardImageScorer,
    ConsistencyLagrangianImage,
    create_bcvf_engine,
)

# USE - Universal Synchronization Engine
from symbolu.image_gen.use_image import (
    USEImageEngine,
    PhaseExtractor,
    PhaseCorrelation,
    PhaseSynchronizer,
    PhaseCorrelationResult,
    PhaseSyncResult,
    create_use_engine,
)

# SCC - Semantic Coherence Controller
from symbolu.image_gen.scc_image import (
    SCCImageEngine,
    LayerCoherenceComputer,
    GlobalCoherenceComputer,
    CoherenceRestorer,
    GlobalCoherenceResult,
    CoherenceIssue,
    create_scc_engine,
)

# =============================================================================
# MONITORING
# =============================================================================

from symbolu.image_gen.coherence_monitor import (
    CoherenceMonitor,
    TimestepMetrics,
    CoherenceHistory,
    GenerationDecision,
    CorrectionAction,
    create_monitor,
    quick_check,
)

# =============================================================================
# FLUX INTEGRATION
# =============================================================================

from symbolu.image_gen.flux_integration import (
    SymbolUFluxWrapper,
    FluxLayerCapture,
    FluxGenerationState,
    FluxGenerationResult,
    BlockHook,
    create_flux_wrapper,
    get_layer_for_timestep,
)

# =============================================================================
# PIPELINE
# =============================================================================

from symbolu.image_gen.pipeline import (
    SymbolUFluxPipeline,
    PipelineResult,
    generate,
    create_pipeline,
)

# =============================================================================
# PUBLIC API
# =============================================================================

__all__ = [
    # Version
    "__version__",

    # === Configuration ===
    # Enums
    "FluxVariant",
    "GenerationMode",
    "OutputFormat",
    # Config classes
    "FluxConfig",
    "CoherenceConfig",
    "BCVFImageConfig",
    "USEImageConfig",
    "SCCImageConfig",
    "LayerMappingConfig",
    "CoherenceMatrixConfig",
    "ImageGenConfig",
    # Result classes
    "LayerCoherenceResult",
    "ImageGenMetrics",
    "ImageGenResult",

    # === Layer Mapping ===
    "OntologicalLayer",
    "LayerMapper",
    "LayerBlockMapping",
    "LayerState",
    "GenerationLayerStates",
    "LAYER_NAMES",
    "LAYER_BHAVA",
    "LAYER_CONFIG",

    # === BCVF Engine ===
    "BCVFImageEngine",
    "BCVFImageScore",
    "ForwardImageScorer",
    "BackwardImageScorer",
    "ConsistencyLagrangianImage",
    "create_bcvf_engine",

    # === USE Engine ===
    "USEImageEngine",
    "PhaseExtractor",
    "PhaseCorrelation",
    "PhaseSynchronizer",
    "PhaseCorrelationResult",
    "PhaseSyncResult",
    "create_use_engine",

    # === SCC Engine ===
    "SCCImageEngine",
    "LayerCoherenceComputer",
    "GlobalCoherenceComputer",
    "CoherenceRestorer",
    "GlobalCoherenceResult",
    "CoherenceIssue",
    "create_scc_engine",

    # === Monitoring ===
    "CoherenceMonitor",
    "TimestepMetrics",
    "CoherenceHistory",
    "GenerationDecision",
    "CorrectionAction",
    "create_monitor",
    "quick_check",

    # === FLUX Integration ===
    "SymbolUFluxWrapper",
    "FluxLayerCapture",
    "FluxGenerationState",
    "FluxGenerationResult",
    "BlockHook",
    "create_flux_wrapper",
    "get_layer_for_timestep",

    # === Pipeline (Main API) ===
    "SymbolUFluxPipeline",
    "PipelineResult",
    "generate",
    "create_pipeline",
]


# =============================================================================
# CONVENIENCE INITIALIZATION
# =============================================================================

def get_version() -> str:
    """Get module version."""
    return __version__


def check_dependencies() -> dict:
    """Check availability of optional dependencies."""
    deps = {
        "torch": False,
        "diffusers": False,
        "transformers": False,
        "PIL": False,
    }

    try:
        import torch
        deps["torch"] = True
    except ImportError:
        pass

    try:
        import diffusers
        deps["diffusers"] = True
    except ImportError:
        pass

    try:
        import transformers
        deps["transformers"] = True
    except ImportError:
        pass

    try:
        from PIL import Image
        deps["PIL"] = True
    except ImportError:
        pass

    return deps


def quick_start_info() -> str:
    """Print quick start information."""
    deps = check_dependencies()

    info = f"""
Symbol-U Image Generation v{__version__}
========================================

Dependencies:
  - torch: {'OK' if deps['torch'] else 'MISSING'}
  - diffusers: {'OK' if deps['diffusers'] else 'MISSING'}
  - transformers: {'OK' if deps['transformers'] else 'MISSING'}
  - PIL: {'OK' if deps['PIL'] else 'MISSING'}

Quick Start:
  from symbolu.image_gen import generate
  result = generate("A beautiful sunset")
  result.image.save("output.png")

For more information, see the module docstring or documentation.
"""
    return info

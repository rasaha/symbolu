"""
Phase-Quad Video Generation Module.

This module provides video generation capabilities using the Phase-Quad
architecture extended with temporal phase integration.

Key components:
    - PhaseIntegrator3D: Tri-axial phase accumulation (row, col, time)
    - VideoMeta: Metadata for video patches
    - PretrainedVideoVAE: Video VAE wrapper (CogVideoX)
    - PhaseQuadVideoConfig: Configuration for video generation
    - PhaseQuadVideoGenerator: Full video generation model
    - PhaseQuadVideoPipeline: Inference pipeline

Example:
    >>> from symbolu_extensions.vision.video import PhaseQuadVideoPipeline, VideoGenerationConfig
    >>>
    >>> # Create pipeline (mock for testing)
    >>> pipeline = PhaseQuadVideoPipeline.create_mock()
    >>>
    >>> # Generate video
    >>> result = pipeline.generate(
    ...     "A cat playing with a ball",
    ...     config=VideoGenerationConfig(num_frames=16)
    ... )
    >>>
    >>> # Save result
    >>> result.save("output.mp4")
"""

from symbolu_extensions.vision.phase_integrator_3d import PhaseIntegrator3D, VideoMeta
from symbolu_extensions.vision.video.vae import PretrainedVideoVAE, load_video_vae
from symbolu_extensions.vision.video.config import PhaseQuadVideoConfig, BCVFVideoConfig
from symbolu_extensions.vision.video.generator import PhaseQuadVideoGenerator
from symbolu_extensions.vision.video.pipeline import (
    PhaseQuadVideoPipeline,
    VideoGenerationConfig,
    VideoGenerationResult,
)
from symbolu_extensions.vision.video.bcvf_video import (
    BCVFVideoQuadWeighter,
    AdaptiveBCVFVideoWeighter,
    compute_video_bcvf_metrics,
)
from symbolu_extensions.vision.video.fscsv_wrapper import (
    FSCSVConfig,
    FSCSVModule,
    FSCSVPipeline,
    make_fscsv_callback,
    CouplingSchedule,
    IdentitySchedule,
    GradientSafetyBound,
    ThreeBandDecomposer,
    ProxyEncoder,
    FrameCoherence,
    TweedieProjection,
    compute_phase_correlation,
    compute_semantic_similarity,
)

__all__ = [
    # Core components
    "PhaseIntegrator3D",
    "VideoMeta",
    # VAE
    "PretrainedVideoVAE",
    "load_video_vae",
    # Config
    "PhaseQuadVideoConfig",
    "BCVFVideoConfig",
    # Model
    "PhaseQuadVideoGenerator",
    # BCVF
    "BCVFVideoQuadWeighter",
    "AdaptiveBCVFVideoWeighter",
    "compute_video_bcvf_metrics",
    # FSCS-V (Frequency-Stratified Coherence for Video)
    "FSCSVConfig",
    "FSCSVModule",
    "FSCSVPipeline",
    "make_fscsv_callback",
    "CouplingSchedule",
    "IdentitySchedule",
    "GradientSafetyBound",
    "ThreeBandDecomposer",
    "ProxyEncoder",
    "FrameCoherence",
    "TweedieProjection",
    "compute_phase_correlation",
    "compute_semantic_similarity",
    # Pipeline
    "PhaseQuadVideoPipeline",
    "VideoGenerationConfig",
    "VideoGenerationResult",
]

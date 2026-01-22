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
    >>> from symbolu.vision.video import PhaseQuadVideoPipeline, VideoGenerationConfig
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

from symbolu.vision.phase_integrator_3d import PhaseIntegrator3D, VideoMeta
from symbolu.vision.video.vae import PretrainedVideoVAE, load_video_vae
from symbolu.vision.video.config import PhaseQuadVideoConfig
from symbolu.vision.video.generator import PhaseQuadVideoGenerator
from symbolu.vision.video.pipeline import (
    PhaseQuadVideoPipeline,
    VideoGenerationConfig,
    VideoGenerationResult,
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
    # Model
    "PhaseQuadVideoGenerator",
    # Pipeline
    "PhaseQuadVideoPipeline",
    "VideoGenerationConfig",
    "VideoGenerationResult",
]

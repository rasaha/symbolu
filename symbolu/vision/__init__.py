"""
Phase-Quad Image Generator for Symbolu.

This module implements a Phase-Quad architecture for image generation,
adapting the proven Phase Integrator + Quad Proposal approach from language
models to latent-space diffusion for coherent image synthesis.

Core Principles:
1. Quad Proposes, Phase Decides - Quadratic attention generates TopK proposals;
   Phase integrates them via sigmoid gating (no softmax winner-take-all)
2. No-Write Contract - Control signals are low-dimensional scalars/per-head values,
   never token-position embeddings
3. Bi-Axial Phase Scans - Row and column scans for 2D spatial coherence
4. Diffusion-Compatible - Plugs into standard latent diffusion training objectives

Key Innovation:
- O(N) phase accumulation with bi-axial scans
- O(N·K) sparse global retrieval via TopK proposals
- Provable contribution through replaceability ablation tests
"""

from symbolu.vision.contracts import (
    ContractViolationError,
    assert_control_shape,
)
from symbolu.vision.controls import (
    PhaseControl,
    QuadControl,
    GateControl,
    BlockControl,
    PatchMeta,
)
from symbolu.vision.config import PhaseQuadVisionConfig
from symbolu.vision.scan_manager import ScanManager2D
from symbolu.vision.rope_2d import RotaryPositionEmbedding2D
from symbolu.vision.patch_embed import PatchEmbed2D
from symbolu.vision.phase_integrator import PhaseIntegrator1D, PhaseIntegrator2D
from symbolu.vision.quad_retriever import QuadRetriever2D
from symbolu.vision.gate_mixer import GateMixer
from symbolu.vision.local_mixer import LocalMixer
from symbolu.vision.cognade_vision_block import CognadeVisionBlock
from symbolu.vision.phase_quad_generator import PhaseQuadImageGenerator
from symbolu.vision.diagnostics import (
    QuadUtilizationMetrics,
    PhaseHealthMetrics,
    compute_quad_utilization,
    compute_phase_health,
    compute_ghost_metrics,
)

__all__ = [
    # Contracts
    "ContractViolationError",
    "assert_control_shape",
    # Controls
    "PhaseControl",
    "QuadControl",
    "GateControl",
    "BlockControl",
    "PatchMeta",
    # Config
    "PhaseQuadVisionConfig",
    # Core Components
    "ScanManager2D",
    "RotaryPositionEmbedding2D",
    "PatchEmbed2D",
    "PhaseIntegrator1D",
    "PhaseIntegrator2D",
    "QuadRetriever2D",
    "GateMixer",
    "LocalMixer",
    "CognadeVisionBlock",
    "PhaseQuadImageGenerator",
    # Diagnostics
    "QuadUtilizationMetrics",
    "PhaseHealthMetrics",
    "compute_quad_utilization",
    "compute_phase_health",
    "compute_ghost_metrics",
]

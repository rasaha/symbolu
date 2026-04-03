#!/usr/bin/env python3
"""
Image Generation Configuration
==============================

Configuration dataclasses for Symbol-U image generation with FLUX integration.

This module provides configuration for:
- ImageGenConfig: Main pipeline configuration
- FluxConfig: FLUX model-specific settings
- CoherenceConfig: Coherence monitoring thresholds
- LayerMappingConfig: 12-layer to FLUX block mapping

Usage:
------
    from symbolu_extensions.image_gen.config import ImageGenConfig, FluxConfig

    # Use defaults
    config = ImageGenConfig()

    # Custom configuration
    config = ImageGenConfig(
        model_id="black-forest-labs/FLUX.1-schnell",
        num_inference_steps=4,
        coherence_threshold=0.8,
    )
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class FluxVariant(Enum):
    """FLUX model variants."""
    DEV = "black-forest-labs/FLUX.1-dev"
    SCHNELL = "black-forest-labs/FLUX.1-schnell"
    PRO = "black-forest-labs/FLUX.1-pro"  # API only


class GenerationMode(Enum):
    """Generation modes with different coherence/speed tradeoffs."""
    FAST = "fast"           # Minimal coherence checks, max speed
    BALANCED = "balanced"   # Standard coherence monitoring
    QUALITY = "quality"     # Full coherence verification, slower
    STRICT = "strict"       # Maximum verification, may reject/retry


class OutputFormat(Enum):
    """Output format options."""
    PIL = "pil"         # PIL.Image
    TENSOR = "tensor"   # torch.Tensor
    NUMPY = "numpy"     # numpy.ndarray
    LATENT = "latent"   # Return latents (for further processing)


# =============================================================================
# FLUX MODEL CONFIGURATION
# =============================================================================

@dataclass
class FluxConfig:
    """
    Configuration for FLUX model.

    Attributes:
        model_id: HuggingFace model ID or local path
        variant: FLUX variant (dev, schnell, pro)
        torch_dtype: Model dtype (float16, bfloat16, float32)
        device: Device to run on (cuda, cpu, mps)
        enable_model_cpu_offload: Offload model to CPU when not in use
        enable_sequential_cpu_offload: More aggressive offloading
        enable_attention_slicing: Reduce memory with sliced attention
        vae_slicing: Enable VAE slicing for large images
    """
    model_id: str = "black-forest-labs/FLUX.1-dev"
    variant: FluxVariant = FluxVariant.DEV
    torch_dtype: str = "bfloat16"
    device: str = "cuda"
    enable_model_cpu_offload: bool = False
    enable_sequential_cpu_offload: bool = False
    enable_attention_slicing: bool = False
    vae_slicing: bool = True

    # FLUX architecture constants
    num_double_blocks: int = 19  # Joint text-image attention
    num_single_blocks: int = 38  # Image-only attention
    text_encoder_dim: int = 4096  # T5-XXL dimension
    clip_encoder_dim: int = 768   # CLIP dimension


# =============================================================================
# COHERENCE CONFIGURATION
# =============================================================================

@dataclass
class CoherenceConfig:
    """
    Configuration for coherence monitoring and thresholds.

    Based on patent formulas BCVF, USE, and SCC.

    Attributes:
        coherence_threshold: Global coherence threshold for quality gate
        entropy_threshold: Maximum semantic entropy before correction
        completion_threshold: w_final threshold for output release
        min_forward_score: Minimum BCVF forward score (sf)
        min_backward_score: Minimum BCVF backward score (sb)
    """
    # Global thresholds
    coherence_threshold: float = 0.7
    entropy_threshold: float = 2.0
    completion_threshold: float = 0.85

    # BCVF thresholds
    min_forward_score: float = 0.5
    min_backward_score: float = 0.5
    max_consistency_gap: float = 0.3  # |sf - sb| threshold

    # Per-layer thresholds
    identity_distinctness_threshold: float = 0.7   # L2
    structure_coherence_threshold: float = 0.6     # L4
    cognition_entropy_threshold: float = 2.0       # L5
    agency_alignment_threshold: float = 0.5        # L6
    reasoning_contradiction_threshold: float = 0.3  # L7
    purpose_clip_threshold: float = 0.6            # L8
    witness_quality_threshold: float = 0.6         # L9
    unifying_coherence_threshold: float = 0.7      # L10
    integration_resolution_threshold: float = 0.8  # L11


# =============================================================================
# BCVF CONFIGURATION (IMAGE-SPECIFIC)
# =============================================================================

@dataclass
class BCVFImageConfig:
    """
    BCVF configuration for image generation.

    Core formula (B1):
        L = lambda_f * (1 - sf)^2 + lambda_b * (1 - sb)^2 + lambda_c * (sf - sb)^2

    Attributes:
        lambda_forward: Weight for forward feasibility penalty (image quality)
        lambda_backward: Weight for backward goal penalty (prompt alignment)
        lambda_consistency: Weight for forward-backward consistency
        beta: Temperature for exponential weighting
    """
    lambda_forward: float = 1.0
    lambda_backward: float = 1.0
    lambda_consistency: float = 0.5
    beta: float = 2.0

    # Image-specific scoring
    use_clip_scorer: bool = True
    use_aesthetic_scorer: bool = False
    clip_model_id: str = "openai/clip-vit-large-patch14"


# =============================================================================
# USE CONFIGURATION (IMAGE-SPECIFIC)
# =============================================================================

@dataclass
class USEImageConfig:
    """
    USE configuration for phase synchronization in image generation.

    Core formulas:
        U1: C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])
        U4: Delta_phi_i = alpha * dC_total/d_phi_i

    Attributes:
        sync_alpha: Learning rate for phase updates
        sync_steps: Number of synchronization iterations per check
        phase_dim: Dimension of phase vectors
    """
    sync_alpha: float = 0.1
    sync_steps: int = 3
    phase_dim: int = 64
    use_mean_field_approximation: bool = True

    # Cross-layer synchronization
    adjacent_layer_weight: float = 0.8
    skip_layer_weight: float = 0.2


# =============================================================================
# SCC CONFIGURATION (IMAGE-SPECIFIC)
# =============================================================================

@dataclass
class SCCImageConfig:
    """
    SCC configuration for semantic coherence in image generation.

    Core formula (S1):
        C_i(t) = alpha * S_i + beta * R_i + gamma * E_i + delta * P_i

    Attributes:
        alpha: Weight for semantic consistency (S_i)
        beta: Weight for resonance (R_i)
        gamma: Weight for entropy (E_i) - inverted
        delta: Weight for predictability (P_i)
    """
    alpha: float = 0.3  # Semantic consistency
    beta: float = 0.3   # Resonance
    gamma: float = 0.2  # Entropy (inverted)
    delta: float = 0.2  # Predictability

    # Layer weights (importance of each layer)
    layer_weights: Optional[List[float]] = None

    def __post_init__(self):
        # Normalize component weights
        total = self.alpha + self.beta + self.gamma + self.delta
        if abs(total - 1.0) > 0.01:
            self.alpha /= total
            self.beta /= total
            self.gamma /= total
            self.delta /= total

        # Default layer weights (higher for reasoning/integration)
        if self.layer_weights is None:
            self.layer_weights = [
                0.06,  # L1: POTENTIAL
                0.08,  # L2: IDENTITY (entity emergence)
                0.07,  # L3: EXECUTION
                0.09,  # L4: STRUCTURE (layout)
                0.10,  # L5: COGNITION (perception)
                0.10,  # L6: AGENCY (guidance)
                0.12,  # L7: REASONING (discrimination)
                0.10,  # L8: PURPOSE (meaning)
                0.10,  # L9: WITNESSES (self-check)
                0.08,  # L10: UNIFYING (coherence)
                0.06,  # L11: INTEGRATION
                0.04,  # L12: ABSOLVING
            ]


# =============================================================================
# LAYER MAPPING CONFIGURATION
# =============================================================================

@dataclass
class LayerMappingConfig:
    """
    Configuration for mapping FLUX blocks to Symbol-U 12 layers.

    FLUX has 19 double blocks + 38 single blocks = 57 total blocks.
    These map to the 12 ontological layers as specified in the design document.
    """
    # Double block ranges (0-indexed)
    l2_identity_blocks: Tuple[int, int] = (0, 3)      # Blocks 0-2
    l3_execution_blocks: Tuple[int, int] = (3, 6)     # Blocks 3-5
    l4_structure_blocks: Tuple[int, int] = (6, 9)     # Blocks 6-8
    l5_cognition_blocks: Tuple[int, int] = (9, 12)    # Blocks 9-11
    l6_agency_blocks: Tuple[int, int] = (12, 15)      # Blocks 12-14
    l7_reasoning_blocks: Tuple[int, int] = (15, 19)   # Blocks 15-18

    # Single block ranges (0-indexed)
    l8_purpose_blocks: Tuple[int, int] = (0, 10)      # Blocks 0-9
    l9_witnesses_blocks: Tuple[int, int] = (10, 20)   # Blocks 10-19
    l10_unifying_blocks: Tuple[int, int] = (20, 30)   # Blocks 20-29
    l11_integration_blocks: Tuple[int, int] = (30, 38)  # Blocks 30-37

    def get_double_block_layer(self, block_idx: int) -> int:
        """Map double block index to layer number (2-7)."""
        if block_idx < self.l2_identity_blocks[1]:
            return 2
        elif block_idx < self.l3_execution_blocks[1]:
            return 3
        elif block_idx < self.l4_structure_blocks[1]:
            return 4
        elif block_idx < self.l5_cognition_blocks[1]:
            return 5
        elif block_idx < self.l6_agency_blocks[1]:
            return 6
        else:
            return 7

    def get_single_block_layer(self, block_idx: int) -> int:
        """Map single block index to layer number (8-11)."""
        if block_idx < self.l8_purpose_blocks[1]:
            return 8
        elif block_idx < self.l9_witnesses_blocks[1]:
            return 9
        elif block_idx < self.l10_unifying_blocks[1]:
            return 10
        else:
            return 11


# =============================================================================
# 12x12 COHERENCE MATRIX CONFIGURATION
# =============================================================================

@dataclass
class CoherenceMatrixConfig:
    """
    Configuration for the 12x12 coherence coupling matrix.

    The matrix M captures the 144 Bhava relationships between layers.
    M[i,j] = coupling strength between Layer i and Layer j.
    """
    # Coupling decay: how quickly coupling decreases with layer distance
    coupling_decay: float = 0.15  # Per-layer distance decay

    # Minimum coupling (even for distant layers)
    min_coupling: float = 0.05

    # Self-coupling (diagonal)
    self_coupling: float = 1.0

    # Adjacent layer coupling
    adjacent_coupling: float = 0.85

    # Learnable matrix (if True, matrix is a trainable parameter)
    learnable: bool = False

    def build_default_matrix(self) -> List[List[float]]:
        """Build default 12x12 coherence coupling matrix."""
        matrix = []
        for i in range(12):
            row = []
            for j in range(12):
                if i == j:
                    coupling = self.self_coupling
                else:
                    distance = abs(i - j)
                    coupling = max(
                        self.min_coupling,
                        self.adjacent_coupling * (1 - self.coupling_decay * distance)
                    )
                row.append(coupling)
            matrix.append(row)
        return matrix


# =============================================================================
# MAIN IMAGE GENERATION CONFIGURATION
# =============================================================================

@dataclass
class ImageGenConfig:
    """
    Main configuration for Symbol-U image generation pipeline.

    This aggregates all sub-configurations for easy setup.

    Usage:
        config = ImageGenConfig()
        pipeline = SymbolUFluxPipeline(config)
        result = pipeline.generate("A beautiful sunset")
    """
    # Generation parameters
    width: int = 1024
    height: int = 1024
    num_inference_steps: int = 28
    guidance_scale: float = 3.5
    seed: Optional[int] = None

    # Generation mode
    mode: GenerationMode = GenerationMode.BALANCED
    output_format: OutputFormat = OutputFormat.PIL

    # Retry/refinement
    max_retries: int = 3
    enable_targeted_regeneration: bool = True

    # Sub-configurations
    flux: FluxConfig = field(default_factory=FluxConfig)
    coherence: CoherenceConfig = field(default_factory=CoherenceConfig)
    bcvf: BCVFImageConfig = field(default_factory=BCVFImageConfig)
    use: USEImageConfig = field(default_factory=USEImageConfig)
    scc: SCCImageConfig = field(default_factory=SCCImageConfig)
    layer_mapping: LayerMappingConfig = field(default_factory=LayerMappingConfig)
    coherence_matrix: CoherenceMatrixConfig = field(default_factory=CoherenceMatrixConfig)

    # Debug/logging
    verbose: bool = False
    log_layer_coherences: bool = False
    return_intermediate_states: bool = False

    @classmethod
    def fast(cls) -> "ImageGenConfig":
        """Preset for fast generation with minimal checks."""
        return cls(
            mode=GenerationMode.FAST,
            num_inference_steps=4,  # FLUX.1-schnell compatible
            max_retries=1,
            flux=FluxConfig(model_id="black-forest-labs/FLUX.1-schnell"),
        )

    @classmethod
    def quality(cls) -> "ImageGenConfig":
        """Preset for maximum quality with full verification."""
        return cls(
            mode=GenerationMode.QUALITY,
            num_inference_steps=50,
            max_retries=5,
            coherence=CoherenceConfig(
                coherence_threshold=0.8,
                completion_threshold=0.9,
            ),
        )

    @classmethod
    def strict(cls) -> "ImageGenConfig":
        """Preset for strict verification (may reject/retry more)."""
        return cls(
            mode=GenerationMode.STRICT,
            num_inference_steps=50,
            max_retries=10,
            coherence=CoherenceConfig(
                coherence_threshold=0.85,
                completion_threshold=0.95,
                min_forward_score=0.7,
                min_backward_score=0.7,
            ),
        )


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class LayerCoherenceResult:
    """Coherence result for a single layer during generation."""
    layer_index: int
    layer_name: str
    coherence_score: float
    semantic_consistency: float
    resonance: float
    entropy: float
    predictability: float

    @property
    def is_coherent(self) -> bool:
        return self.coherence_score >= 0.5


@dataclass
class ImageGenMetrics:
    """Metrics from image generation."""
    global_coherence: float           # Psi_12 score
    prompt_alignment: float           # BCVF sb score
    quality_score: float              # BCVF sf score
    lagrangian: float                 # L_12 value
    completion_weight: float          # w_final
    layer_coherences: Dict[str, float]
    generation_time_ms: float
    num_retries: int
    potential_issues: List[str] = field(default_factory=list)

    @property
    def confidence(self) -> str:
        """Confidence category based on completion weight."""
        if self.completion_weight >= 0.9:
            return "HIGH"
        elif self.completion_weight >= 0.7:
            return "MEDIUM"
        else:
            return "LOW"


@dataclass
class ImageGenResult:
    """Result from image generation."""
    image: Any  # PIL.Image, torch.Tensor, or np.ndarray
    metrics: ImageGenMetrics
    prompt: str
    seed: int
    config: ImageGenConfig
    success: bool = True
    error_message: Optional[str] = None

    # Optional intermediate data
    layer_states: Optional[Dict[int, Any]] = None
    attention_maps: Optional[Dict[str, Any]] = None

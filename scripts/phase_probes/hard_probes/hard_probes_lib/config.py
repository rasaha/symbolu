"""
Configuration dataclasses for hard probe training.

Defines Config (model/training parameters) and SRKPhaseLearningConfig
(Sovereign Reasoning Kernel monitoring configuration).

CLI Usage (model)::

    python train_hard_probes.py --d-model 128 --num-heads 8 --num-layers 4

CLI Usage (SRK)::

    python train_hard_probes.py --real-language --enable-srk \\
        --srk-dna-bridge-layer 0 --srk-witness-layer 2
"""

import torch
from dataclasses import dataclass, field
from typing import Tuple

from .imports import SOVEREIGN_STATE_DIM

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class Config:
    """Training and model configuration."""
    # Model - INCREASED CAPACITY for proper reasoning (not just compression)
    # Phase needs room to encode: role phase, entity amplitude, operation effects
    d_model: int = 128
    num_heads: int = 8
    num_layers: int = 4
    d_ff: int = 256  # 2x d_model
    dropout: float = 0.1
    max_seq_len: int = 80  # Longer for persistence test (chain 8-12)

    # Training
    batch_size: int = 64
    num_steps: int = 15000
    lr: float = 1e-3
    weight_decay: float = 0.01
    eval_every: int = 1000

    # Dataset
    train_samples: int = 20000
    test_samples_per_split: int = 1000

    # Hard probe settings
    bind_ratio: float = 0.6          # Ratio of BIND-dominant schemas
    train_chain_length: Tuple[int, int] = (3, 5)
    test_chain_length: Tuple[int, int] = (6, 8)
    persist_chain_length: Tuple[int, int] = (8, 12)  # Pure persistence test

    # Parameter matching
    match_params: bool = False  # If True, adjust to match parameter counts

    # Phase collapse fix
    bounded_phase: bool = True  # V9.9.11: Constrain φ to [-π, π] via π*sin()

    # V10.3.8: Dual-Channel Attention (ChatGPT recommendation)
    # Separates content similarity from intent alignment:
    #   s_content = cos(φ_q - φ_k)           # What matches (preserved)
    #   s_align = cos(θ_JEPA - θ_SRK)        # Intent agreement (modulator)
    #   score = s_content * (1 + α * s_align) # Combined
    dual_channel_mode: bool = False  # Enable dual-channel attention
    alignment_authority: float = 0.1  # α: weight for alignment term
    # V10.6.1: Clamp bounds for alignment modulator (ChatGPT caveat)
    # Prevents over-constraint collapse from sustained JEPA/SRK misalignment
    alignment_clamp_min: float = 0.8  # Lower bound for (1 + α * s_align)
    alignment_clamp_max: float = 1.2  # Upper bound for (1 + α * s_align)

    # V10.6.3: Alignment reduction mode (ChatGPT feedback)
    # s_align must be [H] or [], NOT [B, N] (token-position dependent)
    alignment_reduction: str = "per_head"  # "per_head" (recommended), "global" (safest), "per_batch_head"

    # V10.6.3: Contract enforcement mode
    strict_control_contract: bool = True  # If True, raise exceptions; if False, warn and continue

    # Device
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


# =============================================================================
# SRK PHASE LEARNING CONFIGURATION
# =============================================================================
# V10.3.0: SRK (Sovereign Reasoning Kernel) monitors how phase learns at layers
#
# Layer Components:
#   L4:  DNA Bridge - Foundational ontology grounding (12D Bhava projection)
#   L7:  CSR Alignment - Phase Extraction Hook for coherence
#   L9:  Witness Arbitrator - Consciousness/attention arbitration
#   L11: Synthesis Gate - Output integration and quality filtering

@dataclass
class SRKPhaseLearningConfig:
    """Configuration for SRK phase learning monitoring."""
    # Enable SRK phase learning monitoring
    enable_srk: bool = False

    # Layer attachment points (must match model's num_layers)
    dna_bridge_layer: int = 4       # L4: DNA Bridge
    csr_alignment_layer: int = 7    # L7: CSR Alignment / Phase Extraction
    witness_layer: int = 9          # L9: Witness Arbitrator
    synthesis_layer: int = 11       # L11: Synthesis Gate

    # Component toggles
    enable_dna_bridge: bool = True      # Enable DNA Bridge at L4
    enable_phase_hook: bool = True      # Enable Phase Extraction at L7
    enable_witness: bool = True         # Enable Witness Arbitrator at L9
    enable_synthesis: bool = True       # Enable Synthesis Gate at L11

    # Phase learning metrics
    track_phase_coherence: bool = True  # Track phase coherence over training
    track_bhava_diversity: bool = True  # Track 12D ontological diversity
    track_layer_contributions: bool = True  # Track per-layer PPL contribution

    # Loss weights for SRK components (optional auxiliary losses)
    lambda_ontology: float = 0.1        # Ontological alignment loss weight
    lambda_coherence: float = 0.05      # Phase coherence loss weight

    # State dimension (32D Sovereign State)
    state_dim: int = SOVEREIGN_STATE_DIM

    def validate_for_model(self, num_layers: int):
        """Validate layer indices against model's actual layer count."""
        max_layer = num_layers - 1
        warnings = []

        if self.dna_bridge_layer > max_layer:
            warnings.append(f"DNA Bridge layer {self.dna_bridge_layer} > max layer {max_layer}, adjusting to {min(3, max_layer)}")
            self.dna_bridge_layer = min(3, max_layer)

        if self.csr_alignment_layer > max_layer:
            warnings.append(f"CSR layer {self.csr_alignment_layer} > max layer {max_layer}, using layer {max_layer}")
            self.csr_alignment_layer = max_layer

        if self.witness_layer > max_layer:
            warnings.append(f"Witness layer {self.witness_layer} > max layer {max_layer}, using layer {max_layer}")
            self.witness_layer = max_layer

        if self.synthesis_layer > max_layer:
            warnings.append(f"Synthesis layer {self.synthesis_layer} > max layer {max_layer}, using layer {max_layer}")
            self.synthesis_layer = max_layer

        return warnings


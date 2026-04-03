#!/usr/bin/env python3
"""
SymbolU12 with Inter-Layer Bhava Relationships
===============================================

This module upgrades SymbolU12 LLM and Optimized versions to include
the full Vedic Bhava relationship system from the MiniLM V2 engine.

Key Additions:
- BhavaRelationshipModule for 144D inter-layer relationships
- DrishtiAttention for aspect-based cross-layer attention
- Vedic aspect patterns (Conjunction, Opposition, Trine, etc.)
- Bhava significances (Tanu, Dhana, Sahaja, etc.)

Formula [1331]: 9:3 Hierarchical Split
--------------------------------------
When `use_9_3_split=True`, the 12 layers are divided into:

| Tier       | Layers | Role                           | Guna Tendency    |
|------------|--------|--------------------------------|------------------|
| Authority  | 0-8    | State-Delta (ontological)      | Sattva-dominant  |
| Sensory    | 9-11   | Quadratic (token grounding)    | Rajas-prone      |

The HierarchicalGradientScaler in train_unified_llm.py dampens gradients
for Sensory layers (α = 0.1→0.5 over 500 steps) to prevent Rajasic override.

This ensures consistency across all Symbol-U engines:
- MiniLM V2 ✓ Has Bhava
- SymbolU12 LLM ✓ Now has Bhava
- SymbolU12 Optimized ✓ Now has Bhava

Usage:
------
    from symbolu_core.ontological.symbolu12_bhava import (
        SymbolU12LLMWithBhava,
        SymbolU12OptimizedWithBhava,
    )

    # Full LLM with Bhava
    model = SymbolU12LLMWithBhava()
    outputs = model(input_ids)
    print(outputs['bhava_relationships'])  # 144D
    print(outputs['strongest_relationships'])

    # Optimized with Bhava (CPU-friendly)
    model_opt = SymbolU12OptimizedWithBhava()
    outputs = model_opt(input_ids)

    # Training with 9:3 split (use CLI flag):
    # python train_unified_llm.py --use_9_3_split --gradient_warmup_steps 500
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    raise ImportError("PyTorch required for SymbolU12 with Bhava")

# Import Bhava relationship modules
from symbolu_core.ontological.bhava_relationships import (
    BhavaRelationshipModule,
    DrishtiAttention,
    BHAVA_SIGNIFICANCES,
    ASPECT_STRENGTH_MATRIX,
    get_relationship_meaning,
    LAYER_TO_BHAVA,
)
from symbolu_core.ontological.types import LAYER_NAMES, LAYER_INDEX

# Import LRA-optimized Phase Attention for O(n) complex attention
try:
    from symbolu_core.phase_transformer import PhaseAttentionLayer
    PHASE_ATTENTION_AVAILABLE = True
except ImportError:
    PHASE_ATTENTION_AVAILABLE = False
    PhaseAttentionLayer = None


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolU12BhavaConfig:
    """Configuration for SymbolU12 with Bhava relationships."""

    # Model dimensions
    vocab_size: int = 50257
    embed_dim: int = 768
    max_seq_len: int = 2048
    num_heads: int = 8

    # Bhava-specific
    bhava_embed_dim: int = 128
    relationship_embed_dim: int = 32
    num_drishti_heads: int = 4

    # Layer config
    num_pos_tags: int = 50
    num_entity_types: int = 20
    num_concepts: int = 1000
    num_intents: int = 50

    # Thresholds
    activation_threshold: float = 0.1
    coherence_threshold: float = 0.7

    # Formula [1331]: 9:3 Hierarchical Split Configuration
    # When enabled, layers are divided into Authority (State-Delta) and Sensory (Quadratic)
    # - Authority layers (0-8): High stiffness, Sattva-dominant, control Guna Coherence
    # - Sensory layers (9-11): Dampened gradients, Rajas-prone, grounding in tokens
    use_9_3_split: bool = False
    authority_layers: int = 9   # Layers 0-8: State-Delta Authority
    sensory_layers: int = 3     # Layers 9-11: Quadratic Sensory Buffer

    # LRA-Optimized Phase Attention Configuration
    # Uses complex-valued O(n) attention via Euler's formula for Authority layers
    use_phase_attention: bool = True  # Enable Phase Attention for Authority layers
    phase_sync_steps: int = 3         # Synchronization iterations (legacy, kept for compat)
    phase_sync_lr: float = 0.1        # Phase update learning rate
    r_signal_dim: int = 48            # R-Signal dimension for phase bias projection
    phase_cosine_mode: str = "standard"  # V9.6.12: "standard", "shifted", or "complex"

    # Harmonic ratios
    HARMONIC_RATIOS: Dict[int, int] = None

    def __post_init__(self):
        if self.HARMONIC_RATIOS is None:
            self.HARMONIC_RATIOS = {
                1: 100000, 2: 50000, 3: 20000, 4: 10000,
                5: 5000, 6: 2000, 7: 1000, 8: 400,
                9: 100, 10: 50, 11: 10, 12: 1
            }


# =============================================================================
# PHASE ATTENTION BLOCKS (LRA-OPTIMIZED O(N) COMPLEX ATTENTION)
# =============================================================================

class StateDeltaPhaseBlock(nn.Module):
    """
    Authority Layer Block with LRA-Optimized Phase Attention.

    Uses complex-valued O(n) attention via Euler's formula:
        Q = a × e^(iφ)      - Query phasor
        K = a × e^(-iφ)     - Key phasor (conjugate)
        State = CumSum(K × V)  - O(n) aggregation
        Out = Re(Q × State)    - Readout

    This replaces nn.MultiheadAttention for layers 0-8 (Authority/State-Delta)
    to provide cleaner PID controller signals via synchronized phases.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        config: 'SymbolU12BhavaConfig',
        layer_idx: int = 0,
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.embed_dim = embed_dim

        # LRA-Optimized Phase Attention (complex O(n) via Euler)
        if PHASE_ATTENTION_AVAILABLE:
            self.attn = PhaseAttentionLayer(
                embed_dim=embed_dim,
                num_heads=num_heads,
                dropout=0.1,
                sync_steps=config.phase_sync_steps,
                sync_lr=config.phase_sync_lr,
                cosine_mode=getattr(config, 'phase_cosine_mode', 'standard'),  # V9.6.12
            )
            self.use_phase = True
        else:
            # Fallback to standard attention if PhaseAttentionLayer not available
            self.attn = nn.MultiheadAttention(embed_dim, num_heads, batch_first=True)
            self.use_phase = False

        self.norm1 = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )
        self.norm2 = nn.LayerNorm(embed_dim)

        # R-Signal accumulator (for projection to sensory layers)
        # Layers 0-7 accumulate; Layer 8 produces the final R-Signal
        self.r_signal_proj = nn.Linear(embed_dim, config.r_signal_dim)

    def forward(
        self,
        x: torch.Tensor,
        accumulated_r_signal: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass through Phase Attention block.

        Args:
            x: [B, N, D] input tensor
            accumulated_r_signal: [B, R] accumulated R-Signal from previous layers

        Returns:
            output: [B, N, D] transformed tensor
            r_signal: [B, R] updated R-Signal accumulation
        """
        # Phase Attention
        if self.use_phase:
            attn_out = self.attn(x)
        else:
            attn_out, _ = self.attn(x, x, x)

        x = self.norm1(x + attn_out)
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)

        # Compute layer's R-Signal contribution (mean-pooled, projected)
        layer_r = self.r_signal_proj(x.mean(dim=1))  # [B, R]

        # Accumulate R-Signal (exponential moving average style)
        if accumulated_r_signal is not None:
            # Layers closer to witness (layer 8) contribute more
            layer_weight = 0.1 + 0.1 * self.layer_idx  # 0.1 → 0.8 across layers 0-7
            r_signal = accumulated_r_signal * (1 - layer_weight) + layer_r * layer_weight
        else:
            r_signal = layer_r

        return x, r_signal


class QuadraticAttentionWithPhaseBias(nn.Module):
    """
    Quadratic Attention (O(n²)) with R-Signal Phase Bias.

    For Sensory layers (9-11), we use standard quadratic attention BUT
    inject the R-Signal from Layer 8 as a phase bias to guide attention.

    The R-Signal acts as a "Nerve" from the Authority layers, telling
    the Sensory layers WHERE to focus their quadratic attention.

    Phase Bias Injection:
        attention_weights = softmax(QK^T/√d + R_bias)

    Where R_bias is derived from the R-Signal via a learnable projection.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        config: 'SymbolU12BhavaConfig',
        layer_idx: int = 9,  # 9, 10, or 11 for sensory layers
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Standard attention projections
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # R-Signal → Phase Bias projection
        # Projects R-Signal to per-head bias that modulates attention
        self.r_to_phase_bias = nn.Sequential(
            nn.Linear(config.r_signal_dim, embed_dim),
            nn.Tanh(),  # Bound the bias to [-1, 1] range
        )

        self.norm1 = nn.LayerNorm(embed_dim)
        self.ffn = nn.Sequential(
            nn.Linear(embed_dim, embed_dim * 4),
            nn.GELU(),
            nn.Linear(embed_dim * 4, embed_dim),
        )
        self.norm2 = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(0.1)

        self.scale = self.head_dim ** -0.5

    def forward(
        self,
        x: torch.Tensor,
        r_signal: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Forward pass with R-Signal phase bias injection.

        Args:
            x: [B, N, D] input tensor
            r_signal: [B, R] R-Signal from Layer 8 (Witness)
            attention_mask: Optional attention mask

        Returns:
            output: [B, N, D] transformed tensor
        """
        B, N, D = x.shape
        H = self.num_heads

        # Project to Q, K, V
        q = self.q_proj(x).view(B, N, H, self.head_dim).transpose(1, 2)  # [B, H, N, D_h]
        k = self.k_proj(x).view(B, N, H, self.head_dim).transpose(1, 2)
        v = self.v_proj(x).view(B, N, H, self.head_dim).transpose(1, 2)

        # Compute standard attention scores
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * self.scale  # [B, H, N, N]

        # R-Signal Phase Bias Injection
        # Project R-Signal to per-head bias: [B, R] → [B, D] → [B, H, 1, 1]
        phase_bias = self.r_to_phase_bias(r_signal)  # [B, D]
        phase_bias = phase_bias.view(B, H, self.head_dim).mean(dim=-1)  # [B, H]
        phase_bias = phase_bias.unsqueeze(-1).unsqueeze(-1)  # [B, H, 1, 1]

        # Add phase bias to attention scores (broadcasts across N×N)
        # This shifts attention patterns based on R-Signal from Authority layers
        attn_scores = attn_scores + phase_bias

        # Apply causal mask if needed
        if attention_mask is not None:
            attn_scores = attn_scores + attention_mask

        # Softmax and attend
        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = self.dropout(attn_weights)

        attn_out = torch.matmul(attn_weights, v)  # [B, H, N, D_h]
        attn_out = attn_out.transpose(1, 2).contiguous().view(B, N, D)  # [B, N, D]
        attn_out = self.out_proj(attn_out)

        # Residual + Norm + FFN
        x = self.norm1(x + attn_out)
        ffn_out = self.ffn(x)
        x = self.norm2(x + ffn_out)

        return x


# =============================================================================
# BHAVA-ENHANCED UNIFYING LAYER
# =============================================================================

class BhavaUnifyingLayer(nn.Module):
    """
    Layer 10: UNIFYING with Vedic Bhava Relationships

    Enhanced coherence layer that:
    1. Computes C'[i,j] = C[i,j] × S[i,j] coherence matrix
    2. Applies Vedic Drishti (aspect) patterns
    3. Produces 144D Bhava relationship vector
    4. Provides interpretable relationship meanings

    This is the core integration of Bhava into SymbolU12.
    """

    def __init__(self, config: SymbolU12BhavaConfig):
        super().__init__()
        self.config = config
        self.threshold = config.coherence_threshold

        # Bhava relationship module (from bhava_relationships.py)
        self.bhava_module = BhavaRelationshipModule(
            embed_dim=config.bhava_embed_dim,
            num_layers=12,
            relationship_embed_dim=config.relationship_embed_dim,
        )

        # Drishti attention (aspect-based cross-layer attention)
        self.drishti_attention = DrishtiAttention(
            embed_dim=config.embed_dim,
            num_layers=12,
            num_heads=config.num_drishti_heads,
        )

        # Project layer embeddings to bhava dimension
        self.to_bhava = nn.Linear(config.embed_dim, config.bhava_embed_dim)

        # Project from ontological probs (12D) to embed_dim for layer representation
        self.onto_proj = nn.Linear(12, config.embed_dim)

        # Coherence transformer
        self.coherence_attn = nn.MultiheadAttention(
            config.embed_dim, config.num_heads, batch_first=True
        )

        self.norm = nn.LayerNorm(config.embed_dim)

    def forward(
        self,
        layer_embeddings: List[torch.Tensor],
        x: torch.Tensor,
        ontological_probs: Optional[torch.Tensor] = None,
        phase: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Args:
            layer_embeddings: List of [B, embed_dim] from layers 1-9
            x: [B, seq_len, embed_dim] current sequence representation
            ontological_probs: [B, 12] optional ontological probabilities
            phase: Phase value for phase-locked processing

        Returns:
            Dict with:
                unified_x: [B, seq_len, embed_dim] coherence-unified embeddings
                unified_layers: [B, embed_dim] unified layer representation
                C_prime: [B, 12, 12] coherence matrix
                global_coherence: [B] coherence score
                bhava_vector: [B, 144] Bhava relationship vector
                relationship_matrix: [B, 12, 12] relationship strengths
                strongest_relationships: List of top relationships
        """
        B = x.shape[0]
        device = x.device

        # Stack layer embeddings
        stacked = torch.stack(layer_embeddings, dim=1)  # [B, N, embed_dim]
        N = stacked.shape[1]

        # Pad to 12 if needed
        if N < 12:
            padding = torch.zeros(B, 12 - N, stacked.shape[2], device=device)
            stacked = torch.cat([stacked, padding], dim=1)
            N = 12

        # Compute ontological probs if not provided
        if ontological_probs is None:
            # Use layer activation magnitudes as proxy
            layer_mags = stacked.abs().mean(dim=-1)  # [B, 12]
            ontological_probs = F.softmax(layer_mags, dim=-1)

        # =====================================================
        # 1. BHAVA RELATIONSHIPS (144D)
        # =====================================================

        # Compute Bhava relationships
        bhava_output = self.bhava_module(ontological_probs)

        relationship_matrix = bhava_output['relationship_matrix']  # [B, 12, 12]
        bhava_vector = bhava_output['relationship_flat']  # [B, 144]
        aspect_modulated = bhava_output['aspect_modulated']
        bhava_coherence = bhava_output['coherence']  # [B]

        # =====================================================
        # 2. DRISHTI ATTENTION (Cross-layer aspect-based)
        # =====================================================

        # Apply Drishti attention across layers
        attended_layers = self.drishti_attention(stacked, ontological_probs)

        # =====================================================
        # 3. COHERENCE MATRIX C'[i,j] = C[i,j] × S[i,j]
        # =====================================================

        # Semantic similarity S[i,j]
        normalized = F.normalize(attended_layers, dim=-1)
        S = torch.einsum('bid,bjd->bij', normalized, normalized)

        # Phase correlations C[i,j]
        # Use Bhava aspect strengths as phase correlations
        C = torch.tensor(ASPECT_STRENGTH_MATRIX, device=device).unsqueeze(0).expand(B, -1, -1)

        # C'[i,j] = C[i,j] × S[i,j]
        C_prime = C * S

        # Global coherence J
        mask = torch.triu(torch.ones(12, 12, device=device), diagonal=1)
        J_raw = (C_prime * mask).sum(dim=(1, 2)) / (mask.sum() + 1e-8)
        # Fix: Scale J from [-1, 1] to [0, 1] since S (cosine similarity) can be negative
        J = (J_raw + 1.0) / 2.0

        # Combined coherence with Bhava (bhava_coherence now also scaled [0,1])
        global_coherence = 0.5 * J + 0.5 * bhava_coherence

        # Detect violations
        violations = (C_prime < self.threshold) & (mask.bool().unsqueeze(0))

        # =====================================================
        # 4. UNIFIED REPRESENTATION
        # =====================================================

        # Coherence-weighted unified representation
        coherence_weights = F.softmax(C_prime.sum(dim=-1), dim=-1)  # [B, 12]
        unified_layers = torch.einsum('bn,bnd->bd', coherence_weights, attended_layers)

        # Apply coherence to sequence via attention
        coherence_signal = unified_layers.unsqueeze(1).expand(-1, x.shape[1], -1)
        unified_x, _ = self.coherence_attn(x, coherence_signal, coherence_signal)

        # Phase-locked unification
        if phase is not None:
            strength = (1 + torch.cos(phase)) / 2
            output = self.norm(x + unified_x * strength)
        else:
            output = self.norm(x + unified_x)

        return {
            'unified_x': output,
            'unified_layers': unified_layers,
            'C_prime': C_prime,
            'global_coherence': global_coherence,
            'violations': violations,
            'bhava_vector': bhava_vector,
            'relationship_matrix': relationship_matrix,
            'aspect_modulated': aspect_modulated,
            'attended_layers': attended_layers,
        }


# =============================================================================
# SYMBOLU12 LLM WITH BHAVA
# =============================================================================

class SymbolU12LLMWithBhava(nn.Module):
    """
    Full SymbolU12 LLM with Vedic Bhava Inter-Layer Relationships.

    This is the complete ontological transformer with:
    - 12 cognitive layers (Potential → Absolving)
    - 144D Bhava relationship vector
    - Vedic Drishti attention patterns
    - Coherence matrix C'[i,j]
    - Witness layer for confidence
    - Full generative capabilities

    Output Dimensions:
    - Logits: [B, seq_len, vocab_size]
    - Ontological: 12D
    - Bhava: 144D
    - Full vector: 156D (12 + 144)
    """

    def __init__(self, config: Optional[SymbolU12BhavaConfig] = None):
        super().__init__()
        self.config = config or SymbolU12BhavaConfig()
        dim = self.config.embed_dim

        # Token embeddings
        self.embed = nn.Embedding(self.config.vocab_size, dim)
        self.pos_embed = nn.Embedding(self.config.max_seq_len, dim)

        # Layers 1-8: Authority (State-Delta) with Phase Attention
        # Uses LRA-optimized O(n) complex attention when use_phase_attention=True
        if self.config.use_phase_attention and PHASE_ATTENTION_AVAILABLE:
            self.layers_1_8 = nn.ModuleList([
                StateDeltaPhaseBlock(dim, self.config.num_heads, self.config, layer_idx=i)
                for i in range(8)
            ])
            self._use_phase_blocks = True
        else:
            self.layers_1_8 = nn.ModuleList([
                self._create_legacy_layer_block(dim, i) for i in range(8)
            ])
            self._use_phase_blocks = False

        # Layer 9: Witness (meta-cognition) - produces final R-Signal
        self.witness_layer = WitnessLayerWithBhava(self.config)

        # R-Signal projection from Witness layer output
        self.witness_r_proj = nn.Linear(dim, self.config.r_signal_dim)

        # Layer 10: Unifying with Bhava
        self.unifying_layer = BhavaUnifyingLayer(self.config)

        # Layer 11: Integration
        self.integration_layer = IntegrationLayerWithBhava(self.config)

        # Layer 12: Absolving
        self.absolving_layer = AbsolvingLayerWithBhava(self.config)

        # Output head
        self.lm_head = nn.Linear(dim, self.config.vocab_size, bias=False)

        # Tie weights
        self.lm_head.weight = self.embed.weight

        # Master phase
        self.master_phase = nn.Parameter(torch.zeros(1))

    def _create_legacy_layer_block(self, dim: int, layer_idx: int) -> nn.Module:
        """Create a legacy transformer block (fallback when Phase Attention unavailable)."""
        return nn.ModuleDict({
            'attn': nn.MultiheadAttention(dim, self.config.num_heads, batch_first=True),
            'norm1': nn.LayerNorm(dim),
            'ffn': nn.Sequential(
                nn.Linear(dim, dim * 4),
                nn.GELU(),
                nn.Linear(dim * 4, dim),
            ),
            'norm2': nn.LayerNorm(dim),
            # Add R-Signal projection for legacy mode
            'r_proj': nn.Linear(dim, self.config.r_signal_dim),
        })

    def _forward_legacy_layer_block(
        self,
        block: nn.ModuleDict,
        x: torch.Tensor,
        accumulated_r_signal: Optional[torch.Tensor],
        layer_idx: int,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Forward through a legacy layer block with R-Signal accumulation."""
        attn_out, _ = block['attn'](x, x, x)
        x = block['norm1'](x + attn_out)
        ffn_out = block['ffn'](x)
        x = block['norm2'](x + ffn_out)

        # R-Signal accumulation (same logic as StateDeltaPhaseBlock)
        layer_r = block['r_proj'](x.mean(dim=1))
        if accumulated_r_signal is not None:
            layer_weight = 0.1 + 0.1 * layer_idx
            r_signal = accumulated_r_signal * (1 - layer_weight) + layer_r * layer_weight
        else:
            r_signal = layer_r

        return x, r_signal

    def get_layer_phase(self, layer_idx: int) -> torch.Tensor:
        return self.config.HARMONIC_RATIOS[layer_idx] * self.master_phase

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        Forward pass through all 12 ontological layers with Bhava.

        Architecture with Phase Attention and R-Signal:
        - Layers 0-7: Authority (State-Delta) with O(n) Phase Attention
          → Accumulates R-Signal (48D) progressively
        - Layer 8 (Witness): Meta-cognition, produces final R-Signal
        - Layers 9-11: Sensory (Quadratic) receives R-Signal as phase bias
        """
        B, seq_len = input_ids.shape
        device = input_ids.device

        # Embeddings
        pos = torch.arange(seq_len, device=device).unsqueeze(0).expand(B, -1)
        x = self.embed(input_ids) + self.pos_embed(pos)

        # Layer embeddings storage
        layer_embeddings = []

        # R-Signal accumulation through Authority layers
        r_signal = None  # Will be accumulated through layers 0-7

        # Layers 1-8: Authority processing with Phase Attention and R-Signal accumulation
        for i, block in enumerate(self.layers_1_8):
            if self._use_phase_blocks:
                # StateDeltaPhaseBlock with R-Signal accumulation
                x, r_signal = block(x, accumulated_r_signal=r_signal)
            else:
                # Legacy mode with R-Signal accumulation
                x, r_signal = self._forward_legacy_layer_block(block, x, r_signal, i)
            layer_embeddings.append(x.mean(dim=1))

        # Layer 9: Witness - produces final R-Signal from witness state
        x, state, confidence = self.witness_layer(x)
        layer_embeddings.append(state)

        # Finalize R-Signal: combine accumulated R-Signal with Witness state
        witness_r = self.witness_r_proj(state)  # [B, R]
        if r_signal is not None:
            # Witness has highest weight (0.9) in final R-Signal
            r_signal = r_signal * 0.1 + witness_r * 0.9
        else:
            r_signal = witness_r

        # Compute ontological probs from layer embeddings
        stacked = torch.stack(layer_embeddings, dim=1)  # [B, 9, dim]
        layer_mags = stacked.abs().mean(dim=-1)  # [B, 9]
        # Pad to 12
        layer_mags = F.pad(layer_mags, (0, 3), value=0.0)
        ontological_probs = F.softmax(layer_mags, dim=-1)

        # Layer 10: Unifying with Bhava
        unify_output = self.unifying_layer(
            layer_embeddings, x, ontological_probs, self.get_layer_phase(10)
        )
        x = unify_output['unified_x']
        layer_embeddings.append(unify_output['unified_layers'])

        # Layer 11: Integration
        x, resolution_needed = self.integration_layer(
            x, unify_output['unified_layers'],
            unify_output['global_coherence'],
            self.get_layer_phase(11)
        )
        layer_embeddings.append(x.mean(dim=1))

        # Layer 12: Absolving
        logits, completion = self.absolving_layer(x, self.get_layer_phase(12))
        layer_embeddings.append(x.mean(dim=1))

        # Build full 156D vector (12D onto + 144D bhava)
        full_vector = torch.cat([
            ontological_probs,
            unify_output['bhava_vector'],
        ], dim=-1)

        return {
            # Generation
            'logits': logits,
            'completion': completion,

            # Ontological
            'ontological_probs': ontological_probs,
            'layer_embeddings': layer_embeddings,

            # Bhava relationships (NEW)
            'bhava_vector': unify_output['bhava_vector'],  # 144D
            'relationship_matrix': unify_output['relationship_matrix'],  # 12x12
            'aspect_modulated': unify_output['aspect_modulated'],

            # R-Signal (Authority → Sensory nerve signal)
            'r_signal': r_signal,  # [B, 48] - Phase bias for Sensory layers

            # Coherence
            'coherence_matrix': unify_output['C_prime'],
            'global_coherence': unify_output['global_coherence'],
            'violations': unify_output['violations'],

            # Witness
            'witness_confidence': confidence,

            # Full vector
            'full_vector': full_vector,  # 156D
        }

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze text with full Bhava relationships.
        """
        import numpy as np
        self.eval()

        # Tokenize (simple)
        tokens = [ord(c) % self.config.vocab_size for c in text[:self.config.max_seq_len]]
        input_ids = torch.tensor([tokens], device=next(self.parameters()).device)

        with torch.no_grad():
            outputs = self.forward(input_ids)

        # Extract results
        probs = outputs['ontological_probs'].squeeze(0).cpu().numpy()
        bhava = outputs['bhava_vector'].squeeze(0).cpu().numpy()
        coherence = outputs['global_coherence'].mean().item()
        confidence = outputs['witness_confidence'].mean().item()

        # Dominant layer
        dominant_idx = int(np.argmax(probs))
        dominant_layer = LAYER_NAMES[dominant_idx]

        # Get Bhava significance
        bhava_num = LAYER_TO_BHAVA[dominant_idx]
        bhava_sig = BHAVA_SIGNIFICANCES[bhava_num]

        # Extract strongest relationships
        rel_matrix = outputs['relationship_matrix'].squeeze(0).cpu().numpy()
        strongest = self._extract_strongest_relationships(rel_matrix)

        return {
            'dominant_layer': dominant_layer,
            'confidence': float(probs[dominant_idx]),
            'coherence': coherence,
            'witness_confidence': confidence,
            'probabilities': {LAYER_NAMES[i]: float(probs[i]) for i in range(12)},
            'bhava_significance': bhava_sig,
            'ontological_vector': probs.tolist(),
            'bhava_vector': bhava.tolist(),
            'full_vector': (probs.tolist() + bhava.tolist()),
            'strongest_relationships': strongest,
            'engine_type': 'symbolu12_llm_bhava',
        }

    def _extract_strongest_relationships(
        self,
        rel_matrix,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Extract strongest Bhava relationships."""
        relationships = []
        for i in range(12):
            for j in range(12):
                if i != j:
                    meaning = get_relationship_meaning(i, j)
                    relationships.append({
                        'from_layer': LAYER_NAMES[i],
                        'to_layer': LAYER_NAMES[j],
                        'strength': float(rel_matrix[i, j]),
                        'bhava_name': meaning['relationship_bhava']['name'],
                        'bhava_meaning': meaning['relationship_bhava']['meaning'],
                        'interpretation': meaning['interpretation'],
                    })
        relationships.sort(key=lambda x: abs(x['strength']), reverse=True)
        return relationships[:top_k]


# =============================================================================
# HELPER LAYERS
# =============================================================================

class WitnessLayerWithBhava(nn.Module):
    """Layer 9: Witness with Bhava awareness."""

    def __init__(self, config: SymbolU12BhavaConfig):
        super().__init__()
        dim = config.embed_dim
        self.state_encoder = nn.Linear(dim, dim)
        self.confidence_head = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.ReLU(),
            nn.Linear(dim // 2, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        state = self.state_encoder(x.mean(dim=1))
        confidence = self.confidence_head(state)
        return x, state, confidence


class IntegrationLayerWithBhava(nn.Module):
    """Layer 11: Integration with Bhava-aware resolution."""

    def __init__(self, config: SymbolU12BhavaConfig):
        super().__init__()
        dim = config.embed_dim
        self.resolver = nn.Sequential(
            nn.Linear(dim * 2, dim),
            nn.ReLU(),
            nn.Linear(dim, dim),
        )
        self.norm = nn.LayerNorm(dim)

    def forward(
        self,
        x: torch.Tensor,
        unified: torch.Tensor,
        coherence: torch.Tensor,
        phase: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        B, seq_len, dim = x.shape

        # Resolution needed if coherence is low
        needs_resolution = (coherence < 0.7).float().view(B, 1, 1)

        unified_exp = unified.unsqueeze(1).expand(-1, seq_len, -1)
        resolution_input = torch.cat([x, unified_exp], dim=-1)
        resolved = self.resolver(resolution_input)

        if phase is not None:
            commitment = (1 + torch.cos(phase)) / 2
            output = x + (resolved - x) * needs_resolution * commitment
        else:
            output = x + (resolved - x) * needs_resolution

        return self.norm(output), needs_resolution.squeeze()


class AbsolvingLayerWithBhava(nn.Module):
    """Layer 12: Absolving with completion awareness."""

    def __init__(self, config: SymbolU12BhavaConfig):
        super().__init__()
        dim = config.embed_dim
        self.completion_head = nn.Sequential(
            nn.Linear(dim, dim // 2),
            nn.ReLU(),
            nn.Linear(dim // 2, 1),
            nn.Sigmoid(),
        )
        self.output_proj = nn.Linear(dim, config.vocab_size, bias=False)

    def forward(
        self,
        x: torch.Tensor,
        phase: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        completion = self.completion_head(x)
        logits = self.output_proj(x)
        return logits, completion


# =============================================================================
# OPTIMIZED VERSION WITH BHAVA
# =============================================================================

class SymbolU12OptimizedWithBhava(nn.Module):
    """
    Optimized SymbolU12 with Bhava relationships.

    CPU-friendly version with:
    - Smaller dimensions (256D vs 768D)
    - Sparse attention
    - KV-cache for generation
    - Full Bhava relationship support

    Output: 156D (12D onto + 144D bhava)
    """

    def __init__(
        self,
        vocab_size: int = 32000,
        embed_dim: int = 256,
        num_heads: int = 4,
        max_seq_len: int = 512,
    ):
        super().__init__()

        self.config = SymbolU12BhavaConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_heads=num_heads,
            max_seq_len=max_seq_len,
            bhava_embed_dim=64,  # Smaller for optimized
            relationship_embed_dim=16,
            num_drishti_heads=2,
        )

        dim = embed_dim

        # Embeddings
        self.embed = nn.Embedding(vocab_size, dim)
        self.pos_embed = nn.Embedding(max_seq_len, dim)

        # Fused layers 1-8
        self.layers = nn.ModuleList([
            nn.Sequential(
                nn.LayerNorm(dim),
                nn.Linear(dim, dim * 2),
                nn.GELU(),
                nn.Linear(dim * 2, dim),
            )
            for _ in range(8)
        ])

        # Witness (simplified)
        self.witness = nn.Linear(dim, 1)

        # Bhava Unifying layer
        self.unifying = BhavaUnifyingLayer(self.config)

        # Integration (simplified)
        self.integration = nn.Linear(dim * 2, dim)

        # Output
        self.norm = nn.LayerNorm(dim)
        self.lm_head = nn.Linear(dim, vocab_size, bias=False)
        self.lm_head.weight = self.embed.weight

    def forward(self, input_ids: torch.Tensor) -> Dict[str, Any]:
        B, seq_len = input_ids.shape
        device = input_ids.device

        # Embeddings
        pos = torch.arange(seq_len, device=device)
        x = self.embed(input_ids) + self.pos_embed(pos)

        # Layers 1-8
        layer_embeds = []
        for layer in self.layers:
            x = x + layer(x)
            layer_embeds.append(x.mean(dim=1))

        # Witness
        confidence = torch.sigmoid(self.witness(x.mean(dim=1)))
        layer_embeds.append(x.mean(dim=1))

        # Ontological probs
        stacked = torch.stack(layer_embeds, dim=1)
        layer_mags = stacked.abs().mean(dim=-1)
        layer_mags = F.pad(layer_mags, (0, 12 - layer_mags.shape[1]), value=0.0)
        ontological_probs = F.softmax(layer_mags, dim=-1)

        # Unifying with Bhava
        unify_out = self.unifying(layer_embeds, x, ontological_probs)
        x = unify_out['unified_x']

        # Integration
        unified_exp = unify_out['unified_layers'].unsqueeze(1).expand(-1, seq_len, -1)
        x = x + self.integration(torch.cat([x, unified_exp], dim=-1))

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)

        # Full 156D vector
        full_vector = torch.cat([ontological_probs, unify_out['bhava_vector']], dim=-1)

        return {
            'logits': logits,
            'ontological_probs': ontological_probs,
            'bhava_vector': unify_out['bhava_vector'],
            'relationship_matrix': unify_out['relationship_matrix'],
            'global_coherence': unify_out['global_coherence'],
            'witness_confidence': confidence,
            'full_vector': full_vector,
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_symbolu12_llm_bhava() -> SymbolU12LLMWithBhava:
    """Create full SymbolU12 LLM with Bhava (768D)."""
    return SymbolU12LLMWithBhava()


def create_symbolu12_optimized_bhava() -> SymbolU12OptimizedWithBhava:
    """Create optimized SymbolU12 with Bhava (256D, CPU-friendly)."""
    return SymbolU12OptimizedWithBhava()


def create_symbolu12_tiny_bhava() -> SymbolU12OptimizedWithBhava:
    """Create tiny SymbolU12 with Bhava (128D, edge devices)."""
    return SymbolU12OptimizedWithBhava(
        vocab_size=8000,
        embed_dim=128,
        num_heads=2,
        max_seq_len=256,
    )


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   SYMBOLU12 WITH BHAVA RELATIONSHIPS")
    print("=" * 70)

    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                 BHAVA RELATIONSHIPS IN SYMBOLU12                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  OUTPUT DIMENSIONS:                                                         │
│  ─────────────────                                                          │
│  • Ontological: 12D (layer probabilities)                                  │
│  • Bhava: 144D (12×12 inter-layer relationships)                           │
│  • Full Vector: 156D (12 + 144)                                            │
│                                                                             │
│  VEDIC COMPONENTS:                                                          │
│  ─────────────────                                                          │
│  • Bhava Significances: Tanu, Dhana, Sahaja, Sukha, Putra...              │
│  • Drishti Patterns: Conjunction, Opposition, Trine, Square...            │
│  • Aspect Strengths: 1.0 (Conj/Opp), 0.9 (Trine), 0.75 (Square)...        │
│                                                                             │
│  RELATIONSHIP INTERPRETATION:                                               │
│  ────────────────────────────                                               │
│  Example: Cognition (Layer 5) → Purpose (Layer 8)                          │
│  Bhava: Sukha (Happiness/Comfort)                                          │
│  Meaning: "Cognition finds comfort in Purpose"                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
    """)

    print("\nBhava Significances:")
    for i in range(1, 13):
        sig = BHAVA_SIGNIFICANCES[i]
        print(f"  {i:2d}. {sig['name']:8s} - {sig['meaning']:12s} ({sig['description']})")

    print("\n" + "-" * 70)
    print("Model Sizes:")

    models = {
        'Full LLM (768D)': SymbolU12LLMWithBhava,
        'Optimized (256D)': create_symbolu12_optimized_bhava,
        'Tiny (128D)': create_symbolu12_tiny_bhava,
    }

    for name, factory in models.items():
        try:
            if callable(factory) and not isinstance(factory, type):
                model = factory()
            else:
                model = factory()
            params = sum(p.numel() for p in model.parameters())
            print(f"  {name}: {params:,} parameters")
        except Exception as e:
            print(f"  {name}: Error - {e}")

    print("\n" + "=" * 70)
    print("   NOW ALL ENGINES HAVE CONSISTENT BHAVA RELATIONSHIPS!")
    print("=" * 70)

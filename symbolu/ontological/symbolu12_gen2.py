#!/usr/bin/env python3
"""
SymbolU12 Generation 2: Hierarchical Complex Phase Rotation
============================================================

This is the next-generation SymbolU12 architecture that implements:

1. Complex-valued embeddings: z = r × e^{iθ} throughout the network
2. Hierarchical 3-tier Bhava with top-down phase rotation
3. Phase Attention with complex synchronization
4. Context-dependent interpretation (same input, different meaning based on intent)

Key Innovation:
  Higher layers SET THE CONTEXT for lower layers via phase rotation.
  The same sensory input means different things depending on intent.

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │  Level 3 (Intent)    →  θ₃  ─────────────────────┐              │
  │                                                   │ rotate      │
  │  Level 2 (Abstract)  →  z₂ ─→ z₂' = z₂ × e^{iθ₃} │              │
  │                                                   │ rotate      │
  │  Level 1 (Concrete)  →  z₁ ─→ z₁' = z₁ × e^{iθ₂'}│              │
  │                                                   ▼              │
  │  Output: Hierarchically-oriented Bhava state                    │
  └─────────────────────────────────────────────────────────────────┘

Usage:
    from symbolu.ontological.symbolu12_gen2 import SymbolU12Gen2

    model = SymbolU12Gen2()
    outputs = model(input_ids)

    # Access hierarchical states
    print(outputs['level_3_phase'])      # Intent context phase
    print(outputs['bhava_complex'])      # Full complex Bhava states
    print(outputs['hierarchy_coherence']) # Per-level coherence

Author: SymbolU Team
Date: December 2025
"""

import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.ontological.hierarchical_complex_bhava import (
    HierarchicalComplexBhava,
    HierarchyConfig,
    to_complex,
    from_complex,
    complex_multiply,
    phase_rotate,
    compute_coherence,
)
from symbolu.ontological.types import LAYER_NAMES, NUM_LAYERS


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SymbolU12Gen2Config:
    """Configuration for SymbolU12 Generation 2."""

    # Model dimensions
    vocab_size: int = 50257
    embed_dim: int = 768
    max_seq_len: int = 2048
    num_heads: int = 8
    num_layers: int = 12  # Transformer layers (not Bhava layers)

    # Complex embedding dimensions
    complex_dim: int = 64  # Dimension for complex representations
    phase_dim: int = 128   # Phase attention dimension

    # Hierarchy configuration
    hierarchy_config: HierarchyConfig = field(default_factory=HierarchyConfig)

    # Phase synchronization
    sync_steps: int = 3
    sync_lr: float = 0.1

    # Training
    dropout: float = 0.1
    use_flash_attention: bool = True
    use_gradient_checkpointing: bool = False

    # FFN
    ffn_mult: float = 4.0

    def __post_init__(self):
        self.hierarchy_config = HierarchyConfig(embed_dim=self.complex_dim)


# =============================================================================
# COMPLEX EMBEDDING LAYER
# =============================================================================

class ComplexEmbedding(nn.Module):
    """
    Embedding layer that outputs complex-valued representations.

    Each token is embedded as z = r × e^{iθ} where:
    - r (magnitude) comes from standard embedding
    - θ (phase) comes from a learned phase embedding

    This gives each token an intrinsic "phase" that can be synchronized.
    """

    def __init__(self, num_embeddings: int, embedding_dim: int):
        super().__init__()

        # Magnitude embedding (standard)
        self.magnitude_embed = nn.Embedding(num_embeddings, embedding_dim)

        # Phase embedding (new - gives each token intrinsic phase)
        self.phase_embed = nn.Embedding(num_embeddings, embedding_dim)

        # Initialize magnitude normally, phase uniformly in [0, 2π]
        nn.init.normal_(self.magnitude_embed.weight, std=0.02)
        nn.init.uniform_(self.phase_embed.weight, 0, 2 * math.pi)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        """
        Args:
            input_ids: [B, T] token IDs

        Returns:
            complex_embed: [B, T, D, 2] complex embeddings (real, imag)
        """
        magnitude = torch.sigmoid(self.magnitude_embed(input_ids))  # [B, T, D]
        phase = self.phase_embed(input_ids)  # [B, T, D]

        # Convert to complex
        return to_complex(magnitude, phase)


class ComplexPositionalEncoding(nn.Module):
    """
    Positional encoding in complex space.

    Positions are encoded as phase rotations, so position affects
    the ANGLE of the embedding, not just the magnitude.

    This allows for RoPE-like behavior naturally in complex space.
    """

    def __init__(self, max_seq_len: int, embed_dim: int):
        super().__init__()

        # Learnable phase shifts per position
        self.phase_shift = nn.Parameter(torch.zeros(max_seq_len, embed_dim))

        # Initialize with sinusoidal pattern
        position = torch.arange(max_seq_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, embed_dim, 2) * (-math.log(10000.0) / embed_dim))

        # Set odd dimensions
        self.phase_shift.data[:, 0::2] = torch.sin(position * div_term)
        self.phase_shift.data[:, 1::2] = torch.cos(position * div_term[:embed_dim//2])

        # Scale to [0, 2π]
        self.phase_shift.data = (self.phase_shift.data + 1) * math.pi

    def forward(self, x: torch.Tensor, offset: int = 0) -> torch.Tensor:
        """
        Apply positional encoding via phase rotation.

        Args:
            x: [B, T, D, 2] complex embeddings
            offset: Position offset for inference

        Returns:
            [B, T, D, 2] position-encoded complex embeddings
        """
        T = x.shape[1]
        phase_shifts = self.phase_shift[offset:offset + T]  # [T, D]

        # Rotate by position-dependent phase
        return phase_rotate(x, phase_shifts.unsqueeze(0))


# =============================================================================
# COMPLEX ATTENTION
# =============================================================================

class ComplexAttention(nn.Module):
    """
    Attention in complex space.

    Key innovation: Attention scores are computed as the PHASE ALIGNMENT
    between queries and keys, not just dot product.

    This naturally captures semantic similarity as phase coherence.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        assert embed_dim % num_heads == 0

        # Projections (output 2x for complex)
        self.q_proj = nn.Linear(embed_dim * 2, embed_dim * 2)
        self.k_proj = nn.Linear(embed_dim * 2, embed_dim * 2)
        self.v_proj = nn.Linear(embed_dim * 2, embed_dim * 2)
        self.out_proj = nn.Linear(embed_dim * 2, embed_dim * 2)

        self.dropout = nn.Dropout(dropout)
        self.scale = 1.0 / math.sqrt(self.head_dim)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [B, T, D, 2] complex input
            mask: [B, T, T] attention mask

        Returns:
            output: [B, T, D, 2] attended output
            coherence: [B] phase coherence of attention
        """
        B, T, D, _ = x.shape

        # Flatten complex dimension for linear projections
        x_flat = x.view(B, T, D * 2)  # [B, T, D*2]

        # Project to Q, K, V
        Q = self.q_proj(x_flat).view(B, T, D, 2)  # [B, T, D, 2]
        K = self.k_proj(x_flat).view(B, T, D, 2)
        V = self.v_proj(x_flat).view(B, T, D, 2)

        # Reshape for multi-head attention
        Q = Q.view(B, T, self.num_heads, self.head_dim, 2).transpose(1, 2)  # [B, H, T, Hd, 2]
        K = K.view(B, T, self.num_heads, self.head_dim, 2).transpose(1, 2)
        V = V.view(B, T, self.num_heads, self.head_dim, 2).transpose(1, 2)

        # Compute attention scores using complex inner product
        # <Q, K> = Re(Q* × K) summed over head_dim
        Q_conj = Q.clone()
        Q_conj[..., 1] = -Q_conj[..., 1]  # Conjugate

        # Complex multiplication per position pair
        # This is expensive, so we approximate with phase difference
        Q_mag, Q_phase = from_complex(Q)  # [B, H, T, Hd]
        K_mag, K_phase = from_complex(K)

        # Phase alignment: cos(θ_q - θ_k) - higher when phases align
        phase_diff = Q_phase.unsqueeze(3) - K_phase.unsqueeze(2)  # [B, H, T, T, Hd]
        phase_alignment = torch.cos(phase_diff).mean(dim=-1)  # [B, H, T, T]

        # Magnitude product
        mag_product = (Q_mag.unsqueeze(3) * K_mag.unsqueeze(2)).mean(dim=-1)  # [B, H, T, T]

        # Combined attention score
        attn_scores = (phase_alignment * mag_product) * self.scale

        # Apply mask
        if mask is not None:
            attn_scores = attn_scores.masked_fill(mask.unsqueeze(1) == 0, float('-inf'))

        # Softmax
        attn_probs = F.softmax(attn_scores, dim=-1)
        attn_probs = self.dropout(attn_probs)

        # Apply attention to values
        # V: [B, H, T, Hd, 2], attn_probs: [B, H, T, T]
        # Output: [B, H, T, Hd, 2]
        V_real = V[..., 0]  # [B, H, T, Hd]
        V_imag = V[..., 1]

        out_real = torch.matmul(attn_probs, V_real)  # [B, H, T, Hd]
        out_imag = torch.matmul(attn_probs, V_imag)

        output = torch.stack([out_real, out_imag], dim=-1)  # [B, H, T, Hd, 2]

        # Reshape back
        output = output.transpose(1, 2).contiguous().view(B, T, D, 2)

        # Output projection
        output_flat = output.view(B, T, D * 2)
        output_flat = self.out_proj(output_flat)
        output = output_flat.view(B, T, D, 2)

        # Compute coherence from phase alignment
        coherence = phase_alignment.mean(dim=(1, 2, 3))  # [B]

        return output, coherence


# =============================================================================
# COMPLEX FFN
# =============================================================================

class ComplexFFN(nn.Module):
    """
    Feed-forward network for complex values.

    Uses SwiGLU activation applied separately to real and imaginary parts.
    """

    def __init__(self, embed_dim: int, ffn_mult: float = 4.0, dropout: float = 0.1):
        super().__init__()

        hidden_dim = int(embed_dim * ffn_mult)

        # Projections (2x for complex)
        self.gate_proj = nn.Linear(embed_dim * 2, hidden_dim * 2)
        self.up_proj = nn.Linear(embed_dim * 2, hidden_dim * 2)
        self.down_proj = nn.Linear(hidden_dim * 2, embed_dim * 2)

        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, T, D, 2] complex input

        Returns:
            [B, T, D, 2] complex output
        """
        B, T, D, _ = x.shape

        # Flatten complex
        x_flat = x.view(B, T, D * 2)

        # SwiGLU
        gate = F.silu(self.gate_proj(x_flat))
        up = self.up_proj(x_flat)
        hidden = gate * up
        hidden = self.dropout(hidden)
        output_flat = self.down_proj(hidden)

        return output_flat.view(B, T, D, 2)


# =============================================================================
# COMPLEX TRANSFORMER BLOCK
# =============================================================================

class ComplexTransformerBlock(nn.Module):
    """
    Transformer block operating on complex values.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        ffn_mult: float = 4.0,
        dropout: float = 0.1,
    ):
        super().__init__()

        self.attn = ComplexAttention(embed_dim, num_heads, dropout)
        self.ffn = ComplexFFN(embed_dim, ffn_mult, dropout)

        # Layer norms operate on flattened real+imag
        self.norm1 = nn.LayerNorm(embed_dim * 2)
        self.norm2 = nn.LayerNorm(embed_dim * 2)

    def forward(
        self,
        x: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: [B, T, D, 2] complex input

        Returns:
            output: [B, T, D, 2] complex output
            coherence: [B] attention coherence
        """
        B, T, D, _ = x.shape

        # Pre-norm attention
        x_flat = x.view(B, T, D * 2)
        normed = self.norm1(x_flat).view(B, T, D, 2)

        attn_out, coherence = self.attn(normed, mask)
        x = x + attn_out  # Complex addition is element-wise

        # Pre-norm FFN
        x_flat = x.view(B, T, D * 2)
        normed = self.norm2(x_flat).view(B, T, D, 2)

        ffn_out = self.ffn(normed)
        x = x + ffn_out

        return x, coherence


# =============================================================================
# SYMBOLU12 GENERATION 2 MODEL
# =============================================================================

class SymbolU12Gen2(nn.Module):
    """
    SymbolU12 Generation 2: Hierarchical Complex Phase Rotation.

    This model uses complex-valued representations throughout and
    implements hierarchical Bhava with top-down phase rotation.

    The key innovation: Higher-level intent ROTATES the interpretation
    of lower-level perceptions.
    """

    def __init__(self, config: Optional[SymbolU12Gen2Config] = None):
        super().__init__()

        self.config = config or SymbolU12Gen2Config()
        D = self.config.complex_dim

        # Complex embeddings
        self.embed = ComplexEmbedding(self.config.vocab_size, D)
        self.pos_embed = ComplexPositionalEncoding(self.config.max_seq_len, D)

        # Projection from complex to real for transformer layers
        # (We use real transformers with periodic complex integration)
        self.complex_to_real = nn.Linear(D * 2, self.config.embed_dim)
        self.real_to_complex = nn.Linear(self.config.embed_dim, D * 2)

        # Transformer layers (operate in real space for efficiency)
        self.layers = nn.ModuleList([
            nn.TransformerEncoderLayer(
                d_model=self.config.embed_dim,
                nhead=self.config.num_heads,
                dim_feedforward=int(self.config.embed_dim * self.config.ffn_mult),
                dropout=self.config.dropout,
                activation='gelu',
                batch_first=True,
                norm_first=True,
            )
            for _ in range(self.config.num_layers)
        ])

        # Hierarchical Complex Bhava
        self.hierarchical_bhava = HierarchicalComplexBhava(
            embed_dim=D,
            hierarchy_config=self.config.hierarchy_config,
        )

        # Ontological projector: extract 12D ontological state from hidden
        self.onto_projector = nn.Sequential(
            nn.Linear(self.config.embed_dim, 256),
            nn.GELU(),
            nn.Linear(256, 12),
        )

        # Output head
        self.norm = nn.LayerNorm(self.config.embed_dim)
        self.lm_head = nn.Linear(self.config.embed_dim, self.config.vocab_size, bias=False)

        # Master phase for synchronization
        self.master_phase = nn.Parameter(torch.zeros(1))

        # Layer for incorporating Bhava into hidden state
        self.bhava_integration = nn.Linear(12 * D * 2, self.config.embed_dim)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """
        Forward pass through the model.

        Args:
            input_ids: [B, T] token IDs
            attention_mask: [B, T] attention mask
            labels: [B, T] optional labels for loss computation

        Returns:
            Dict with logits, loss, coherence, bhava states, etc.
        """
        B, T = input_ids.shape
        device = input_ids.device

        # Create causal mask
        if attention_mask is None:
            causal_mask = torch.triu(
                torch.ones(T, T, device=device, dtype=torch.bool),
                diagonal=1
            )
        else:
            causal_mask = attention_mask == 0

        # Complex embeddings
        x_complex = self.embed(input_ids)  # [B, T, D, 2]
        x_complex = self.pos_embed(x_complex)

        # Convert to real for transformer layers
        D = self.config.complex_dim
        x_flat = x_complex.view(B, T, D * 2)
        x = self.complex_to_real(x_flat)  # [B, T, embed_dim]

        # Transformer layers with periodic complex state extraction
        layer_coherences = []
        layer_states = []

        for i, layer in enumerate(self.layers):
            x = layer(x, src_mask=causal_mask)
            layer_states.append(x.mean(dim=1))  # [B, embed_dim]

        # Extract ontological probabilities
        pooled = x.mean(dim=1)  # [B, embed_dim]
        onto_logits = self.onto_projector(pooled)  # [B, 12]
        ontological_probs = F.softmax(onto_logits, dim=-1)

        # Compute hierarchical Bhava
        bhava_output = self.hierarchical_bhava(ontological_probs)

        # Integrate Bhava into hidden state
        bhava_flat = bhava_output['bhava_vector']  # [B, 12 * D * 2]
        bhava_integration = self.bhava_integration(bhava_flat)  # [B, embed_dim]
        bhava_expanded = bhava_integration.unsqueeze(1).expand(-1, T, -1)

        # Phase-modulated integration
        phase_mod = (1 + torch.cos(self.master_phase)) / 2
        x = x + bhava_expanded * phase_mod

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)  # [B, T, vocab_size]

        # Compute loss if labels provided
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_labels.view(-1),
                ignore_index=-100,
            )

        return {
            # Core outputs
            'logits': logits,
            'loss': loss,

            # Ontological state
            'ontological_probs': ontological_probs,

            # Hierarchical Bhava (Gen 2 specific)
            'bhava_complex': bhava_output['bhava_complex'],
            'bhava_vector': bhava_output['bhava_vector'],
            'relationship_matrix': bhava_output['relationship_matrix'],

            # Coherence metrics
            'coherence': bhava_output['coherence'],
            'level_coherences': bhava_output['level_coherences'],

            # Phase information
            'level_phases': bhava_output['level_phases'],
            'level_1_state': bhava_output['level_1_state'],
            'level_2_state': bhava_output['level_2_state'],
            'level_3_state': bhava_output['level_3_state'],

            # For compatibility with existing code
            'hierarchy_coherence': bhava_output['level_coherences'],
        }

    def get_num_params(self, non_embedding: bool = True) -> int:
        """Get number of parameters."""
        n_params = sum(p.numel() for p in self.parameters())
        if non_embedding:
            n_params -= self.embed.magnitude_embed.weight.numel()
            n_params -= self.embed.phase_embed.weight.numel()
        return n_params


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_symbolu12_gen2_small() -> SymbolU12Gen2:
    """Create small Gen 2 model (~45M params)."""
    config = SymbolU12Gen2Config(
        vocab_size=50257,
        embed_dim=512,
        num_heads=8,
        num_layers=6,
        complex_dim=32,
        max_seq_len=1024,
    )
    return SymbolU12Gen2(config)


def create_symbolu12_gen2_medium() -> SymbolU12Gen2:
    """Create medium Gen 2 model (~145M params)."""
    config = SymbolU12Gen2Config(
        vocab_size=50257,
        embed_dim=768,
        num_heads=12,
        num_layers=12,
        complex_dim=64,
        max_seq_len=2048,
    )
    return SymbolU12Gen2(config)


def create_symbolu12_gen2_large() -> SymbolU12Gen2:
    """Create large Gen 2 model (~350M params)."""
    config = SymbolU12Gen2Config(
        vocab_size=50257,
        embed_dim=1024,
        num_heads=16,
        num_layers=24,
        complex_dim=128,
        max_seq_len=2048,
    )
    return SymbolU12Gen2(config)


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   SYMBOLU12 GENERATION 2: HIERARCHICAL COMPLEX PHASE ROTATION")
    print("=" * 70)

    # Test creation
    print("\nCreating small model...")
    model = create_symbolu12_gen2_small()

    n_params = model.get_num_params()
    print(f"Parameters: {n_params:,} ({n_params / 1e6:.1f}M)")

    # Test forward pass
    print("\nTesting forward pass...")
    B, T = 2, 128
    input_ids = torch.randint(0, 1000, (B, T))
    labels = input_ids.clone()

    with torch.no_grad():
        outputs = model(input_ids, labels=labels)

    print("\nOutput shapes:")
    for key, value in outputs.items():
        if isinstance(value, torch.Tensor):
            print(f"  {key}: {tuple(value.shape)}")
        elif value is not None:
            print(f"  {key}: {type(value).__name__}")

    print("\n" + "-" * 70)
    print("Hierarchical Coherence:")
    coh = outputs['level_coherences']
    print(f"  Level 1 (Concrete):    {coh[0, 0].item():.4f}")
    print(f"  Level 2 (Abstract):    {coh[0, 1].item():.4f}")
    print(f"  Level 3 (Intent):      {coh[0, 2].item():.4f}")
    print(f"  Overall:               {outputs['coherence'][0].item():.4f}")

    print("\n" + "-" * 70)
    print("Ontological Distribution:")
    probs = outputs['ontological_probs'][0]
    top_k = torch.topk(probs, 3)
    for i, (val, idx) in enumerate(zip(top_k.values, top_k.indices)):
        print(f"  {i+1}. {LAYER_NAMES[idx.item()]}: {val.item():.4f}")

    print("\n" + "=" * 70)
    print("   GEN 2 MODEL READY FOR TRAINING")
    print("=" * 70)

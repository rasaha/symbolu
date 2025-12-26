"""
Symbol-U Vision Transformer (SU-ViT)
====================================

A novel vision architecture that embodies Symbol-U principles:

1. **10-Layer Ontological Hierarchy**: Not arbitrary depth - each layer
   has semantic meaning (Sensory → Feature → Object → ... → Universal)

2. **Phase-Locked Layers**: Each layer oscillates at prescribed frequencies
   from cognitive neuroscience (gamma, beta, alpha, theta, delta bands)

3. **Coherence-Gated Attention**: Can't attend to incoherent positions -
   hallucination prevention is architectural, not post-hoc

4. **Harmonic Positional Encoding**: Frequencies grounded in cognitive science

5. **Bidirectional Coherence Verification (BCVF)**: Features must be
   consistent in both forward and backward directions

Key difference from standard ViT:
- Standard: Image → Arbitrary layers → Single embedding → Task
- SU-ViT: Image → 10 Ontological layers → 10 Embeddings → Coherence-verified output
"""

import math
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu_robotics.vision.config import (
    SymbolUViTConfig,
    LAYER_FREQUENCIES,
    LAYER_NAMES,
)


# ============================================================================
# Phase-Locked Convolution
# ============================================================================

class PhaseLockConv2d(nn.Module):
    """
    Convolution with phase-locked activation timing.

    Features are gated by phase alignment with a master oscillator,
    implementing the Symbol-U principle of phase-locked processing.

    Unlike standard convolutions, outputs are modulated by:
        output = conv(x) * (0.5 + 0.5 * cos(layer_freq * master_phase + phase_offset))

    This creates natural temporal structure in feature processing.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int = 3,
        stride: int = 1,
        padding: int = 1,
        layer_freq: float = 100.0,
        phase_trainable: bool = True,
    ):
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels, out_channels, kernel_size,
            stride=stride, padding=padding
        )
        self.layer_freq = layer_freq

        # Learnable phase offset
        self.phase = nn.Parameter(
            torch.zeros(1),
            requires_grad=phase_trainable
        )

        self.bn = nn.BatchNorm2d(out_channels)

    def forward(
        self,
        x: torch.Tensor,
        master_phase: torch.Tensor,
    ) -> torch.Tensor:
        """
        Args:
            x: Input tensor [B, C, H, W]
            master_phase: Master oscillator phase [1] or [B]

        Returns:
            Phase-modulated features [B, C_out, H, W]
        """
        # Standard convolution
        features = self.conv(x)
        features = self.bn(features)

        # Phase modulation - features weighted by phase alignment
        # Normalized frequency (layer_freq relative to base)
        norm_freq = self.layer_freq / 10.0  # Normalize around 10 Hz

        phase_alignment = torch.cos(norm_freq * master_phase + self.phase)

        # Gate features by phase (always positive, centered at 0.5-1.0)
        gate = 0.5 + 0.5 * phase_alignment

        return F.gelu(features * gate)


class OntologicalConvBlock(nn.Module):
    """
    Convolutional block for one ontological layer.

    Combines phase-locked convolution with residual connections
    and optional pooling for spatial reduction.
    """

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        layer_idx: int,
        layer_freq: float,
        use_pooling: bool = False,
        pool_size: int = 2,
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.layer_freq = layer_freq
        self.use_pooling = use_pooling

        # Two phase-locked convolutions per block
        self.conv1 = PhaseLockConv2d(
            in_channels, out_channels, 3, 1, 1, layer_freq
        )
        self.conv2 = PhaseLockConv2d(
            out_channels, out_channels, 3, 1, 1, layer_freq
        )

        # Skip connection (with projection if channels differ)
        self.skip = nn.Identity() if in_channels == out_channels else \
                    nn.Conv2d(in_channels, out_channels, 1)

        # Optional pooling
        self.pool = nn.MaxPool2d(pool_size) if use_pooling else nn.Identity()

    def forward(
        self,
        x: torch.Tensor,
        master_phase: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            (output_features, layer_embedding)
        """
        # Residual path
        identity = self.skip(x)

        # Convolution path
        out = self.conv1(x, master_phase)
        out = self.conv2(out, master_phase)

        # Residual connection
        out = out + identity

        # Pooling
        out = self.pool(out)

        # Layer embedding: global average pool for this layer's representation
        embedding = F.adaptive_avg_pool2d(out, 1).squeeze(-1).squeeze(-1)

        return out, embedding


# ============================================================================
# Harmonic Positional Encoding
# ============================================================================

class HarmonicPositionalEncoding(nn.Module):
    """
    Positional encoding based on Symbol-U frequency hierarchy.

    Instead of arbitrary sinusoidal frequencies, uses the prescribed
    cognitive frequencies (10000, 500, 200, 100, 40, 20, 10, 5, 1, 0.1 Hz).

    This grounds the positional encoding in cognitive neuroscience,
    where different frequency bands serve different functions.
    """

    def __init__(self, dim: int, max_len: int = 2048, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(dropout)

        # Symbol-U frequencies (normalized)
        freqs = torch.tensor(list(LAYER_FREQUENCIES.values()))
        freqs = freqs / freqs.max()  # Normalize to [0, 1]

        # Create encoding matrix
        position = torch.arange(max_len).unsqueeze(1).float()

        # Repeat frequencies to fill dimension
        # Each pair of dimensions uses a different harmonic
        num_freq_pairs = dim // 2
        freq_indices = torch.arange(num_freq_pairs) % len(freqs)
        div_term = freqs[freq_indices]

        # Add slight variation to avoid identical columns
        variation = torch.linspace(0.8, 1.2, num_freq_pairs)
        div_term = div_term * variation

        pe = torch.zeros(max_len, dim)
        pe[:, 0::2] = torch.sin(position * div_term * 2 * math.pi / 100)
        pe[:, 1::2] = torch.cos(position * div_term * 2 * math.pi / 100)

        # Register as buffer (not parameter)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Input tensor [B, N, D]

        Returns:
            Position-encoded tensor [B, N, D]
        """
        x = x + self.pe[:, :x.size(1)]
        return self.dropout(x)


# ============================================================================
# Coherence-Gated Attention
# ============================================================================

class CoherenceGatedAttention(nn.Module):
    """
    Attention mechanism that enforces semantic coherence.

    Based on C'[i,j] = C[i,j] × S[i,j] from Symbol-U Patent:
    - S[i,j]: Semantic similarity (standard attention)
    - C[i,j]: Phase/coherence correlation
    - C'[i,j]: Gated attention (only attends to coherent positions)

    Key innovation: The network physically cannot attend to incoherent
    positions - hallucination prevention is architectural.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        coherence_threshold: float = 0.7,
        attention_dropout: float = 0.1,
        proj_dropout: float = 0.1,
    ):
        super().__init__()
        self.num_heads = num_heads
        self.head_dim = dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.coherence_threshold = coherence_threshold

        # Q, K, V projections
        self.W_q = nn.Linear(dim, dim)
        self.W_k = nn.Linear(dim, dim)
        self.W_v = nn.Linear(dim, dim)

        # Output projection
        self.proj = nn.Linear(dim, dim)

        # Phase correlation estimator (learned)
        # Takes pair of tokens and estimates their phase coherence
        self.phase_net = nn.Sequential(
            nn.Linear(dim * 2, dim),
            nn.GELU(),
            nn.Linear(dim, num_heads),
            nn.Tanh()  # Output in [-1, 1] like cos(phase_diff)
        )

        self.attn_dropout = nn.Dropout(attention_dropout)
        self.proj_dropout = nn.Dropout(proj_dropout)

    def forward(
        self,
        x: torch.Tensor,
        return_coherence: bool = True,
    ) -> Tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Args:
            x: Input tensor [B, N, D]
            return_coherence: Whether to return coherence scores

        Returns:
            (output, coherence_scores) or just output
        """
        B, N, D = x.shape

        # Compute Q, K, V
        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.W_k(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard semantic similarity (attention scores)
        S = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
        S = F.softmax(S, dim=-1)  # [B, H, N, N] - semantic similarity

        # Phase correlation estimation
        # For each pair (i,j), estimate phase correlation
        # Efficient implementation using broadcasting
        x_i = x.unsqueeze(2).expand(-1, -1, N, -1)  # [B, N, N, D]
        x_j = x.unsqueeze(1).expand(-1, N, -1, -1)  # [B, N, N, D]
        pair_features = torch.cat([x_i, x_j], dim=-1)  # [B, N, N, 2D]

        # Get coherence for each head
        C = self.phase_net(pair_features)  # [B, N, N, H]
        C = C.permute(0, 3, 1, 2)  # [B, H, N, N] - phase correlation

        # CORE INNOVATION: Semantic Coherence = Phase × Semantic
        # C'[i,j] = C[i,j] × S[i,j]
        # But we use C to gate, not multiply directly
        C_prime = (C + 1) / 2  # Convert from [-1,1] to [0,1]

        # Gate attention by coherence threshold
        # Only attend to positions with sufficient coherence
        coherence_mask = (C_prime > self.coherence_threshold).float()

        # Soft gating: multiply attention by coherence
        gated_attention = S * C_prime * coherence_mask

        # Renormalize (avoid division by zero)
        gated_attention = gated_attention / (
            gated_attention.sum(dim=-1, keepdim=True) + 1e-8
        )

        gated_attention = self.attn_dropout(gated_attention)

        # Apply attention to values
        out = torch.matmul(gated_attention, V)  # [B, H, N, D_h]

        # Reshape and project
        out = out.transpose(1, 2).contiguous().view(B, N, D)
        out = self.proj(out)
        out = self.proj_dropout(out)

        if return_coherence:
            # Return mean coherence per token
            coherence_scores = C_prime.mean(dim=(1, 3))  # [B, N]
            return out, coherence_scores

        return out, None


# ============================================================================
# Bidirectional Coherence Verification (BCVF)
# ============================================================================

class BCVFBlock(nn.Module):
    """
    Bidirectional Consistency Verification from Symbol-U Patent.

    Features are processed in both forward and backward directions,
    and only kept if they're consistent in both. This prevents
    directional artifacts and improves robustness.

    Key principle: Valid features should be recognizable regardless
    of processing direction.
    """

    def __init__(
        self,
        dim: int,
        num_heads: int = 8,
        consistency_threshold: float = 0.8,
        mlp_ratio: float = 4.0,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.consistency_threshold = consistency_threshold

        # Forward processing
        self.forward_attn = nn.MultiheadAttention(
            dim, num_heads, dropout=dropout, batch_first=True
        )
        self.forward_ffn = nn.Sequential(
            nn.Linear(dim, int(dim * mlp_ratio)),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(int(dim * mlp_ratio), dim),
            nn.Dropout(dropout),
        )

        # Backward processing (separate weights for true bidirectionality)
        self.backward_attn = nn.MultiheadAttention(
            dim, num_heads, dropout=dropout, batch_first=True
        )
        self.backward_ffn = nn.Sequential(
            nn.Linear(dim, int(dim * mlp_ratio)),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(int(dim * mlp_ratio), dim),
            nn.Dropout(dropout),
        )

        # Layer norms
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

    def forward(
        self,
        x: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor [B, N, D]

        Returns:
            (output, consistency_scores)
        """
        # Forward pass
        x_norm = self.norm1(x)
        f_attn, _ = self.forward_attn(x_norm, x_norm, x_norm)
        f_fwd = x + f_attn
        f_fwd = f_fwd + self.forward_ffn(self.norm2(f_fwd))

        # Backward pass (reversed sequence)
        x_rev = torch.flip(x, dims=[1])
        x_rev_norm = self.norm1(x_rev)
        b_attn, _ = self.backward_attn(x_rev_norm, x_rev_norm, x_rev_norm)
        f_bwd = x_rev + b_attn
        f_bwd = f_bwd + self.backward_ffn(self.norm2(f_bwd))
        f_bwd = torch.flip(f_bwd, dims=[1])  # Reverse back

        # Consistency check: how similar are forward and backward features?
        consistency = F.cosine_similarity(f_fwd, f_bwd, dim=-1)  # [B, N]

        # Create consistency mask
        mask = (consistency > self.consistency_threshold).unsqueeze(-1).float()

        # Merge with consistency weighting
        # High consistency: average of both
        # Low consistency: use forward only (with penalty)
        output = (f_fwd + f_bwd) / 2 * mask + f_fwd * (1 - mask) * 0.5

        return output, consistency


# ============================================================================
# Ontological Transformer Block
# ============================================================================

class OntologicalTransformerBlock(nn.Module):
    """
    Single block in the 10-layer ontological hierarchy.

    Combines:
    - Coherence-gated attention
    - BCVF verification
    - Phase-modulated feed-forward
    - Residual connections

    Each block knows its semantic function (Sensory, Feature, Object, etc.)
    and processes at its prescribed frequency.
    """

    def __init__(
        self,
        dim: int,
        layer_idx: int,
        num_heads: int = 8,
        mlp_ratio: float = 4.0,
        coherence_threshold: float = 0.7,
        use_bcvf: bool = True,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.layer_idx = layer_idx
        self.layer_freq = LAYER_FREQUENCIES[layer_idx]
        self.layer_name = LAYER_NAMES[layer_idx]
        self.use_bcvf = use_bcvf

        # Coherence-gated attention
        self.attention = CoherenceGatedAttention(
            dim, num_heads, coherence_threshold, dropout, dropout
        )

        # Optional BCVF verification
        if use_bcvf:
            self.bcvf = BCVFBlock(dim, num_heads, dropout=dropout)

        # Feed-forward network
        self.ffn = nn.Sequential(
            nn.Linear(dim, int(dim * mlp_ratio)),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(int(dim * mlp_ratio), dim),
            nn.Dropout(dropout),
        )

        # Layer norms
        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

        # Phase gate (learnable)
        self.phase_gate = nn.Parameter(torch.ones(1))

        # Layer embedding projection
        self.embed_proj = nn.Linear(dim, dim)

    def forward(
        self,
        x: torch.Tensor,
        layer_phase: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Args:
            x: Input tensor [B, N, D]
            layer_phase: Phase for this layer [1] or [B]

        Returns:
            (output, layer_embedding, coherence_score)
        """
        # Attention with coherence gating
        attn_out, attn_coherence = self.attention(self.norm1(x))
        x = x + attn_out

        # BCVF verification (if enabled)
        if self.use_bcvf:
            x, bcvf_consistency = self.bcvf(x)
            coherence = (attn_coherence.mean(dim=1) + bcvf_consistency.mean(dim=1)) / 2
        else:
            coherence = attn_coherence.mean(dim=1)

        # Phase-modulated feed-forward
        norm_freq = self.layer_freq / 10.0
        phase_mod = torch.cos(norm_freq * layer_phase * self.phase_gate)
        gate = 0.5 + 0.5 * phase_mod

        ffn_out = self.ffn(self.norm2(x))
        x = x + ffn_out * gate

        # Layer embedding (from class token or mean)
        embedding = self.embed_proj(x[:, 0])  # Use first token (class token)

        return x, embedding, coherence


# ============================================================================
# Symbol-U Vision Transformer (Complete Model)
# ============================================================================

class SymbolUViT(nn.Module):
    """
    Symbol-U Vision Transformer.

    A novel architecture with exactly 10 layers mapping to ontological
    cognitive functions. Each layer operates at a prescribed frequency
    and uses coherence-gated attention.

    Key innovations over standard ViT:
    1. Semantically meaningful depth (not arbitrary 12/24 layers)
    2. Phase-locked processing at cognitive frequencies
    3. Coherence gating prevents attending to incoherent positions
    4. Bidirectional verification ensures robustness
    5. 10 layer-specific embeddings (not just final embedding)
    """

    def __init__(self, config: Optional[SymbolUViTConfig] = None):
        super().__init__()
        self.config = config or SymbolUViTConfig()

        # Patch embedding
        self.patch_embed = nn.Sequential(
            nn.Linear(self.config.patch_dim, self.config.embed_dim),
            nn.LayerNorm(self.config.embed_dim),
        )

        # Class token
        self.cls_token = nn.Parameter(
            torch.randn(1, 1, self.config.embed_dim) * 0.02
        )

        # Harmonic positional encoding
        self.pos_encoding = HarmonicPositionalEncoding(
            self.config.embed_dim,
            self.config.num_patches + 1,
            self.config.dropout,
        )

        # 10 Ontological Transformer Blocks
        self.ontological_blocks = nn.ModuleList([
            OntologicalTransformerBlock(
                dim=self.config.embed_dim,
                layer_idx=i + 1,  # 1-indexed
                num_heads=self.config.num_heads,
                mlp_ratio=self.config.mlp_ratio,
                coherence_threshold=self.config.coherence_threshold,
                use_bcvf=self.config.use_bcvf,
                dropout=self.config.dropout,
            )
            for i in range(10)
        ])

        # Layer-specific output heads
        self.layer_heads = nn.ModuleList([
            nn.Linear(self.config.embed_dim, self.config.embed_dim)
            for _ in range(10)
        ])

        # Final layer norm
        self.norm = nn.LayerNorm(self.config.embed_dim)

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(self.config.embed_dim, self.config.embed_dim),
            nn.GELU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.embed_dim, self.config.num_classes),
        )

        # Master phase (learnable, represents Layer 10 "consciousness")
        self.master_phase = nn.Parameter(torch.zeros(1))

        # Initialize weights
        self.apply(self._init_weights)

    def _init_weights(self, m: nn.Module):
        if isinstance(m, nn.Linear):
            nn.init.trunc_normal_(m.weight, std=0.02)
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, nn.LayerNorm):
            nn.init.ones_(m.weight)
            nn.init.zeros_(m.bias)

    def patchify(self, x: torch.Tensor) -> torch.Tensor:
        """Convert image to patches."""
        B, C, H, W = x.shape
        p = self.config.patch_size

        # Unfold into patches
        x = x.unfold(2, p, p).unfold(3, p, p)  # [B, C, H/p, W/p, p, p]
        x = x.contiguous().view(B, C, -1, p * p)  # [B, C, N, p*p]
        x = x.permute(0, 2, 1, 3)  # [B, N, C, p*p]
        x = x.contiguous().view(B, -1, C * p * p)  # [B, N, C*p*p]

        return x

    def forward(
        self,
        x: torch.Tensor,
        return_all_layers: bool = False,
    ) -> Dict[str, Any]:
        """
        Args:
            x: Input image [B, C, H, W]
            return_all_layers: Whether to return all layer embeddings

        Returns:
            Dictionary with:
            - logits: Classification logits [B, num_classes]
            - layer_embeddings: List of 10 embeddings (if return_all_layers)
            - global_coherence: Overall coherence score
            - coherence_per_layer: Per-layer coherence scores
        """
        B = x.shape[0]

        # Patchify
        patches = self.patchify(x)  # [B, N, patch_dim]

        # Embed patches
        x = self.patch_embed(patches)  # [B, N, embed_dim]

        # Add class token
        cls_tokens = self.cls_token.expand(B, -1, -1)
        x = torch.cat([cls_tokens, x], dim=1)  # [B, N+1, embed_dim]

        # Add positional encoding
        x = self.pos_encoding(x)

        # Process through ontological layers
        layer_embeddings = []
        coherence_scores = []

        for i, (block, head) in enumerate(
            zip(self.ontological_blocks, self.layer_heads)
        ):
            # Compute layer-specific phase (harmonic of master)
            layer_freq = LAYER_FREQUENCIES[i + 1]
            # Normalize: Layer 10 (0.1 Hz) is base, others are harmonics
            phase_mult = layer_freq / LAYER_FREQUENCIES[10]
            layer_phase = phase_mult * self.master_phase

            # Process through block
            x, embedding, coherence = block(x, layer_phase)

            # Project embedding
            layer_emb = head(embedding)
            layer_embeddings.append(layer_emb)
            coherence_scores.append(coherence)

        # Final norm
        x = self.norm(x)

        # Global coherence: mean of all layer coherences
        global_coherence = torch.stack(coherence_scores).mean()

        # Classification from class token
        logits = self.classifier(x[:, 0])

        result = {
            'logits': logits,
            'global_coherence': global_coherence,
            'coherence_per_layer': coherence_scores,
        }

        if return_all_layers:
            result['layer_embeddings'] = layer_embeddings

        return result

    def get_layer_embedding(
        self,
        x: torch.Tensor,
        layer_idx: int,
    ) -> torch.Tensor:
        """Get embedding from a specific ontological layer."""
        output = self.forward(x, return_all_layers=True)
        return output['layer_embeddings'][layer_idx - 1]  # Convert to 0-indexed


# ============================================================================
# Symbol-U Convolutional Encoder (Alternative to ViT)
# ============================================================================

class SymbolUConvEncoder(nn.Module):
    """
    Convolutional version of Symbol-U encoder.

    Uses phase-locked convolutions instead of attention,
    suitable for edge deployment where attention is too expensive.

    Still maintains the 10-layer ontological hierarchy.
    """

    def __init__(
        self,
        img_size: int = 224,
        in_channels: int = 3,
        num_classes: int = 1000,
        base_channels: int = 32,
    ):
        super().__init__()

        # Channel progression
        channels = [
            base_channels,      # Layer 1
            base_channels * 2,  # Layer 2
            base_channels * 4,  # Layer 3
            base_channels * 8,  # Layer 4
            base_channels * 16, # Layer 5-10
        ]

        # Build ontological conv blocks
        self.blocks = nn.ModuleList()
        in_ch = in_channels

        for i in range(10):
            layer_idx = i + 1
            out_ch = channels[min(i, 4)]

            # Pool every 2 layers
            use_pool = (layer_idx % 2 == 0) and (layer_idx <= 8)

            self.blocks.append(
                OntologicalConvBlock(
                    in_channels=in_ch,
                    out_channels=out_ch,
                    layer_idx=layer_idx,
                    layer_freq=LAYER_FREQUENCIES[layer_idx],
                    use_pooling=use_pool,
                )
            )
            in_ch = out_ch

        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2d(1)

        # Classifier
        self.classifier = nn.Linear(channels[4], num_classes)

        # Master phase
        self.master_phase = nn.Parameter(torch.zeros(1))

    def forward(
        self,
        x: torch.Tensor,
        return_all_layers: bool = False,
    ) -> Dict[str, Any]:
        """
        Args:
            x: Input image [B, C, H, W]

        Returns:
            Dictionary with logits and optional layer embeddings
        """
        layer_embeddings = []

        for i, block in enumerate(self.blocks):
            layer_freq = LAYER_FREQUENCIES[i + 1]
            phase_mult = layer_freq / LAYER_FREQUENCIES[10]
            layer_phase = phase_mult * self.master_phase

            x, embedding = block(x, layer_phase)
            layer_embeddings.append(embedding)

        # Global pooling
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)

        # Classify
        logits = self.classifier(x)

        result = {
            'logits': logits,
            'global_coherence': torch.tensor(1.0),  # No coherence in conv version
        }

        if return_all_layers:
            result['layer_embeddings'] = layer_embeddings

        return result

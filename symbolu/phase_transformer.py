#!/usr/bin/env python3
"""
Phase Transformer: General-Purpose O(n) LLM
============================================

A standalone transformer that replaces O(n²) attention with O(n) phase
synchronization. No ontological/Bhava dependencies - pure general-purpose LLM.

This enables:
1. Direct comparison with standard transformers
2. Testing U1-U4 formulas in isolation
3. Integration into any LLM architecture
4. Potential licensing for cost savings

Key Innovation (Patent U1-U4):
------------------------------
Traditional: Attention = softmax(QK^T/√d) × V    [O(n²)]
Phase:       Attention emerges from phase sync    [O(n)]

Mean-field approximation:
    Σⱼ sin(φᵢ - φⱼ) ≈ N × sin(φᵢ - φ_mean)

Usage:
------
    from symbolu.phase_transformer import (
        PhaseTransformer,
        StandardTransformer,
        compare_models,
    )

    # Create phase transformer (O(n))
    phase_model = PhaseTransformer(
        vocab_size=50257,
        embed_dim=768,
        num_layers=12,
        num_heads=12,
    )

    # Create standard transformer (O(n²)) for comparison
    std_model = StandardTransformer(
        vocab_size=50257,
        embed_dim=768,
        num_layers=12,
        num_heads=12,
    )

    # Compare
    results = compare_models(phase_model, std_model, seq_lengths=[512, 1024, 2048])
"""

import math
import time
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.checkpoint import checkpoint

# Check for FlashAttention / PyTorch 2.0 SDPA availability
FLASH_ATTN_AVAILABLE = False
SDPA_AVAILABLE = hasattr(F, 'scaled_dot_product_attention')

try:
    from flash_attn import flash_attn_func
    from flash_attn.flash_attn_interface import flash_attn_varlen_func
    FLASH_ATTN_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TransformerConfig:
    """Configuration for both Phase and Standard Transformers."""
    vocab_size: int = 50257
    embed_dim: int = 768
    num_layers: int = 12
    num_heads: int = 12
    ff_dim: Optional[int] = None  # Default: 4 * embed_dim
    max_seq_len: int = 8192
    dropout: float = 0.1

    # Phase-specific
    sync_steps: int = 3
    sync_lr: float = 0.1
    temperature: float = 1.0  # Lower = sharper attention (for classification tasks)

    def __post_init__(self):
        if self.ff_dim is None:
            self.ff_dim = 4 * self.embed_dim


# =============================================================================
# PHASE ATTENTION (O(n)) - Standalone Implementation
# =============================================================================

class PhaseAttentionLayer(nn.Module):
    """
    Learned Phase-Amplitude Attention (O(N) Complex Linear Attention)

    V2 UPGRADE using Euler's Formula for cleaner math:

    Mathematically:
        Attn(i,j) = a_i * a_j * cos(φ_i - φ_j)

    Using Euler's formula e^(iφ) = cos(φ) + i*sin(φ):
        cos(φ_i - φ_j) = Re(e^(iφ_i) × e^(-iφ_j))

    Implemented as:
        Q = a * exp(i * φ)       # Query phasor
        K = a * exp(-i * φ)      # Key phasor (conjugate)
        State = CumSum(K * V)    # O(n) aggregation
        Out = Re(Q * State)      # Readout

    This is mathematically equivalent to amplitude-gated phase attention
    but more elegant and numerically stable via complex arithmetic.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        sync_steps: int = 3,      # Unused in V2 but kept for compatibility
        sync_lr: float = 0.1,     # Unused in V2 but kept for compatibility
        temperature: float = 1.0,  # Unused in V2 but kept for compatibility
        aux_scale: float = 0.1,   # Output scaling for auxiliary path integration
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.aux_scale = aux_scale

        # Legacy parameters kept for checkpoint compatibility
        self.sync_steps = sync_steps
        self.temperature = temperature
        self.sync_lr = nn.Parameter(torch.tensor(sync_lr))

        # =====================================================================
        # V2: LEARNED PHASE-AMPLITUDE PROJECTIONS (The "Brain" of Phase)
        # =====================================================================
        # Learn WHAT to sync (Phase) and HOW MUCH to sync (Amplitude)
        self.W_phase = nn.Linear(embed_dim, num_heads, bias=False)
        self.W_amp = nn.Linear(embed_dim, num_heads, bias=False)

        # Value projection (content)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        # Output projection
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=False)

        # Initialize out_proj to near-zero for gradual contribution
        nn.init.zeros_(self.out_proj.weight)

        # Layer normalization for stability
        self.norm = nn.LayerNorm(embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Legacy projections kept for checkpoint compatibility
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.phase_proj = nn.Linear(self.head_dim, self.head_dim)
        self.key_gate = nn.Linear(self.head_dim, self.head_dim)
        self.value_gate = nn.Linear(self.head_dim, self.head_dim)
        # Legacy V2 projections
        self.phase_embed = nn.Linear(embed_dim, num_heads)
        self.amp_gate = nn.Linear(embed_dim, num_heads)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        phase_context: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        Forward pass with O(n) complex phase attention.

        Args:
            x: [B, N, D] input tensor
            causal_mask: Apply causal masking (always True for complex cumsum)
            phase_context: Optional streaming context (not used in V2)

        Returns:
            output: [B, N, D] or (output, None) if phase_context given
        """
        B, N, D = x.shape
        residual = x

        # Pre-norm (standard for modern transformers)
        x_norm = self.norm(x)

        # =====================================================================
        # 1. Project to Phase (φ) and Amplitude (a)
        # =====================================================================
        # φ: learned phase angle per head
        # a: learned amplitude gate (how much this token participates)
        phi = self.W_phase(x_norm)  # [B, N, H]
        a = torch.sigmoid(self.W_amp(x_norm))  # [B, N, H], range (0, 1)

        # =====================================================================
        # 2. Project Values (content)
        # =====================================================================
        v = self.v_proj(x_norm).view(B, N, self.num_heads, self.head_dim)  # [B, N, H, D_h]

        # =====================================================================
        # 3. Form Complex Phasors using Euler's Formula
        # =====================================================================
        # Q = a * e^(iφ)   - Query phasor
        # K = a * e^(-iφ)  - Key phasor (conjugate for cos(φ_i - φ_j))

        # Reshape for broadcasting: [B, N, H] -> [B, N, H, 1]
        phi = phi.unsqueeze(-1)
        a = a.unsqueeze(-1)

        # torch.polar doesn't support BFloat16 - cast to float32 for complex ops
        orig_dtype = phi.dtype
        if orig_dtype == torch.bfloat16:
            phi = phi.float()
            a = a.float()
            v = v.float()

        # Create complex phasors using torch.polar(magnitude, angle)
        q_phasor = torch.polar(a, phi)      # [B, N, H, 1]
        k_phasor = torch.polar(a, -phi)     # [B, N, H, 1] (negative phase = conjugate)

        # =====================================================================
        # 4. O(n) State Accumulation via Complex Cumsum
        # =====================================================================
        # KV = K * V (complex × real = complex)
        # State_t = Σ_{j≤t} K_j * V_j

        # Convert V to complex (real part only, imaginary = 0)
        v_complex = torch.complex(v, torch.zeros_like(v))

        # KV product: [B, N, H, 1] × [B, N, H, D_h] -> [B, N, H, D_h]
        kv_complex = k_phasor * v_complex

        # O(n) Causal aggregation: cumulative sum along sequence dimension
        global_state = torch.cumsum(kv_complex, dim=1)  # [B, N, H, D_h]

        # =====================================================================
        # 5. Readout: Synchronization via Q × State
        # =====================================================================
        # Out = Re(Q × State) = Σ_{j≤t} a_t * a_j * cos(φ_t - φ_j) * V_j
        sync_output = (q_phasor * global_state).real  # [B, N, H, D_h]

        # Cast back to original dtype if we converted
        if orig_dtype == torch.bfloat16:
            sync_output = sync_output.to(orig_dtype)

        # =====================================================================
        # 6. Output Projection
        # =====================================================================
        sync_output = sync_output.reshape(B, N, D)
        output = self.out_proj(sync_output)
        output = self.dropout(output)

        # Scale output for auxiliary path integration
        # This prevents Phase from competing 50/50 with Quadratic attention
        output = output * self.aux_scale

        # Residual connection
        result = output + residual

        # Return with phase_context compatibility (not used in V2)
        if phase_context is not None:
            return result, None
        return result

# =============================================================================
# STANDARD ATTENTION (O(n²)) - For Comparison
# =============================================================================

class StandardAttentionLayer(nn.Module):
    """
    Standard O(n²) Multi-Head Attention Layer.

    For direct comparison with PhaseAttentionLayer.
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
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
    ) -> torch.Tensor:
        """
        Standard attention forward pass (O(n²)).
        """
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # O(n²) attention scores
        attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale

        # Causal mask
        if causal_mask:
            mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # O(n²) value aggregation
        output = torch.matmul(attn, V)

        output = output.transpose(1, 2).reshape(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)

        return self.norm(output + residual)


# =============================================================================
# FEED-FORWARD NETWORK
# =============================================================================

class FeedForward(nn.Module):
    """Standard feed-forward network."""

    def __init__(
        self,
        embed_dim: int,
        ff_dim: int,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(embed_dim, ff_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(ff_dim, embed_dim),
            nn.Dropout(dropout),
        )
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.norm(x + self.net(x))


# =============================================================================
# STATE DELTA PREDICTOR - State-Centric Training (No LM Head Required)
# =============================================================================

class StateDeltaPredictor(nn.Module):
    """
    Predicts next hidden state delta for state-centric training.

    Instead of token prediction (expensive LM head):
        hidden → LM head (50K dim) → CE loss  [O(B·T·V) memory]

    We predict state deltas (cheap):
        h[t] → delta predictor → h[t+1] - h[t]  [O(B·T·d) memory]

    This enables:
    1. Training without vocabulary projection (infinite context)
    2. Learning dynamics rather than discrete tokens
    3. Coherence/entropy-based training signals

    Memory savings: 50K/768 = ~65x reduction per position
    At 1M context: 200GB → 3GB
    """

    def __init__(
        self,
        embed_dim: int,
        hidden_dim: Optional[int] = None,
        dropout: float = 0.1,
        num_layers: int = 2,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        hidden_dim = hidden_dim or embed_dim * 2

        # Multi-layer delta predictor
        layers = []
        in_dim = embed_dim
        for i in range(num_layers - 1):
            layers.extend([
                nn.Linear(in_dim, hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout),
            ])
            in_dim = hidden_dim
        layers.append(nn.Linear(in_dim, embed_dim))

        self.delta_net = nn.Sequential(*layers)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """
        Predict state deltas from current hidden states.

        Args:
            hidden_states: [B, T, embed_dim] - current hidden states

        Returns:
            predicted_deltas: [B, T-1, embed_dim] - predicted h[t+1] - h[t]
        """
        # Predict delta for each position (what should change next)
        deltas = self.delta_net(hidden_states[:, :-1])  # [B, T-1, embed_dim]
        return self.norm(deltas)

    def compute_loss(
        self,
        hidden_states: torch.Tensor,
        reduction: str = 'mean',
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute state delta prediction loss.

        Args:
            hidden_states: [B, T, embed_dim] - hidden states from forward pass
            reduction: 'mean', 'sum', or 'none'

        Returns:
            loss: State delta prediction loss
            metrics: Dict with delta_mae, delta_cosine_sim
        """
        # Actual deltas: h[t+1] - h[t]
        actual_deltas = hidden_states[:, 1:] - hidden_states[:, :-1]  # [B, T-1, d]

        # Predicted deltas
        predicted_deltas = self.forward(hidden_states)  # [B, T-1, d]

        # L2 loss (MSE)
        delta_loss = F.mse_loss(predicted_deltas, actual_deltas, reduction=reduction)

        # Metrics
        with torch.no_grad():
            delta_mae = F.l1_loss(predicted_deltas, actual_deltas)
            # Cosine similarity between predicted and actual deltas
            cos_sim = F.cosine_similarity(
                predicted_deltas.reshape(-1, self.embed_dim),
                actual_deltas.reshape(-1, self.embed_dim),
                dim=-1
            ).mean()

        metrics = {
            'delta_loss': delta_loss.detach(),
            'delta_mae': delta_mae,
            'delta_cosine_sim': cos_sim,
        }

        return delta_loss, metrics


def compute_entropy_change_loss(
    hidden_states: torch.Tensor,
    target_entropy_rate: float = 0.0,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """
    Compute entropy change loss - encourages smooth information flow.

    Measures how much "information" changes between consecutive states
    using the magnitude of state changes as a proxy for entropy.

    Args:
        hidden_states: [B, T, embed_dim]
        target_entropy_rate: Target rate of entropy change (0 = stable)

    Returns:
        loss: Entropy change regularization loss
        metrics: Dict with entropy_rate, entropy_variance
    """
    # State changes as proxy for information change
    deltas = hidden_states[:, 1:] - hidden_states[:, :-1]  # [B, T-1, d]

    # Entropy proxy: L2 norm of deltas (information magnitude)
    entropy_proxy = torch.norm(deltas, dim=-1)  # [B, T-1]

    # Mean entropy rate
    entropy_rate = entropy_proxy.mean()

    # Variance of entropy rate (want consistency)
    entropy_variance = entropy_proxy.var()

    # Loss: deviation from target rate + variance penalty
    loss = (entropy_rate - target_entropy_rate).abs() + 0.1 * entropy_variance

    metrics = {
        'entropy_rate': entropy_rate.detach(),
        'entropy_variance': entropy_variance.detach(),
    }

    return loss, metrics


def compute_constraint_satisfaction_loss(
    hidden_states: torch.Tensor,
    phase_coherence: Optional[torch.Tensor] = None,
) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
    """
    Compute constraint satisfaction loss for state-centric training.

    Constraints:
    1. Bounded norm: Hidden states should have bounded magnitude
    2. Diversity: States should be diverse (not collapse to same point)
    3. Smoothness: Consecutive states should be smooth (Lipschitz)

    Args:
        hidden_states: [B, T, embed_dim]
        phase_coherence: Optional phase coherence from attention (if available)

    Returns:
        loss: Constraint satisfaction loss
        metrics: Dict with norm_violation, diversity, smoothness
    """
    B, T, D = hidden_states.shape

    # 1. Bounded norm constraint (soft constraint)
    norms = torch.norm(hidden_states, dim=-1)  # [B, T]
    max_norm = 10.0  # Soft upper bound
    norm_violation = F.relu(norms - max_norm).mean()

    # 2. Diversity constraint: states should span the space
    # Use variance across time as diversity measure
    diversity = hidden_states.var(dim=1).mean()  # Want high diversity
    diversity_loss = F.relu(1.0 - diversity)  # Penalize if diversity < 1

    # 3. Smoothness constraint: Lipschitz bound on state changes
    deltas = hidden_states[:, 1:] - hidden_states[:, :-1]
    delta_norms = torch.norm(deltas, dim=-1)  # [B, T-1]
    max_delta = 5.0  # Soft Lipschitz bound
    smoothness_violation = F.relu(delta_norms - max_delta).mean()

    # Combined loss
    loss = norm_violation + diversity_loss + smoothness_violation

    metrics = {
        'norm_violation': norm_violation.detach(),
        'diversity': diversity.detach(),
        'smoothness_violation': smoothness_violation.detach(),
    }

    # Add phase coherence if available
    if phase_coherence is not None:
        metrics['phase_coherence'] = phase_coherence.detach()

    return loss, metrics


# =============================================================================
# LOCAL ATTENTION (Sliding Window) - O(n*w)
# =============================================================================

class LocalAttention(nn.Module):
    """
    Sliding window local attention for fast local pattern learning.

    Complexity: O(n * window_size) instead of O(n²)

    Backends:
    - 'flash': FlashAttention with sliding window (fastest, requires flash-attn)
    - 'sdpa': PyTorch 2.0 SDPA (good performance, built-in)
    - 'unfold': Manual unfold implementation (fallback, always works)
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        window_size: int = 256,
        dropout: float = 0.1,
        backend: str = 'auto',  # 'auto', 'flash', 'sdpa', 'unfold'
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.window_size = window_size
        self.scale = self.head_dim ** -0.5
        self.dropout_p = dropout

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

        # Select backend
        if backend == 'auto':
            if FLASH_ATTN_AVAILABLE:
                self.backend = 'flash'
            elif SDPA_AVAILABLE:
                self.backend = 'sdpa'
            else:
                self.backend = 'unfold'
        else:
            self.backend = backend

    def _forward_flash(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                       causal: bool) -> torch.Tensor:
        """FlashAttention with sliding window - O(n×w) kernel-level."""
        # flash_attn expects (B, N, H, head_dim)
        Q = Q.transpose(1, 2)  # (B, N, H, head_dim)
        K = K.transpose(1, 2)
        V = V.transpose(1, 2)

        # FlashAttention with window_size parameter
        output = flash_attn_func(
            Q, K, V,
            dropout_p=self.dropout_p if self.training else 0.0,
            causal=causal,
            window_size=(self.window_size, 0),  # (left, right) - causal means right=0
        )
        return output.transpose(1, 2)  # back to (B, H, N, head_dim)

    def _forward_sdpa(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                      B: int, N: int, causal: bool) -> torch.Tensor:
        """PyTorch 2.0 SDPA - creates block-sparse mask for O(n×w)."""
        w = self.window_size

        # Create sliding window + causal mask
        # This is still O(n²) in mask creation but SDPA is optimized
        # For true O(n×w), use flash backend
        if causal:
            # Create band matrix mask: each position attends to [i-w+1, i]
            row_idx = torch.arange(N, device=Q.device).unsqueeze(1)
            col_idx = torch.arange(N, device=Q.device).unsqueeze(0)
            # Valid if: col <= row (causal) AND col >= row - w + 1 (window)
            mask = (col_idx <= row_idx) & (col_idx >= row_idx - w + 1)
            attn_mask = torch.zeros(N, N, device=Q.device, dtype=Q.dtype)
            attn_mask.masked_fill_(~mask, float('-inf'))
        else:
            attn_mask = None

        output = F.scaled_dot_product_attention(
            Q, K, V,
            attn_mask=attn_mask,
            dropout_p=self.dropout_p if self.training else 0.0,
            is_causal=False,  # We handle causality in attn_mask
        )
        return output

    def _forward_unfold(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                        B: int, N: int, causal: bool) -> torch.Tensor:
        """Unfold-based sliding window - TRUE O(n×w), no N×N tensors.

        Uses chunked processing to reduce peak memory usage for long sequences.
        """
        w = self.window_size

        # For large batch × sequence, process in chunks to avoid OOM
        # K_windows memory ≈ B × H × chunk × w × head_dim × 2 bytes
        # Very aggressive chunking for large batches to leave room for gradients
        chunk_size = max(64, min(256, 1024 // max(B, 1)))

        if B * N > 8192 and N > chunk_size:
            # Process in chunks along sequence dimension
            return self._forward_unfold_chunked(Q, K, V, B, N, causal, chunk_size)

        # Pad K and V on the left so each position can look back w-1 positions
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Use unfold to create sliding windows of size w
        K_windows = K_padded.unfold(2, w, 1)  # (B, H, N, head_dim, w)
        V_windows = V_padded.unfold(2, w, 1)

        # Rearrange for attention computation
        K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, N, w, head_dim)
        V_windows = V_windows.permute(0, 1, 2, 4, 3)

        # Compute attention scores: Q @ K^T for each window
        Q_expanded = Q.unsqueeze(3)  # (B, H, N, 1, head_dim)
        attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
        attn = attn.squeeze(3)  # (B, H, N, w)

        if causal:
            # Mask out padding positions
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))
            attn = attn.masked_fill(mask.unsqueeze(0).unsqueeze(0), float('-inf'))

        attn = F.softmax(attn, dim=-1)
        attn = self.dropout(attn)

        # Apply attention to values
        attn_expanded = attn.unsqueeze(3)  # (B, H, N, 1, w)
        output = torch.matmul(attn_expanded, V_windows)
        output = output.squeeze(3)  # (B, H, N, head_dim)

        return output

    def _forward_unfold_chunked(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor,
                                 B: int, N: int, causal: bool, chunk_size: int) -> torch.Tensor:
        """Chunked unfold processing for memory efficiency with large batches."""
        w = self.window_size
        H = Q.shape[1]
        head_dim = Q.shape[-1]

        # Pad K and V once
        K_padded = F.pad(K, (0, 0, w - 1, 0), value=0)  # (B, H, N+w-1, head_dim)
        V_padded = F.pad(V, (0, 0, w - 1, 0), value=0)

        # Pre-compute causal mask info
        if causal:
            positions = torch.arange(N, device=Q.device)
            valid_counts = torch.clamp(positions + 1, max=w)
            window_indices = torch.arange(w, device=Q.device)
            causal_mask = window_indices.unsqueeze(0) < (w - valid_counts.unsqueeze(1))

        # Process in chunks
        outputs = []
        for start in range(0, N, chunk_size):
            end = min(start + chunk_size, N)
            chunk_len = end - start

            # Extract Q chunk
            Q_chunk = Q[:, :, start:end, :]  # (B, H, chunk_len, head_dim)

            # Extract corresponding K, V windows
            # K_padded indices [start:end] correspond to original [start-w+1:end]
            K_chunk_padded = K_padded[:, :, start:end + w - 1, :]
            V_chunk_padded = V_padded[:, :, start:end + w - 1, :]

            # Unfold this chunk
            K_windows = K_chunk_padded.unfold(2, w, 1)  # (B, H, chunk_len, head_dim, w)
            V_windows = V_chunk_padded.unfold(2, w, 1)
            K_windows = K_windows.permute(0, 1, 2, 4, 3)  # (B, H, chunk_len, w, head_dim)
            V_windows = V_windows.permute(0, 1, 2, 4, 3)

            # Attention for this chunk
            Q_expanded = Q_chunk.unsqueeze(3)  # (B, H, chunk_len, 1, head_dim)
            attn = torch.matmul(Q_expanded, K_windows.transpose(-2, -1)) * self.scale
            attn = attn.squeeze(3)  # (B, H, chunk_len, w)

            if causal:
                chunk_mask = causal_mask[start:end, :]  # (chunk_len, w)
                attn = attn.masked_fill(chunk_mask.unsqueeze(0).unsqueeze(0), float('-inf'))

            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)

            # Apply to values
            attn_expanded = attn.unsqueeze(3)  # (B, H, chunk_len, 1, w)
            out_chunk = torch.matmul(attn_expanded, V_windows)
            out_chunk = out_chunk.squeeze(3)  # (B, H, chunk_len, head_dim)
            outputs.append(out_chunk)

        return torch.cat(outputs, dim=2)

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        """
        Local attention with sliding window - O(n × window_size) complexity.

        Automatically selects best available backend:
        1. FlashAttention (if available) - fastest, true O(n×w) kernel
        2. PyTorch SDPA (if available) - good performance
        3. Unfold (fallback) - always works, true O(n×w)
        """
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Q, K, V: (B, H, N, head_dim)

        # Select backend
        if self.backend == 'flash' and FLASH_ATTN_AVAILABLE:
            output = self._forward_flash(Q, K, V, causal_mask)
        elif self.backend == 'sdpa' and SDPA_AVAILABLE:
            output = self._forward_sdpa(Q, K, V, B, N, causal_mask)
        else:
            output = self._forward_unfold(Q, K, V, B, N, causal_mask)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)

        return self.norm(residual + output)


# =============================================================================
# LIGHTNING ATTENTION (O(d²) constant KV cache)
# =============================================================================

class LightningAttention(nn.Module):
    """
    Linear attention with constant O(d²) KV cache - inspired by TransNormerLLM/RetNet.

    Memory: O(d²) regardless of sequence length (vs O(n×w) for local attention)
    Compute: O(n·d²) per layer

    Key formula:
        kv_t = λ · kv_{t-1} + k_t^T · v_t   (d×d matrix, constant size)
        o_t = q_t · kv_t

    This enables infinite context with bounded memory.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        dropout: float = 0.1,
        decay_init: float = 0.99,
        use_decay_mask: bool = True,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.scale = self.head_dim ** -0.5
        self.use_decay_mask = use_decay_mask

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        # Learnable per-head decay factors
        self.decay = nn.Parameter(torch.full((num_heads,), decay_init))

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def _forward_recurrent(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor) -> torch.Tensor:
        """
        Recurrent mode: O(d²) memory, O(n·d²) compute.
        Best for inference with very long sequences.
        """
        B, H, N, D = Q.shape
        device = Q.device

        # Initialize KV cache: (B, H, d, d) - constant size!
        kv = torch.zeros(B, H, D, D, device=device, dtype=Q.dtype)

        outputs = []
        decay = torch.sigmoid(self.decay).view(1, H, 1, 1)  # (1, H, 1, 1)

        for t in range(N):
            k_t = K[:, :, t, :]  # (B, H, D)
            v_t = V[:, :, t, :]  # (B, H, D)
            q_t = Q[:, :, t, :]  # (B, H, D)

            # Update KV cache with decay: O(d²) per step
            # kv_t = λ · kv_{t-1} + k_t^T · v_t
            kv_update = torch.einsum('bhd,bhe->bhde', k_t, v_t)
            kv = decay * kv + kv_update

            # Compute output: O(d²) per step
            o_t = torch.einsum('bhd,bhde->bhe', q_t, kv) * self.scale
            outputs.append(o_t)

        return torch.stack(outputs, dim=2)  # (B, H, N, D)

    def _forward_parallel(self, Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor) -> torch.Tensor:
        """
        Parallel mode: Uses cumulative sum with decay weights.
        Better for training (parallelizable), but creates O(n²) decay matrix.
        Falls back to chunked approach for very long sequences.
        """
        B, H, N, D = Q.shape
        device = Q.device

        # For shorter sequences, use full parallel computation
        if N <= 2048:
            # Compute decay weights matrix: (N, N) lower triangular
            positions = torch.arange(N, device=device, dtype=Q.dtype)
            decay = torch.sigmoid(self.decay).view(H, 1, 1)  # (H, 1, 1)

            # decay_weights[i,j] = λ^(i-j) for j <= i, else 0
            diff = positions.unsqueeze(0) - positions.unsqueeze(1)  # (N, N)
            decay_weights = decay ** diff.unsqueeze(0).clamp(min=0)  # (H, N, N)
            decay_weights = torch.tril(decay_weights)  # Causal mask

            # Compute KV terms: (B, H, N, D, D)
            kv_terms = torch.einsum('bhnd,bhne->bhnde', K, V)

            # Cumulative weighted sum: (B, H, N, D, D)
            kv_cumsum = torch.einsum('hts,bhtde->bhsde', decay_weights, kv_terms)

            # Output: (B, H, N, D)
            output = torch.einsum('bhnd,bhnde->bhne', Q, kv_cumsum) * self.scale
            return output
        else:
            # For longer sequences, use recurrent to avoid O(n²) memory
            return self._forward_recurrent(Q, K, V)

    def forward(self, x: torch.Tensor, causal_mask: bool = True, mode: str = 'auto') -> torch.Tensor:
        """
        Lightning attention forward pass.

        Args:
            x: Input tensor (B, N, D)
            causal_mask: Always True for autoregressive (built into the method)
            mode: 'auto', 'recurrent', or 'parallel'
        """
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Q, K, V: (B, H, N, D)

        if mode == 'recurrent' or (mode == 'auto' and N > 2048):
            output = self._forward_recurrent(Q, K, V)
        else:
            output = self._forward_parallel(Q, K, V)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)
        output = self.dropout(output)

        return self.norm(residual + output)


class LightningTransformerBlock(nn.Module):
    """Transformer block with Lightning Attention."""

    def __init__(self, config: TransformerConfig, decay_init: float = 0.99):
        super().__init__()
        self.attention = LightningAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
            decay_init=decay_init,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# STANDARD SOFTMAX ATTENTION (for grouped hybrid)
# =============================================================================

class StandardAttention(nn.Module):
    """
    Standard O(n²) softmax attention - used sparingly in grouped hybrid.
    High-fidelity retrieval layer to complement linear attention.
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
        self.scale = self.head_dim ** -0.5

        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        B, N, D = x.shape
        residual = x

        Q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.k_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.v_proj(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard attention: O(n²)
        if SDPA_AVAILABLE:
            output = F.scaled_dot_product_attention(
                Q, K, V, is_causal=causal_mask,
                dropout_p=self.dropout.p if self.training else 0.0,
            )
        else:
            attn = torch.matmul(Q, K.transpose(-2, -1)) * self.scale
            if causal_mask:
                mask = torch.triu(torch.ones(N, N, device=x.device, dtype=torch.bool), diagonal=1)
                attn = attn.masked_fill(mask, float('-inf'))
            attn = F.softmax(attn, dim=-1)
            attn = self.dropout(attn)
            output = torch.matmul(attn, V)

        output = output.transpose(1, 2).contiguous().view(B, N, D)
        output = self.out_proj(output)

        return self.norm(residual + output)


class StandardAttentionBlock(nn.Module):
    """Transformer block with standard softmax attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.attention = StandardAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# GROUPED HYBRID TRANSFORMER (M linear + 1 softmax pattern)
# =============================================================================

class GroupedHybridTransformer(nn.Module):
    """
    Grouped Hybrid Transformer: M layers of Lightning + 1 layer of Softmax.

    Architecture: [Lightning × M, Softmax] × num_groups

    This pattern:
    - Uses efficient linear attention (Lightning) for most computation
    - Periodically uses softmax attention for high-fidelity retrieval/correction
    - Optimal M is 4-7 based on scaling laws

    Memory: O(d²) for Lightning layers + O(n²) only for sparse softmax layers
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        # Grouped hybrid params
        M: int = 4,  # Lightning layers per group
        num_groups: int = 3,  # Number of (M+1) groups
        decay_init: float = 0.99,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
    ):
        super().__init__()

        if ff_dim is None:
            ff_dim = 4 * embed_dim

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_groups * (M + 1),  # Total layers
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.M = M
        self.num_groups = num_groups
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Build grouped layers: [Lightning × M, Softmax] × num_groups
        self.blocks = nn.ModuleList()
        for g in range(num_groups):
            # M layers of Lightning Attention
            for m in range(M):
                self.blocks.append(LightningTransformerBlock(config, decay_init=decay_init))
            # 1 layer of Standard Softmax Attention
            self.blocks.append(StandardAttentionBlock(config))

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        self._init_weights()

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        # Without this, lm_head is random → gibberish output early in training
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def _init_weights(self):
        for module in self.modules():
            if isinstance(module, nn.Linear):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
                if module.bias is not None:
                    torch.nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        x: torch.Tensor,
        return_hidden: bool = False,
        causal_mask: bool = True,
    ) -> Dict[str, Any]:
        B, N = x.shape
        device = x.device

        # Embeddings
        positions = torch.arange(N, device=device).unsqueeze(0)
        x = self.token_embed(x) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        hidden_states = [x] if return_hidden else []

        # Forward through grouped blocks
        for block in self.blocks:
            x = block(x, causal_mask)
            if return_hidden:
                hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x)

        output = {"logits": logits}
        if return_hidden:
            output["hidden_states"] = hidden_states

        return output

    def get_num_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


# =============================================================================
# HYBRID ATTENTION (Local + Phase)
# =============================================================================

class HybridAttentionLayer(nn.Module):
    """
    Combines local attention (fast pattern learning) with phase attention (global context).

    Sequential processing: LocalAttn → PhaseAttn (memory efficient)
    - Local: Quickly learns syntax, grammar, local patterns
    - Phase: Handles long-range dependencies efficiently O(n)

    Previous parallel approach (α_local * LocalAttn(x) + α_phase * PhaseAttn(x))
    required 2x memory. Sequential approach processes one at a time.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        window_size: int = 256,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        local_backend: str = 'auto',
        temperature: float = 1.0,  # Lower = sharper phase attention
    ):
        super().__init__()
        # Keep alphas for potential future use (e.g., residual weighting)
        self.alpha_local = nn.Parameter(torch.tensor(alpha_local))
        self.alpha_phase = nn.Parameter(torch.tensor(alpha_phase))

        self.local_attn = LocalAttention(
            embed_dim=embed_dim,
            num_heads=num_heads,
            window_size=window_size,
            dropout=dropout,
            backend=local_backend,
        )

        # V9.6.11: Fix Double Dampening - use aux_scale=1.0 in hybrid mode
        # Previously: aux_scale=0.1 (default) × w_phase=0.2 = 2% effective signal
        # This caused phase attention gradients to be 40x smaller than local
        # Fix: Full strength phase output, let alpha weights handle the mixing
        self.phase_attn = PhaseAttentionLayer(
            embed_dim=embed_dim,
            num_heads=num_heads,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
            aux_scale=1.0,  # V9.6.11: Full strength (was 0.1 causing 2% effective signal)
        )

        self.norm = nn.LayerNorm(embed_dim)

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        """
        Weighted hybrid forward: Blend local and phase attention outputs.

        Key fix: Phase attention processes ORIGINAL input (not local's output)
        so it can do proper long-range retrieval without local interference.

        Uses alpha weights to blend contributions:
        - alpha_local: Weight for local attention (syntax, grammar)
        - alpha_phase: Weight for phase attention (long-range context)
        """
        residual = x

        # Local attention on original input (captures local patterns)
        x_local = self.local_attn(x, causal_mask)

        # Phase attention on ORIGINAL input (captures global context)
        # This is critical: phase needs raw input to do long-range retrieval
        x_phase = self.phase_attn(residual, causal_mask)

        # Weighted combination using learnable alphas
        # Normalize alphas to sum to 1 for stability
        alpha_sum = torch.abs(self.alpha_local) + torch.abs(self.alpha_phase) + 1e-8
        w_local = torch.abs(self.alpha_local) / alpha_sum
        w_phase = torch.abs(self.alpha_phase) / alpha_sum

        output = w_local * x_local + w_phase * x_phase

        return output


class HybridTransformerBlock(nn.Module):
    """Transformer block with hybrid local + phase attention."""

    def __init__(
        self,
        config: TransformerConfig,
        window_size: int = 256,
        local_backend: str = 'auto',
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
    ):
        super().__init__()
        self.attention = HybridAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            window_size=window_size,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            alpha_local=alpha_local,
            alpha_phase=alpha_phase,
            local_backend=local_backend,
            temperature=getattr(config, 'temperature', 1.0),  # Sharper attention
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


class LocalTransformerBlock(nn.Module):
    """Transformer block with local attention only (for early layers)."""

    def __init__(self, config: TransformerConfig, window_size: int = 256, backend: str = 'auto'):
        super().__init__()
        self.attention = LocalAttention(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            window_size=window_size,
            dropout=config.dropout,
            backend=backend,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# TRANSFORMER BLOCKS
# =============================================================================

class PhaseTransformerBlock(nn.Module):
    """Transformer block with O(n) phase attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        # V9.6.11: Use aux_scale=1.0 for pure phase model
        # In pure phase, there's no local attention to compete with
        # The 0.1 default was designed for hybrid mode auxiliary integration
        self.attention = PhaseAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
            sync_steps=config.sync_steps,
            sync_lr=config.sync_lr,
            temperature=getattr(config, 'temperature', 1.0),  # Sharper attention for classification
            aux_scale=1.0,  # V9.6.11: Full strength for pure phase model
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        phase_context: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Union[torch.Tensor, Tuple[torch.Tensor, Dict[str, torch.Tensor]]]:
        """Forward with optional streaming phase context."""
        if phase_context is not None:
            x, new_context = self.attention(x, causal_mask, phase_context)
            x = self.ff(x)
            return x, new_context
        else:
            x = self.attention(x, causal_mask)
            x = self.ff(x)
            return x


class StandardTransformerBlock(nn.Module):
    """Transformer block with O(n²) standard attention."""

    def __init__(self, config: TransformerConfig):
        super().__init__()
        self.attention = StandardAttentionLayer(
            embed_dim=config.embed_dim,
            num_heads=config.num_heads,
            dropout=config.dropout,
        )
        self.ff = FeedForward(
            embed_dim=config.embed_dim,
            ff_dim=config.ff_dim,
            dropout=config.dropout,
        )

    def forward(self, x: torch.Tensor, causal_mask: bool = True) -> torch.Tensor:
        x = self.attention(x, causal_mask)
        x = self.ff(x)
        return x


# =============================================================================
# FULL TRANSFORMERS
# =============================================================================

class PhaseTransformer(nn.Module):
    """
    General-Purpose O(n) Phase Transformer.

    Drop-in replacement for standard transformer with massive cost savings.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        temperature: float = 1.0,  # Lower = sharper attention (for classification)
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR to prevent embedding corruption
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
        )
        self.config = config
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            PhaseTransformerBlock(config) for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        # When tied, Sanskrit gradients corrupt the output decoder vocabulary space
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # State-centric training head (optional, for token-free training)
        self.state_delta_predictor = StateDeltaPredictor(
            embed_dim=embed_dim,
            hidden_dim=embed_dim * 2,
            dropout=dropout,
            num_layers=2,
        )

        # Gradient checkpointing (disabled by default)
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        """Enable gradient checkpointing to save memory at cost of speed."""
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing."""
        self.gradient_checkpointing = False

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward_hidden(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass returning hidden states BEFORE LM head.

        Use this for memory-efficient training with chunked LM head processing.
        For 5M+ context, calling lm_head on full hidden creates 1TB+ tensor.
        Instead, process lm_head in chunks during loss computation.

        Args:
            input_ids: [B, N] token indices

        Returns:
            hidden: [B, N, embed_dim] - final hidden states before LM head
        """
        B, N = input_ids.shape

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks
        for block in self.blocks:
            if self.gradient_checkpointing and self.training:
                x = checkpoint(
                    block,
                    x,
                    True,  # causal_mask
                    use_reentrant=False,
                )
            else:
                x = block(x, causal_mask=True)

        # Return normalized hidden states (before LM head)
        return self.norm(x)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
        phase_contexts: Optional[List[Dict[str, torch.Tensor]]] = None,
        position_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Forward pass with optional streaming phase context and layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head
            phase_contexts: List of phase contexts per layer for streaming (10M+ tokens)
            position_offset: Position offset for streaming (chunk start position)

        Returns:
            Dict with 'logits', optionally 'hidden_states', 'last_hidden_state',
            and 'phase_contexts' if streaming
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # Embeddings with position offset for streaming
        positions = torch.arange(position_offset, position_offset + N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Initialize phase contexts if streaming but none provided
        streaming = phase_contexts is not None
        if streaming and len(phase_contexts) == 0:
            phase_contexts = [{}] * len(self.blocks)

        # Transformer blocks
        hidden_states = [] if should_extract else None
        new_phase_contexts = []

        for i, block in enumerate(self.blocks):
            if streaming:
                # Streaming mode: pass and collect phase contexts
                layer_context = phase_contexts[i] if i < len(phase_contexts) else {}
                if self.gradient_checkpointing and self.training:
                    # Note: checkpointing with streaming requires special handling
                    x, new_ctx = block(x, causal_mask=True, phase_context=layer_context)
                else:
                    x, new_ctx = block(x, causal_mask=True, phase_context=layer_context)
                new_phase_contexts.append(new_ctx)
            else:
                # Normal mode
                if self.gradient_checkpointing and self.training:
                    x = checkpoint(
                        block,
                        x,
                        True,  # causal_mask
                        use_reentrant=False,
                    )
                else:
                    x = block(x, causal_mask=True)

            # Extract if: return_hidden=True (all), or layer in extract_layers
            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        if streaming:
            result['phase_contexts'] = new_phase_contexts

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop."""
        for _ in range(max_new_tokens):
            # Forward
            logits = self(input_ids)['logits'][:, -1, :]

            # Temperature
            logits = logits / temperature

            # Top-k
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')

            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            input_ids = torch.cat([input_ids, next_token], dim=1)

        return input_ids


class HybridPhaseTransformer(nn.Module):
    """
    Hybrid Phase Transformer with Local + Phase Attention.

    Architecture:
    - Early layers (1 to local_layers): Local attention only
    - Later layers: Hybrid (Local + Phase) attention

    This enables:
    - Fast learning of local patterns (syntax, grammar)
    - Efficient global context via Phase attention O(n)
    - Better PPL convergence than pure Phase attention
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        # Hybrid-specific params
        local_layers: int = 4,  # First N layers use local attention only
        window_size: int = 256,  # Local attention window
        local_backend: str = 'auto',  # LocalAttention backend: 'auto', 'flash', 'sdpa', 'unfold'
        alpha_local: float = 0.8,  # Weight for local attention in hybrid layers
        alpha_phase: float = 0.2,  # Weight for phase attention in hybrid layers
        temperature: float = 1.0,  # Lower = sharper attention (for classification)
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR to prevent embedding corruption
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
            sync_steps=sync_steps,
            sync_lr=sync_lr,
            temperature=temperature,  # Pass temperature for sharper attention
        )
        self.config = config
        self.local_layers = local_layers
        self.local_backend = local_backend
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks: Local (early) + Hybrid (later)
        self.blocks = nn.ModuleList()
        for i in range(num_layers):
            if i < local_layers:
                # Early layers: Local attention only (fast pattern learning)
                self.blocks.append(LocalTransformerBlock(
                    config, window_size=window_size, backend=local_backend))
            else:
                # Later layers: Hybrid Local + Phase attention
                self.blocks.append(HybridTransformerBlock(
                    config,
                    window_size=window_size,
                    local_backend=local_backend,
                    alpha_local=alpha_local,
                    alpha_phase=alpha_phase,
                ))

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        # When tied, Sanskrit gradients corrupt the output decoder vocabulary space
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # State-centric training head (optional, for token-free training)
        self.state_delta_predictor = StateDeltaPredictor(
            embed_dim=embed_dim,
            hidden_dim=embed_dim * 2,
            dropout=dropout,
            num_layers=2,
        )

        # Gradient checkpointing (disabled by default)
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        """Enable gradient checkpointing to save memory at cost of speed."""
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        """Disable gradient checkpointing."""
        self.gradient_checkpointing = False

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward_hidden(
        self,
        input_ids: torch.Tensor,
    ) -> torch.Tensor:
        """
        Forward pass returning hidden states BEFORE LM head.

        Use this for memory-efficient training with chunked LM head processing.
        For 5M+ context, calling lm_head on full hidden creates 1TB+ tensor.
        Instead, process lm_head in chunks during loss computation.

        Args:
            input_ids: [B, N] token indices

        Returns:
            hidden: [B, N, embed_dim] - final hidden states before LM head
        """
        B, N = input_ids.shape

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks
        for block in self.blocks:
            if self.gradient_checkpointing and self.training:
                x = checkpoint(
                    block,
                    x,
                    True,  # causal_mask
                    use_reentrant=False,
                )
            else:
                x = block(x, causal_mask=True)

        # Return normalized hidden states (before LM head)
        return self.norm(x)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Supports targeted hidden state extraction for inference components
        (EvolutionaryInferenceEngine, CSRInferenceGuard, SovereignScorer).

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states (legacy behavior)
            extract_layers: Specific layer indices to extract (0-indexed).
                           More memory-efficient than return_hidden=True.
                           Common patterns:
                           - [0, 11]: O1 (Potential) and O12 (Integration) for karma
                           - [0, 5, 11]: Authority sample + midpoint + final
                           - None with return_hidden=True: all layers
            return_last_hidden: Return normalized hidden state before lm_head.
                               Required for CSR re-projection after gating.

        Returns:
            Dict with:
            - 'logits': [B, N, V] output logits
            - 'hidden_states': List[Tensor] if return_hidden or extract_layers
            - 'last_hidden_state': [B, N, D] if return_last_hidden (post-norm)

        Note:
            Authority layers (0-8) capture "meaning" / ontological structure.
            Sensory layers (9-11) capture "expression" / output refinement.
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks with targeted extraction
        hidden_states = [] if should_extract else None
        for i, block in enumerate(self.blocks):
            if self.gradient_checkpointing and self.training:
                x = checkpoint(
                    block,
                    x,
                    True,  # causal_mask
                    use_reentrant=False,
                )
            else:
                x = block(x, causal_mask=True)

            # Extract if: return_hidden=True (all), or layer in extract_layers
            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop."""
        for _ in range(max_new_tokens):
            logits = self(input_ids)['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)
        return input_ids


class LocalOnlyTransformer(nn.Module):
    """
    Local-Only Transformer (Sliding Window Attention, NO Phase).

    Baseline model to test if Phase attention is helping or hurting.
    Uses only LocalTransformerBlock with sliding window attention O(n×w).
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        window_size: int = 256,
        local_backend: str = 'auto',
        # Unused but kept for compatibility with create_model()
        sync_steps: int = 3,
        sync_lr: float = 0.1,
        local_layers: int = 4,
        alpha_local: float = 0.8,
        alpha_phase: float = 0.2,
        temperature: float = 1.0,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.local_backend = local_backend
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # ALL layers use LocalTransformerBlock (NO Phase)
        self.blocks = nn.ModuleList([
            LocalTransformerBlock(config, window_size=window_size, backend=local_backend)
            for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        # Gradient checkpointing
        self.gradient_checkpointing = False

        # Initialize
        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def gradient_checkpointing_enable(self):
        self.gradient_checkpointing = True

    def gradient_checkpointing_disable(self):
        self.gradient_checkpointing = False

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head

        Returns:
            Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state'
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        # Embeddings
        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        # Transformer blocks (all local, no phase)
        hidden_states = [] if should_extract else None
        for i, block in enumerate(self.blocks):
            if self.gradient_checkpointing and self.training:
                x = checkpoint(block, x, True, use_reentrant=False)
            else:
                x = block(x, causal_mask=True)

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 50,
        temperature: float = 1.0,
        top_k: int = 50,
    ) -> torch.Tensor:
        """Simple generation loop."""
        for _ in range(max_new_tokens):
            logits = self(input_ids)['logits'][:, -1, :]
            logits = logits / temperature
            if top_k > 0:
                v, _ = torch.topk(logits, min(top_k, logits.size(-1)))
                logits[logits < v[:, [-1]]] = float('-inf')
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            input_ids = torch.cat([input_ids, next_token], dim=1)
        return input_ids


class StandardTransformer(nn.Module):
    """
    Standard O(n²) Transformer for comparison.

    Same architecture as PhaseTransformer but with standard attention.
    """

    def __init__(
        self,
        vocab_size: int = 50257,
        embed_dim: int = 768,
        num_layers: int = 12,
        num_heads: int = 12,
        ff_dim: Optional[int] = None,
        max_seq_len: int = 8192,
        dropout: float = 0.1,
        tie_embeddings: bool = True,  # V9.6.0: Set False when using Sanskrit/CSR
        **kwargs,  # Ignore phase-specific params
    ):
        super().__init__()

        config = TransformerConfig(
            vocab_size=vocab_size,
            embed_dim=embed_dim,
            num_layers=num_layers,
            num_heads=num_heads,
            ff_dim=ff_dim,
            max_seq_len=max_seq_len,
            dropout=dropout,
        )
        self.config = config
        self.tie_embeddings = tie_embeddings

        # Embeddings
        self.token_embed = nn.Embedding(vocab_size, embed_dim)
        self.pos_embed = nn.Embedding(max_seq_len, embed_dim)
        self.embed_dropout = nn.Dropout(dropout)

        # Transformer blocks
        self.blocks = nn.ModuleList([
            StandardTransformerBlock(config) for _ in range(num_layers)
        ])

        # Output
        self.norm = nn.LayerNorm(embed_dim)
        self.lm_head = nn.Linear(embed_dim, vocab_size, bias=False)

        # V9.6.0: Optionally tie weights (disable when using Sanskrit/CSR injection)
        if tie_embeddings:
            self.lm_head.weight = self.token_embed.weight

        self.apply(self._init_weights)

        # V9.6.10: For untied embeddings, copy token_embed to lm_head AFTER init
        # This provides semantic alignment at start while keeping them separate
        if not self.tie_embeddings:
            with torch.no_grad():
                self.lm_head.weight.copy_(self.token_embed.weight)

    def _init_weights(self, module):
        if isinstance(module, nn.Linear):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)
            if module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            torch.nn.init.normal_(module.weight, mean=0.0, std=0.02)

    def forward(
        self,
        input_ids: torch.Tensor,
        return_hidden: bool = False,
        extract_layers: Optional[List[int]] = None,
        return_last_hidden: bool = False,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass with efficient layer extraction.

        Args:
            input_ids: [B, N] token indices
            return_hidden: Return all hidden states
            extract_layers: Specific layer indices to extract (memory-efficient)
            return_last_hidden: Return normalized hidden state before lm_head

        Returns:
            Dict with 'logits' and optionally 'hidden_states', 'last_hidden_state'
        """
        B, N = input_ids.shape

        # Determine which layers to extract
        should_extract = return_hidden or extract_layers is not None
        extract_set = set(extract_layers) if extract_layers is not None else None

        positions = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.token_embed(input_ids) + self.pos_embed(positions)
        x = self.embed_dropout(x)

        hidden_states = [] if should_extract else None
        for i, block in enumerate(self.blocks):
            x = block(x, causal_mask=True)

            if should_extract:
                if extract_set is None or i in extract_set:
                    hidden_states.append(x)

        x = self.norm(x)
        logits = self.lm_head(x)

        result = {'logits': logits}

        if should_extract:
            result['hidden_states'] = hidden_states

        if return_last_hidden:
            result['last_hidden_state'] = x

        return result


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================

def count_parameters(model: nn.Module) -> int:
    """Count trainable parameters."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def measure_inference_time(
    model: nn.Module,
    input_ids: torch.Tensor,
    num_runs: int = 10,
    warmup: int = 3,
) -> float:
    """Measure average inference time in milliseconds."""
    device = next(model.parameters()).device

    # Warmup
    with torch.no_grad():
        for _ in range(warmup):
            _ = model(input_ids)

    if device.type == 'cuda':
        torch.cuda.synchronize()

    # Timed runs
    start = time.time()
    with torch.no_grad():
        for _ in range(num_runs):
            _ = model(input_ids)

    if device.type == 'cuda':
        torch.cuda.synchronize()

    return (time.time() - start) / num_runs * 1000  # ms


def compare_models(
    phase_model: PhaseTransformer,
    std_model: StandardTransformer,
    seq_lengths: List[int] = [256, 512, 1024, 2048],
    batch_size: int = 4,
    device: Optional[torch.device] = None,
) -> Dict[str, Any]:
    """
    Compare Phase Transformer vs Standard Transformer.

    Returns detailed comparison metrics.
    """
    if device is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    phase_model = phase_model.to(device).eval()
    std_model = std_model.to(device).eval()

    results = {
        'device': str(device),
        'phase_params': count_parameters(phase_model),
        'std_params': count_parameters(std_model),
        'timings': [],
    }

    print("\n" + "=" * 70)
    print("  PHASE TRANSFORMER vs STANDARD TRANSFORMER")
    print("=" * 70)
    print(f"\n  Device: {device}")
    print(f"  Phase params: {results['phase_params']:,}")
    print(f"  Standard params: {results['std_params']:,}")
    print(f"\n  {'SeqLen':<10} {'Standard':<15} {'Phase':<15} {'Speedup':<10} {'Savings':<10}")
    print(f"  {'-'*60}")

    for seq_len in seq_lengths:
        input_ids = torch.randint(0, 1000, (batch_size, seq_len), device=device)

        std_time = measure_inference_time(std_model, input_ids)
        phase_time = measure_inference_time(phase_model, input_ids)

        speedup = std_time / phase_time if phase_time > 0 else 0
        savings = (std_time - phase_time) / std_time * 100 if std_time > 0 else 0

        results['timings'].append({
            'seq_len': seq_len,
            'std_time_ms': std_time,
            'phase_time_ms': phase_time,
            'speedup': speedup,
            'savings_pct': savings,
        })

        print(f"  {seq_len:<10} {std_time:<15.2f}ms {phase_time:<15.2f}ms {speedup:<10.1f}x {savings:<10.1f}%")

    # Verify outputs are valid
    print("\n  Output Validation:")
    input_ids = torch.randint(0, 1000, (2, 128), device=device)

    with torch.no_grad():
        phase_out = phase_model(input_ids)['logits']
        std_out = std_model(input_ids)['logits']

    phase_valid = not (torch.isnan(phase_out).any() or torch.isinf(phase_out).any())
    std_valid = not (torch.isnan(std_out).any() or torch.isinf(std_out).any())

    print(f"    Phase output valid: {'✓' if phase_valid else '✗'}")
    print(f"    Standard output valid: {'✓' if std_valid else '✗'}")

    results['phase_valid'] = phase_valid
    results['std_valid'] = std_valid

    # Summary
    avg_speedup = sum(t['speedup'] for t in results['timings']) / len(results['timings'])
    print(f"\n  Average Speedup: {avg_speedup:.1f}x")
    print("=" * 70)

    results['avg_speedup'] = avg_speedup

    return results


def quick_test():
    """Quick validation test."""
    print("\nQuick Test: Phase Transformer")
    print("-" * 40)

    # Small model for quick test
    model = PhaseTransformer(
        vocab_size=1000,
        embed_dim=128,
        num_layers=2,
        num_heads=4,
    )

    print(f"Parameters: {count_parameters(model):,}")

    # Forward pass
    input_ids = torch.randint(0, 1000, (2, 32))
    output = model(input_ids)

    print(f"Input shape: {input_ids.shape}")
    print(f"Output shape: {output['logits'].shape}")
    print(f"Output valid: {not torch.isnan(output['logits']).any()}")

    # Backward pass
    loss = output['logits'].mean()
    loss.backward()

    # Check gradients: pass if at least some gradients exist and none are NaN/Inf
    has_any_grad = False
    grads_ok = True
    for p in model.parameters():
        if p.requires_grad and p.grad is not None:
            has_any_grad = True
            if torch.isnan(p.grad).any() or torch.isinf(p.grad).any():
                grads_ok = False
                break
    grads_ok = grads_ok and has_any_grad
    print(f"Gradients valid: {grads_ok}")

    print("-" * 40)
    return grads_ok


def long_context_benchmark(max_seq_len: int = 32768, batch_size: int = 1):
    """
    Benchmark Phase Transformer at long context lengths up to 32K tokens.

    This validates the O(n) scaling advantage at production-scale contexts.
    Tests will automatically reduce sequence length if memory is insufficient.
    """
    print("\n" + "=" * 70)
    print("  LONG CONTEXT BENCHMARK (up to 32K tokens)")
    print("=" * 70)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\n  Device: {device}")

    # Smaller model for long context testing (to fit in memory)
    phase_model = PhaseTransformer(
        vocab_size=10000,
        embed_dim=128,  # Smaller for memory
        num_layers=2,
        num_heads=4,
    ).to(device).eval()

    std_model = StandardTransformer(
        vocab_size=10000,
        embed_dim=128,
        num_layers=2,
        num_heads=4,
    ).to(device).eval()

    print(f"  Model: embed_dim=128, layers=2, heads=4")
    print(f"  Phase params: {count_parameters(phase_model):,}")
    print(f"  Standard params: {count_parameters(std_model):,}")

    # Test sequence lengths: 512, 1K, 2K, 4K, 8K, 16K, 32K
    seq_lengths = [512, 1024, 2048, 4096, 8192, 16384, 32768]
    seq_lengths = [s for s in seq_lengths if s <= max_seq_len]

    print(f"\n  {'SeqLen':<10} {'Standard':<15} {'Phase':<15} {'Speedup':<12} {'Status'}")
    print(f"  {'-'*65}")

    results = []
    baseline_std = None
    baseline_phase = None

    for seq_len in seq_lengths:
        try:
            input_ids = torch.randint(0, 1000, (batch_size, seq_len), device=device)

            # Measure standard transformer
            try:
                std_time = measure_inference_time(std_model, input_ids, num_runs=3)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    std_time = float('inf')
                    if device.type == 'cuda':
                        torch.cuda.empty_cache()
                else:
                    raise

            # Measure phase transformer
            try:
                phase_time = measure_inference_time(phase_model, input_ids, num_runs=3)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    phase_time = float('inf')
                    if device.type == 'cuda':
                        torch.cuda.empty_cache()
                else:
                    raise

            # Store baseline for scaling analysis
            if baseline_std is None and std_time != float('inf'):
                baseline_std = std_time
                baseline_phase = phase_time

            # Calculate speedup
            if std_time == float('inf') and phase_time == float('inf'):
                speedup_str = "Both OOM"
                status = "⚠"
            elif std_time == float('inf'):
                speedup_str = "Std OOM"
                status = "✓ Phase only"
            elif phase_time == float('inf'):
                speedup_str = "Phase OOM"
                status = "⚠"
            else:
                speedup = std_time / phase_time
                speedup_str = f"{speedup:.1f}x"
                status = "✓"

            # Format times
            std_str = f"{std_time:.1f}ms" if std_time != float('inf') else "OOM"
            phase_str = f"{phase_time:.1f}ms" if phase_time != float('inf') else "OOM"

            print(f"  {seq_len:<10} {std_str:<15} {phase_str:<15} {speedup_str:<12} {status}")

            results.append({
                'seq_len': seq_len,
                'std_time': std_time,
                'phase_time': phase_time,
            })

            # Clean up
            del input_ids
            if device.type == 'cuda':
                torch.cuda.empty_cache()

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print(f"  {seq_len:<10} {'OOM':<15} {'OOM':<15} {'---':<12} ⚠ Memory limit")
                if device.type == 'cuda':
                    torch.cuda.empty_cache()
                break
            else:
                raise

    # Scaling analysis
    print(f"\n  Scaling Analysis:")
    valid_results = [r for r in results if r['std_time'] != float('inf') and r['phase_time'] != float('inf')]

    if len(valid_results) >= 2:
        # Calculate scaling factor (time increase per 2x sequence length)
        std_scaling = []
        phase_scaling = []

        for i in range(1, len(valid_results)):
            if valid_results[i]['seq_len'] == 2 * valid_results[i-1]['seq_len']:
                std_scaling.append(valid_results[i]['std_time'] / valid_results[i-1]['std_time'])
                phase_scaling.append(valid_results[i]['phase_time'] / valid_results[i-1]['phase_time'])

        if std_scaling:
            avg_std_scaling = sum(std_scaling) / len(std_scaling)
            avg_phase_scaling = sum(phase_scaling) / len(phase_scaling)

            print(f"    Standard: ~{avg_std_scaling:.1f}x per 2x seq_len (O(n²) expects ~4x)")
            print(f"    Phase:    ~{avg_phase_scaling:.1f}x per 2x seq_len (O(n) expects ~2x)")

            if avg_phase_scaling < avg_std_scaling:
                print(f"    ✓ Phase scales {avg_std_scaling/avg_phase_scaling:.1f}x better than standard")

    # Maximum context achieved
    max_std = max([r['seq_len'] for r in results if r['std_time'] != float('inf')], default=0)
    max_phase = max([r['seq_len'] for r in results if r['phase_time'] != float('inf')], default=0)

    print(f"\n  Maximum Context Achieved:")
    print(f"    Standard Transformer: {max_std:,} tokens")
    print(f"    Phase Transformer:    {max_phase:,} tokens")

    if max_phase > max_std:
        print(f"    ✓ Phase handles {max_phase/max_std:.1f}x longer context!")

    print("=" * 70)

    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import sys

    # Check for command-line arguments
    run_long_context = "--long" in sys.argv or "--32k" in sys.argv
    max_seq = 32768
    if "--16k" in sys.argv:
        max_seq = 16384
    elif "--8k" in sys.argv:
        max_seq = 8192

    # Quick validation
    success = quick_test()

    if success:
        print("\n✓ Quick test passed!")

        # Full comparison (if resources available)
        try:
            phase_model = PhaseTransformer(
                vocab_size=50257,
                embed_dim=256,
                num_layers=4,
                num_heads=8,
            )

            std_model = StandardTransformer(
                vocab_size=50257,
                embed_dim=256,
                num_layers=4,
                num_heads=8,
            )

            results = compare_models(
                phase_model,
                std_model,
                seq_lengths=[128, 256, 512, 1024],
                batch_size=2,
            )

            print(f"\n✓ Comparison complete! Average speedup: {results['avg_speedup']:.1f}x")

        except RuntimeError as e:
            if "out of memory" in str(e).lower():
                print("\n⚠ Not enough memory for full comparison")
            else:
                raise

        # Long context benchmark (optional)
        if run_long_context:
            print("\n" + "=" * 70)
            print("  Running Long Context Benchmark...")
            print("  (This may take a while and use significant memory)")
            print("=" * 70)
            try:
                long_context_benchmark(max_seq_len=max_seq)
            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    print("\n⚠ Out of memory during long context benchmark")
                else:
                    raise
        else:
            print("\n  Tip: Run with --long or --32k for long context benchmark (up to 32K tokens)")
            print("       Use --16k or --8k for smaller benchmarks")

    else:
        print("\n✗ Quick test failed!")

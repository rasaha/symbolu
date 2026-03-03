"""
Protected Phase architecture: Phase accumulates, Quad queries.

No gradient competition - Phase and Quad collaborate sequentially.
Also includes HardProbeTransformer (the main benchmark model).

Contains:
    - ProtectedPhaseAttention: Phase state accumulation
    - ProtectedQuadAttention: Quad as query-only
    - ProtectedPhaseBlock: Sequential Phase -> Memory -> Quad
    - ProtectedPhaseTransformer: Full protected model
    - HardProbeTransformer: Configurable attn type benchmark model

CLI Usage::

    python train_hard_probes.py --protected-phase
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Dict, Optional

# =============================================================================
# PROTECTED PHASE ARCHITECTURE (v5)
# =============================================================================
# Evidence shows Phase becomes DECORATIVE when mixed with Quadratic.
# Solution: Give Phase and Quadratic EXCLUSIVE, NON-COMPETING roles.
#
# Architecture:
#   Phase:     memory_state = cumsum(keys * values)  # Accumulate bindings
#   Quadratic: output = attention(query, memory_state)  # Query the memory
#
# This is NOT mixing - it's COLLABORATION:
#   - Phase has exclusive control over state accumulation
#   - Quadratic has exclusive control over state querying
#   - They don't compete for the same gradient signal
# =============================================================================

class ProtectedPhaseAttention(nn.Module):
    """
    Phase attention that outputs a MEMORY STATE for Quadratic to query.

    Unlike regular PhaseAttention which outputs attention-weighted values,
    this outputs the raw cumsum state that Quadratic can query.

    Phase's exclusive job: Accumulate key-value pairs into persistent state.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        # Phase projections for keys
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)

        # Operation-conditioned phase offsets
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self.dropout = nn.Dropout(dropout)
        self._ablation_mode = "none"
        self._rotation_angle = 0.0  # For rotation test (applied to phi_k)

        # Health tracking: R_k (amplitude) statistics
        self._last_r_k_mean = 0.0
        self._last_r_k_std = 0.0
        self._last_r_k_min = 0.0
        self._last_r_k_max = 0.0

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_k.

        For Protected Phase, we rotate φ_k (not φ_q) because:
        - Protected Phase uses φ_k for memory accumulation (cumsum)
        - There is no φ_q in this architecture (Quadratic handles queries)

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded in keys, rotating φ_k should disrupt retrieval
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def get_health_metrics(self) -> dict:
        """Return Phase health metrics (R_k statistics)."""
        return {
            "r_k_mean": self._last_r_k_mean,
            "r_k_std": self._last_r_k_std,
            "r_k_min": self._last_r_k_min,
            "r_k_max": self._last_r_k_max,
        }

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        """
        Compute Phase memory state via cumsum.

        Returns: memory_state [B, N, D] - the accumulated state for Quadratic to query
        """
        B, N, D = x.shape

        # Compute phase projection for keys
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_k = phi_k_raw

        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        # Track R_k health metrics (amplitude statistics)
        with torch.no_grad():
            self._last_r_k_mean = a_k.mean().item()
            self._last_r_k_std = a_k.std().item()
            self._last_r_k_min = a_k.min().item()
            self._last_r_k_max = a_k.max().item()

        # Apply operation-conditioned phase shifts
        if self.op_phase_shifts is not None and token_ids is not None:
            for tok_id, op_idx in self.op_to_idx.items():
                mask = (token_ids == tok_id).float().unsqueeze(-1).unsqueeze(-1)
                mask = mask.expand(B, N, self.num_heads, self.head_dim)
                shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
                phi_k = phi_k + mask * shift

        # Ablation
        if self._ablation_mode == "scramble":
            torch.manual_seed(self._scramble_seed)
            for b in range(B):
                for h in range(self.num_heads):
                    perm = torch.randperm(N, device=phi_k.device)
                    phi_k[b, :, h, :] = phi_k[b, perm, h, :]
        elif self._ablation_mode in ["freeze", "off"]:
            phi_k = torch.zeros_like(phi_k)

        # Apply rotation to φ_k (tests phase selectivity for Protected Phase)
        # Note: We rotate φ_k here because Protected Phase has no φ_q
        if self._rotation_angle != 0.0:
            phi_k = phi_k + self._rotation_angle

        # Compute complex phasor and accumulate via cumsum
        dtype = phi_k.dtype
        if dtype == torch.bfloat16:
            phi_k, a_k, v = phi_k.float(), a_k.float(), v.float()

        k_phasor = torch.polar(a_k, -phi_k)
        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex

        # CUMSUM: This is Phase's exclusive job - accumulate state
        memory_state = torch.cumsum(kv, dim=1)

        # Return real part as memory state for Quadratic to query
        memory_state = memory_state.real

        if dtype == torch.bfloat16:
            memory_state = memory_state.to(dtype)

        return memory_state.reshape(B, N, D)


class ProtectedQuadAttention(nn.Module):
    """
    Quadratic attention that QUERIES a memory state (from Phase).

    Unlike regular QuadraticAttention which computes K,V from input,
    this uses the Phase memory state as keys/values.

    Quadratic's exclusive job: Query the Phase-accumulated memory.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        # Query projection (from input)
        self.W_q = nn.Linear(d_model, d_model)
        # Key/Value projections (from memory state)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor, memory_state: torch.Tensor) -> torch.Tensor:
        """
        Query the Phase memory state.

        Args:
            x: Input tensor [B, N, D] - used for queries
            memory_state: Phase memory [B, N, D] - used for keys/values
        """
        B, N, D = x.shape

        # Queries from input
        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        # Keys and Values from Phase memory state
        K = self.W_k(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(memory_state).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        # Standard attention over memory
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)


class ProtectedPhaseBlock(nn.Module):
    """
    Block with PROTECTED Phase and Quadratic roles.

    Architecture:
        1. Phase accumulates memory: memory = cumsum(k * v)
        2. Quadratic queries memory: output = attention(q, memory)

    This is SEQUENTIAL COLLABORATION, not parallel mixing.
    Phase and Quadratic don't compete for gradients.
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)
        self.norm_mem = nn.LayerNorm(d_model)

        # Protected Phase: accumulates memory state
        self.phase_memory = ProtectedPhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase)
        # Protected Quad: queries memory state
        self.quad_query = ProtectedQuadAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Step 1: Phase accumulates memory state (Phase's exclusive job)
        normed = self.norm1(x)
        memory_state = self.phase_memory(normed, token_ids)
        memory_state = self.norm_mem(memory_state)

        # Step 2: Quadratic queries the memory (Quad's exclusive job)
        attn_out = self.quad_query(normed, memory_state)

        # Residual and FF
        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase component."""
        self.phase_memory.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase component (applied to φ_k)."""
        self.phase_memory.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase component."""
        self.phase_memory.clear_rotation()


class ProtectedPhaseTransformer(nn.Module):
    """
    Transformer with PROTECTED Phase architecture.

    Key insight from ablation tests:
    - When mixed, Phase becomes DECORATIVE (0% ablation drop)
    - When alone, Phase is ESSENTIAL (37% ablation drop)

    Solution: Give Phase and Quadratic NON-COMPETING roles:
    - Phase: O(n) memory accumulation (cumsum)
    - Quadratic: O(n²) memory querying (attention)

    They collaborate sequentially, not compete in parallel.
    """

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
    ):
        super().__init__()
        self.operation_tokens = operation_tokens

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            ProtectedPhaseBlock(d_model, num_heads, d_ff, dropout, operation_tokens, bounded_phase)
            for _ in range(num_layers)
        ])

        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        for layer in self.layers:
            x = layer(x, input_ids)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for all Phase components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """
        Set rotation angle for all Phase components (applied to φ_k).

        Note: ProtectedPhaseTransformer uses φ_k only (for memory accumulation),
        not φ_q. So we rotate φ_k to test whether phase encodes relational structure.

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase components."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics (placeholder for compatibility)."""
        pass

    def get_phase_health(self) -> dict:
        """
        Aggregate Phase health metrics (R_k statistics) from all layers.

        Interpretation:
        - R_k → 0: Phase collapsed (bad)
        - R_k → 1: Phase degenerate (bad)
        - R_k stable in (0.3, 0.7): Healthy
        """
        metrics = {
            "r_k_mean": [],
            "r_k_std": [],
            "r_k_min": [],
            "r_k_max": [],
        }
        for layer in self.layers:
            layer_metrics = layer.phase_memory.get_health_metrics()
            for k, v in layer_metrics.items():
                metrics[k].append(v)

        # Average across layers
        return {
            "r_k_mean": sum(metrics["r_k_mean"]) / len(metrics["r_k_mean"]) if metrics["r_k_mean"] else 0.0,
            "r_k_std": sum(metrics["r_k_std"]) / len(metrics["r_k_std"]) if metrics["r_k_std"] else 0.0,
            "r_k_min": min(metrics["r_k_min"]) if metrics["r_k_min"] else 0.0,
            "r_k_max": max(metrics["r_k_max"]) if metrics["r_k_max"] else 0.0,
        }

    def get_R_k(self) -> float:
        """Get mean R_k metric for backward compatibility."""
        return self.get_phase_health()["r_k_mean"]

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class HardProbeTransformer(nn.Module):
    """Transformer for hard probe classification with operation-conditioned phase shifts."""

    def __init__(
        self,
        vocab_size: int,
        d_model: int,
        num_heads: int,
        num_layers: int,
        d_ff: int,
        dropout: float,
        max_seq_len: int,
        num_classes: int,
        use_phase: bool,
        extra_ff_per_layer: int = 0,  # For parameter matching
        operation_tokens: List[int] = None,  # Tokens that trigger phase shifts
        bounded_phase: bool = True,  # V9.9.11: Constrain φ to [-π, π] via π*sin()
        dual_channel_mode: bool = False,  # V10.3.8: Separate content/intent
        alignment_authority: float = 0.1,  # V10.3.8: α weight for alignment
    ):
        super().__init__()
        self.use_phase = use_phase
        self.operation_tokens = operation_tokens
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)
        self.layers = nn.ModuleList([
            TransformerBlock(d_model, num_heads, d_ff, dropout, use_phase,
                           extra_ff_per_layer, operation_tokens, bounded_phase,
                           dual_channel_mode, alignment_authority)
            for _ in range(num_layers)
        ])
        self.norm = nn.LayerNorm(d_model)
        self.classifier = nn.Linear(d_model, num_classes)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        B, N = input_ids.shape
        pos = torch.arange(N, device=input_ids.device).unsqueeze(0)
        x = self.dropout(self.token_emb(input_ids) + self.pos_emb(pos))

        # Pass input_ids to layers for operation-conditioned phase shifts
        for layer in self.layers:
            x = layer(x, input_ids if self.use_phase else None)

        return self.classifier(self.norm(x[:, -1, :]))

    def set_ablation(self, mode: str, seed: int = 42):
        for layer in self.layers:
            if hasattr(layer.attn, 'set_ablation'):
                layer.attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'set_rotation'):
                layer.attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            if hasattr(layer.attn, 'clear_rotation'):
                layer.attn.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        for layer in self.layers:
            if hasattr(layer.attn, 'capture_diagnostics'):
                layer.attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        r_values = []
        for layer in self.layers:
            if hasattr(layer.attn, 'get_R_k'):
                r_values.append(layer.attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


def compute_param_diff(d_model: int, num_heads: int, num_layers: int) -> int:
    """
    Compute parameter difference between Phase and Quadratic attention.

    Phase has extra W_q_phase, W_k_phase, W_q_amp, W_k_amp projections.
    Quadratic has W_q, W_k, W_v.

    Difference per layer = 2 * d_model^2 (two extra projections)
    """
    # Phase: W_q_phase, W_k_phase, W_q_amp, W_k_amp, W_v, out_proj = 6
    # Quadratic: W_q, W_k, W_v, out_proj = 4
    # Difference: 2 projections per layer
    extra_per_layer = 2 * d_model * d_model
    return extra_per_layer * num_layers


# =============================================================================
# EVALUATION
# =============================================================================

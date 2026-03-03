"""
QuadraticAttention and PhaseAttention mechanisms.

QuadraticAttention: Standard O(n^2) softmax attention.
PhaseAttention: Phase-based O(n) attention with cumulative state.

CLI Usage::

    # Run comparison between Quadratic and Phase
    python train_hard_probes.py

    # Enable bounded phase (constrain phi to [-pi, pi])
    python train_hard_probes.py --bounded-phase

    # Enable dual-channel attention
    python train_hard_probes.py --dual-channel-mode --alignment-authority 0.1
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple, Dict, List, Optional

from .contracts import assert_control_shape, validate_intent_phase_shapes

# =============================================================================
# MODELS
# =============================================================================

class QuadraticAttention(nn.Module):
    """Standard O(n^2) attention."""

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.scale = math.sqrt(self.head_dim)

        self.W_q = nn.Linear(d_model, d_model)
        self.W_k = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        B, N, D = x.shape

        Q = self.W_q(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        K = self.W_k(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)
        V = self.W_v(x).view(B, N, self.num_heads, self.head_dim).transpose(1, 2)

        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale

        # Causal mask
        mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))

        attn = F.softmax(scores, dim=-1)
        attn = self.dropout(attn)

        out = torch.matmul(attn, V)
        out = out.transpose(1, 2).contiguous().view(B, N, D)

        return self.out_proj(out)

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class PhaseAttention(nn.Module):
    """
    O(n) phasor attention with operation-conditioned phase offsets.

    KEY ENHANCEMENT: Operation tokens (NEG, PERMUTE, OVERWRITE) add learned
    phase shifts before the cumsum. This allows operations to be true STATE
    TRANSFORMATIONS rather than passive symbols.

    WHY THIS MATTERS:
    -----------------
    Without operation-conditioned offsets, operations like NEG are just tokens
    that the model must learn to interpret through content-based attention.
    With offsets, operations directly transform the phase state, which is how
    Phase is hypothesized to encode relational structure.

    This is NOT cheating - it tests the hypothesis more faithfully by making
    operations act as they're theoretically supposed to.
    """

    def __init__(self, d_model: int, num_heads: int, dropout: float = 0.1,
                 operation_tokens: List[int] = None, bounded_phase: bool = True,
                 dual_channel_mode: bool = False, alignment_authority: float = 0.1):
        super().__init__()
        self.d_model = d_model
        self.num_heads = num_heads
        self.head_dim = d_model // num_heads
        self.bounded_phase = bounded_phase  # V9.9.11: Constrain φ to [-π, π] via π*sin()

        # V10.3.8: Dual-Channel Attention
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        self.W_q_phase = nn.Linear(d_model, d_model)
        self.W_k_phase = nn.Linear(d_model, d_model)
        self.W_q_amp = nn.Linear(d_model, d_model)
        self.W_k_amp = nn.Linear(d_model, d_model)
        self.W_v = nn.Linear(d_model, d_model)
        self.out_proj = nn.Linear(d_model, d_model)
        self.dropout = nn.Dropout(dropout)

        # Operation-conditioned phase offsets
        # Each operation token gets a learned phase shift per head
        self.operation_tokens = operation_tokens or []
        if self.operation_tokens:
            # Map operation token IDs to indices 0, 1, 2, ...
            self.op_to_idx = {tok: i for i, tok in enumerate(self.operation_tokens)}
            # Learned phase shifts: [num_ops, num_heads, head_dim]
            self.op_phase_shifts = nn.Parameter(
                torch.randn(len(self.operation_tokens), num_heads, self.head_dim) * 0.1
            )
        else:
            self.op_to_idx = {}
            self.op_phase_shifts = None

        self._ablation_mode = "none"
        self._scramble_seed = 42
        self.capture_diagnostics = False
        self._phi_k = None
        self._phi_q = None

        # Rotation test: add a global phase rotation to φ_q
        self._rotation_angle = 0.0  # in radians

        # V10.3.8: Intent phase storage for dual-channel diagnostics
        self._intent_phase_query = None  # θ_JEPA
        self._intent_phase_key = None    # θ_SRK

    def set_ablation(self, mode: str, seed: int = 42):
        self._ablation_mode = mode
        self._scramble_seed = seed

    def set_rotation(self, angle_radians: float):
        """
        Set a global phase rotation to apply to φ_q.

        This tests whether phase encodes relational structure:
        - If roles are phase-encoded, rotating φ_q should shift which bindings are retrieved
        - If phase is decorative, rotation should have minimal effect

        Args:
            angle_radians: Rotation angle in radians (e.g., π/4 = 45°)
        """
        self._rotation_angle = angle_radians

    def clear_rotation(self):
        """Clear any applied rotation."""
        self._rotation_angle = 0.0

    def _ablate(self, phi: torch.Tensor) -> torch.Tensor:
        if self._ablation_mode == "none":
            return phi
        elif self._ablation_mode == "scramble":
            B, N, H, D = phi.shape
            torch.manual_seed(self._scramble_seed)
            result = phi.clone()
            for b in range(B):
                for h in range(H):
                    perm = torch.randperm(N, device=phi.device)
                    result[b, :, h, :] = phi[b, perm, h, :]
            return result
        elif self._ablation_mode in ["freeze", "off"]:
            return torch.zeros_like(phi)
        return phi

    def _apply_operation_phase_shifts(self, phi_k: torch.Tensor,
                                       token_ids: torch.Tensor) -> torch.Tensor:
        """
        Apply learned phase shifts for operation tokens.

        When NEG, PERMUTE, or OVERWRITE appears, add its learned phase shift
        to phi_k at that position. This transforms the state before cumsum.
        """
        if self.op_phase_shifts is None or token_ids is None:
            return phi_k

        B, N, H, D = phi_k.shape

        # Create mask for each operation type and apply its phase shift
        for tok_id, op_idx in self.op_to_idx.items():
            # Mask: [B, N] where operation token appears
            mask = (token_ids == tok_id).float()  # [B, N]
            # Expand mask to [B, N, H, D]
            mask = mask.unsqueeze(-1).unsqueeze(-1).expand(B, N, H, D)
            # Get phase shift for this operation: [H, D] -> [1, 1, H, D]
            shift = self.op_phase_shifts[op_idx].unsqueeze(0).unsqueeze(0)
            # Apply: add shift where operation token appears
            phi_k = phi_k + mask * shift

        return phi_k

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None,
                intent_phase_query: torch.Tensor = None,
                intent_phase_key: torch.Tensor = None) -> torch.Tensor:
        """
        Forward pass with optional operation-conditioned phase shifts.

        Args:
            x: Input tensor [B, N, D]
            token_ids: Token IDs [B, N] for operation-conditioned phase shifts
            intent_phase_query: V10.3.8 - θ_JEPA from Sensor (optional)
            intent_phase_key: V10.3.8 - θ_SRK from Master (optional)
        """
        B, N, D = x.shape

        # Compute phase projections
        phi_q_raw = self.W_q_phase(x).view(B, N, self.num_heads, self.head_dim)
        phi_k_raw = self.W_k_phase(x).view(B, N, self.num_heads, self.head_dim)

        # V9.9.11: Bounded phase parameterization (constrain φ to [-π, π] via π*sin())
        if self.bounded_phase:
            phi_q = math.pi * torch.sin(phi_q_raw)
            phi_k = math.pi * torch.sin(phi_k_raw)
        else:
            phi_q = phi_q_raw
            phi_k = phi_k_raw

        # Apply operation-conditioned phase shifts BEFORE ablation
        phi_k = self._apply_operation_phase_shifts(phi_k, token_ids)

        phi_q = self._ablate(phi_q)
        phi_k = self._ablate(phi_k)

        # Apply rotation to φ_q (tests phase selectivity)
        if self._rotation_angle != 0.0:
            phi_q = phi_q + self._rotation_angle

        # V10.3.8: Store intent phases for diagnostics
        self._intent_phase_query = intent_phase_query
        self._intent_phase_key = intent_phase_key

        if self.capture_diagnostics:
            self._phi_k = phi_k.detach()
            self._phi_q = phi_q.detach()

        a_q = torch.sigmoid(self.W_q_amp(x)).view(B, N, self.num_heads, self.head_dim)
        a_k = torch.sigmoid(self.W_k_amp(x)).view(B, N, self.num_heads, self.head_dim)
        v = self.W_v(x).view(B, N, self.num_heads, self.head_dim)

        dtype = phi_q.dtype
        if dtype == torch.bfloat16:
            phi_q, phi_k, a_q, a_k, v = [t.float() for t in [phi_q, phi_k, a_q, a_k, v]]

        q_phasor = torch.polar(a_q, phi_q)
        k_phasor = torch.polar(a_k, -phi_k)

        v_complex = torch.complex(v, torch.zeros_like(v))
        kv = k_phasor * v_complex
        state = torch.cumsum(kv, dim=1)

        output = (q_phasor * state).real

        # V10.3.8: Dual-Channel Alignment Modulation
        # If dual_channel_mode is enabled and we have intent phases,
        # modulate the content score by the alignment term:
        #   output = output * (1 + α * s_align)
        # where s_align = cos(θ_JEPA - θ_SRK)
        if self.dual_channel_mode and (intent_phase_query is not None or intent_phase_key is not None):
            # Normalize intent_phase shapes
            def _norm_intent(ip):
                if ip is None:
                    return None
                if ip.dim() == 2:
                    return ip.unsqueeze(1).unsqueeze(-1)  # [B, H] → [B, 1, H, 1]
                elif ip.dim() == 3:
                    return ip.unsqueeze(1)  # [B, H, D_h] → [B, 1, H, D_h]
                return ip

            theta_jepa = _norm_intent(intent_phase_query)
            theta_srk = _norm_intent(intent_phase_key)

            if theta_jepa is not None and theta_srk is not None:
                theta_diff = theta_jepa - theta_srk
            elif theta_jepa is not None:
                theta_diff = theta_jepa
            else:
                theta_diff = theta_srk

            # s_align = cos(θ_JEPA - θ_SRK)
            s_align = torch.cos(theta_diff.float())

            # V10.6.2: No-Write Contract validation
            # s_align should be broadcastable control, not full embedding tensor
            # Note: In PhaseAttention, s_align may be [B, 1, H, D_h] which is
            # per-head control (valid) as long as it's not [B, N, D] token-wise embeddings
            assert_control_shape(
                s_align,
                name="s_align (PhaseAttention alignment)",
                d_model=self.d_model,
                seq_len=N,  # Must not have full sequence dimension
                strict=True,
            )

            # Modulate: output = output * (1 + α * s_align)
            alignment_modulator = 1.0 + self.alignment_authority * s_align
            output = output * alignment_modulator

        if dtype == torch.bfloat16:
            output = output.to(dtype)

        output = output.reshape(B, N, D)
        return self.out_proj(self.dropout(output))

    def get_R_k(self) -> float:
        """Mean resultant length (phase health metric)."""
        if self._phi_k is None:
            return 0.0
        z = torch.exp(1j * self._phi_k.float())
        return torch.abs(z.mean()).item()

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters())


class TransformerBlock(nn.Module):

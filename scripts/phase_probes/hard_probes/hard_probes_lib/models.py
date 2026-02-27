"""
Transformer blocks and composite model architectures.

Contains:
    - TransformerBlock: Standard attention + FFN block
    - HybridTransformerBlock: Blends Phase + Quad with configurable ratios
    - HybridTransformer: Full model with inverted curriculum
    - HardProbeTransformer: Main benchmark model

CLI Usage::

    # Compare curricula (inverted vs standard)
    python train_hard_probes.py --compare-curricula

    # Custom curriculum ratio per layer
    python train_hard_probes.py --run-hybrid --curriculum 0.9,0.7,0.3,0.1
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Optional

class TransformerBlock(nn.Module):
    def __init__(self, d_model: int, num_heads: int, d_ff: int, dropout: float,
                 use_phase: bool, extra_ff: int = 0, operation_tokens: List[int] = None,
                 bounded_phase: bool = True, dual_channel_mode: bool = False,
                 alignment_authority: float = 0.1):
        super().__init__()
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # PhaseAttention gets operation_tokens for conditioned phase shifts
        if use_phase:
            self.attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase,
                                       dual_channel_mode, alignment_authority)
        else:
            self.attn = QuadraticAttention(d_model, num_heads, dropout)

        # Extra FF parameters for matching (added to quadratic when match_params=True)
        actual_d_ff = d_ff + extra_ff
        self.ff = nn.Sequential(
            nn.Linear(d_model, actual_d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(actual_d_ff, d_model), nn.Dropout(dropout)
        )
        self.use_phase = use_phase

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        # Pass token_ids to PhaseAttention for operation-conditioned phase shifts
        if self.use_phase and token_ids is not None:
            x = x + self.attn(self.norm1(x), token_ids)
        else:
            x = x + self.attn(self.norm1(x))
        x = x + self.ff(self.norm2(x))
        return x


class HybridTransformerBlock(nn.Module):
    """
    Hybrid block that MIXES Phase and Quadratic attention outputs.

    WHY MIXING (not switching):
    ---------------------------
    Instead of choosing one attention type per layer, we combine both:
      output = phase_ratio * phase_out + (1 - phase_ratio) * quad_out

    This allows smooth interpolation and lets the model learn to leverage
    Phase for state persistence and Quadratic for reasoning within each layer.

    The INVERTED CURRICULUM sets:
    - Early layers: phase_ratio ≈ 0.9 (mostly Phase for state capture)
    - Late layers: phase_ratio ≈ 0.1 (mostly Quadratic for reasoning)
    """

    def __init__(
        self,
        d_model: int,
        num_heads: int,
        d_ff: int,
        dropout: float,
        phase_ratio: float = 0.5,  # 0.0 = pure Quadratic, 1.0 = pure Phase
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
        dual_channel_mode: bool = False,
        alignment_authority: float = 0.1,
    ):
        super().__init__()
        self.phase_ratio = phase_ratio
        self.norm1 = nn.LayerNorm(d_model)
        self.norm2 = nn.LayerNorm(d_model)

        # Both attention types
        self.phase_attn = PhaseAttention(d_model, num_heads, dropout, operation_tokens, bounded_phase,
                                         dual_channel_mode, alignment_authority)
        self.quad_attn = QuadraticAttention(d_model, num_heads, dropout)

        self.ff = nn.Sequential(
            nn.Linear(d_model, d_ff), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(d_ff, d_model), nn.Dropout(dropout)
        )

    def forward(self, x: torch.Tensor, token_ids: torch.Tensor = None) -> torch.Tensor:
        normed = self.norm1(x)

        # Run both attention types
        phase_out = self.phase_attn(normed, token_ids)
        quad_out = self.quad_attn(normed)

        # Mix outputs according to phase_ratio
        attn_out = self.phase_ratio * phase_out + (1 - self.phase_ratio) * quad_out

        x = x + attn_out
        x = x + self.ff(self.norm2(x))
        return x

    def set_ablation(self, mode: str, seed: int = 42):
        """Set ablation mode for Phase attention component."""
        self.phase_attn.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for Phase attention component."""
        self.phase_attn.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from Phase attention component."""
        self.phase_attn.clear_rotation()


class HybridTransformer(nn.Module):
    """
    Transformer with per-layer Phase/Quadratic mixing (INVERTED CURRICULUM).

    INVERTED CURRICULUM RATIONALE:
    ------------------------------
    Evidence shows PhaseAttention excels at STATE PERSISTENCE, not reasoning.
    Therefore:
    - Early layers: Phase-heavy → capture input state with O(n) efficiency
    - Late layers: Quadratic-heavy → reason over persisted state

    Curriculum format: List of phase_ratios per layer
    - [0.9, 0.7, 0.3, 0.1] = Inverted (Phase early, Quad late) ← RECOMMENDED
    - [0.1, 0.3, 0.7, 0.9] = Standard (Quad early, Phase late)
    - [0.5, 0.5, 0.5, 0.5] = Balanced
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
        curriculum: List[float],  # phase_ratio per layer
        operation_tokens: List[int] = None,
        bounded_phase: bool = True,
        dual_channel_mode: bool = False,
        alignment_authority: float = 0.1,
    ):
        super().__init__()
        self.curriculum = curriculum
        self.operation_tokens = operation_tokens
        self.dual_channel_mode = dual_channel_mode
        self.alignment_authority = alignment_authority

        assert len(curriculum) == num_layers, \
            f"Curriculum length ({len(curriculum)}) must match num_layers ({num_layers})"

        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.dropout = nn.Dropout(dropout)

        self.layers = nn.ModuleList([
            HybridTransformerBlock(
                d_model, num_heads, d_ff, dropout,
                phase_ratio=curriculum[i],
                operation_tokens=operation_tokens,
                bounded_phase=bounded_phase,
                dual_channel_mode=dual_channel_mode,
                alignment_authority=alignment_authority,
            )
            for i in range(num_layers)
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
        """Set ablation mode for all Phase attention components."""
        for layer in self.layers:
            layer.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float):
        """Set rotation angle for all Phase attention layers."""
        for layer in self.layers:
            layer.set_rotation(angle_radians)

    def clear_rotation(self):
        """Clear rotation from all Phase attention layers."""
        for layer in self.layers:
            layer.clear_rotation()

    def enable_diagnostics(self, enable: bool = True):
        """Enable/disable phase diagnostics capture."""
        for layer in self.layers:
            layer.phase_attn.capture_diagnostics = enable

    def get_R_k(self) -> float:
        """Get mean R_k across all Phase attention layers."""
        r_values = []
        for layer in self.layers:
            r_values.append(layer.phase_attn.get_R_k())
        return sum(r_values) / len(r_values) if r_values else 0.0

    def count_params(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def describe_curriculum(self) -> str:
        """Return human-readable curriculum description."""
        parts = []
        for i, ratio in enumerate(self.curriculum):
            parts.append(f"L{i}:{ratio*100:.0f}%P")
        return " → ".join(parts)


# =============================================================================

"""
Phase-Aware Adaptation: IA³ gates + surgical LoRA for Phase Quad.

This module implements controlled plasticity for Phase Quad without
breaking the existing phase math, AdaLN-Zero training geometry, or
no-write contract.

Design principles:
1. IA³ (primary): Multiplicative scaling aligned with Phase Quad's
   existing gate architecture. Scales activations, not weights.
   Zero additional sequential ops.

2. LoRA (secondary, surgical): Low-rank weight deltas ONLY on
   projection matrices (q/k/v). Never on MLP, residual paths,
   or phase gates. Used only when task requires new attention geometry.

3. Phase-scoped: Gates are indexed by (layer, path) to prevent
   adaptation from leaking across phase domains.

Reference: Liu et al. 2022, "Few-Shot Parameter-Efficient Fine-Tuning
is Better and Cheaper than In-Context Learning" (IA³)
Reference: Hu et al. 2021, "LoRA: Low-Rank Adaptation of Large
Language Models"
"""

import math
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class IA3Config:
    """Configuration for phase-aware IA³ gates.

    Attributes:
        enable: Master switch for IA³ adaptation.
        gate_attention: Scale attention value outputs per path.
        gate_mlp: Scale MLP hidden activations per path.
        gate_quad: Scale quad cross-attention outputs.
        init_value: Initial gate value (1.0 = identity at start).
        regularization_lambda: Strength of ||g - 1||² regularizer.
            Keeps gates near identity to prevent drift.
        paths: List of phase path names for scoping.
    """
    enable: bool = True
    gate_attention: bool = True
    gate_mlp: bool = True
    gate_quad: bool = True
    init_value: float = 1.0
    regularization_lambda: float = 0.01
    paths: List[str] = field(
        default_factory=lambda: ["local", "quad", "ffn"]
    )


@dataclass
class LoRAConfig:
    """Configuration for surgical LoRA on projections.

    Attributes:
        enable: Master switch for LoRA adaptation.
        rank: Low-rank dimension r. Keep small (4-8) for Phase Quad.
        alpha: Scaling factor. Typical: alpha = 2 * rank.
        dropout: Dropout on LoRA path (0.0 to disable).
        target_modules: Which projection matrices to adapt.
            Only q/k/v projections — never MLP or residual.
    """
    enable: bool = False
    rank: int = 8
    alpha: float = 16.0
    dropout: float = 0.0
    target_modules: List[str] = field(
        default_factory=lambda: ["W_q", "W_k", "W_v"]
    )


@dataclass
class AdaptationConfig:
    """Combined adaptation configuration.

    Attributes:
        ia3: IA³ gate configuration (primary adaptation).
        lora: LoRA configuration (secondary, surgical).
        freeze_base: Whether to freeze base model weights.
    """
    ia3: IA3Config = field(default_factory=IA3Config)
    lora: LoRAConfig = field(default_factory=LoRAConfig)
    freeze_base: bool = True


# ---------------------------------------------------------------------------
# IA³ Gate: Phase-Aware Multiplicative Scaling
# ---------------------------------------------------------------------------

class IA3Gate(nn.Module):
    """Single IA³ gate vector for one (layer, path) pair.

    Learns a multiplicative scaling vector g ∈ R^d that modulates
    activations: y = x ⊙ g

    This is architecturally congruent with Phase Quad's existing
    AdaLN-Zero multiplicative gates, but learned per-task rather
    than per-timestep.

    Args:
        dim: Dimension of the gate vector.
        init_value: Initial value (1.0 = identity).
    """

    def __init__(self, dim: int, init_value: float = 1.0):
        super().__init__()
        self.gate = nn.Parameter(torch.full((dim,), init_value))

    def forward(self, x: Tensor) -> Tensor:
        """Apply multiplicative gate: y = x ⊙ g.

        Args:
            x: Input tensor [..., D].

        Returns:
            Scaled tensor [..., D].
        """
        return x * self.gate


class IA3BlockGates(nn.Module):
    """Phase-aware IA³ gates for a single PhaseQuadDiTBlock.

    Creates separate gate vectors for each path (local attention,
    quad cross-attention, FFN) within a single block. Gates are
    scoped per-path to prevent adaptation from leaking.

    Args:
        embed_dim: Model dimension D.
        ffn_dim: FFN hidden dimension (for MLP gate).
        config: IA³ configuration.
    """

    def __init__(
        self,
        embed_dim: int,
        ffn_dim: int,
        config: IA3Config,
    ):
        super().__init__()
        self.config = config

        # Attention value gate: scales attention output per path
        if config.gate_attention:
            self.gate_local_attn = IA3Gate(embed_dim, config.init_value)
        else:
            self.gate_local_attn = None

        # Quad cross-attention output gate
        if config.gate_quad:
            self.gate_quad_attn = IA3Gate(embed_dim, config.init_value)
        else:
            self.gate_quad_attn = None

        # MLP hidden activation gate (applied after activation, before down_proj)
        if config.gate_mlp:
            self.gate_ffn = IA3Gate(ffn_dim, config.init_value)
        else:
            self.gate_ffn = None

    def scale_local_attn(self, x: Tensor) -> Tensor:
        """Scale local attention output."""
        if self.gate_local_attn is not None:
            return self.gate_local_attn(x)
        return x

    def scale_quad_attn(self, x: Tensor) -> Tensor:
        """Scale quad cross-attention output."""
        if self.gate_quad_attn is not None:
            return self.gate_quad_attn(x)
        return x

    def scale_ffn_hidden(self, x: Tensor) -> Tensor:
        """Scale FFN hidden activations (between activation and down_proj)."""
        if self.gate_ffn is not None:
            return self.gate_ffn(x)
        return x

    def regularization_loss(self) -> Tensor:
        """Compute ||g - 1||² regularization for all gates.

        Keeps gates near identity to prevent catastrophic drift.
        """
        loss = torch.tensor(0.0, device=self._get_device())
        count = 0
        for gate_module in [self.gate_local_attn, self.gate_quad_attn, self.gate_ffn]:
            if gate_module is not None:
                loss = loss + (gate_module.gate - 1.0).pow(2).mean()
                count += 1
        if count > 0:
            loss = loss / count
        return loss

    def _get_device(self) -> torch.device:
        """Get device from first available parameter."""
        for gate_module in [self.gate_local_attn, self.gate_quad_attn, self.gate_ffn]:
            if gate_module is not None:
                return gate_module.gate.device
        return torch.device("cpu")


# ---------------------------------------------------------------------------
# LoRA: Low-Rank Adaptation for Projection Matrices
# ---------------------------------------------------------------------------

class LoRALinear(nn.Module):
    """LoRA-adapted linear layer.

    Wraps an existing nn.Linear with a low-rank additive path:
        y = Wx + (alpha/r) * BAx

    The base weight W is frozen. Only A and B are trained.

    Args:
        base_linear: The original nn.Linear to adapt.
        rank: Low-rank dimension r.
        alpha: Scaling factor (effective scale = alpha / rank).
        dropout: Dropout rate on LoRA path.
    """

    def __init__(
        self,
        base_linear: nn.Linear,
        rank: int = 8,
        alpha: float = 16.0,
        dropout: float = 0.0,
    ):
        super().__init__()

        self.base_linear = base_linear
        self.rank = rank
        self.alpha = alpha
        self.scaling = alpha / rank

        in_features = base_linear.in_features
        out_features = base_linear.out_features

        # A: down-project (in_features -> rank)
        # Init: Kaiming uniform for A, zeros for B
        # This ensures LoRA starts at zero contribution
        self.lora_A = nn.Parameter(torch.empty(rank, in_features))
        self.lora_B = nn.Parameter(torch.zeros(out_features, rank))

        nn.init.kaiming_uniform_(self.lora_A, a=math.sqrt(5))

        # Optional dropout
        self.lora_dropout = nn.Dropout(dropout) if dropout > 0.0 else nn.Identity()

        # Freeze base weights
        self.base_linear.weight.requires_grad = False
        if self.base_linear.bias is not None:
            self.base_linear.bias.requires_grad = False

        # Track merge state to avoid double-applying LoRA
        self._merged = False

    def forward(self, x: Tensor) -> Tensor:
        """Forward with LoRA: y = Wx + (alpha/r) * B @ A @ x.

        If weights are merged, just use base_linear (delta already in W).

        Args:
            x: Input tensor [..., in_features].

        Returns:
            Output tensor [..., out_features].
        """
        # Base path (frozen, or contains merged delta)
        base_out = self.base_linear(x)

        # Skip LoRA path if weights are already merged into base
        if self._merged:
            return base_out

        # LoRA path (trainable)
        lora_out = self.lora_dropout(x)
        lora_out = F.linear(lora_out, self.lora_A)  # [..., rank]
        lora_out = F.linear(lora_out, self.lora_B)  # [..., out_features]

        return base_out + self.scaling * lora_out

    def merge_weights(self) -> None:
        """Merge LoRA weights into base for zero-overhead inference.

        After calling this, the layer behaves as a standard nn.Linear
        with W' = W + (alpha/r) * B @ A. The LoRA path is skipped in
        forward() to avoid double-applying the delta.
        """
        if self._merged:
            return
        with torch.no_grad():
            delta = self.scaling * (self.lora_B @ self.lora_A)
            self.base_linear.weight.add_(delta)
        self._merged = True

    def unmerge_weights(self) -> None:
        """Reverse merge for continued training."""
        if not self._merged:
            return
        with torch.no_grad():
            delta = self.scaling * (self.lora_B @ self.lora_A)
            self.base_linear.weight.sub_(delta)
        self._merged = False

    @property
    def num_trainable_params(self) -> int:
        """Number of trainable LoRA parameters."""
        return self.lora_A.numel() + self.lora_B.numel()


# ---------------------------------------------------------------------------
# Adaptation Manager: Coordinates IA³ + LoRA across the model
# ---------------------------------------------------------------------------

class PhaseQuadAdaptationManager(nn.Module):
    """Manages adaptation layers across a PhaseQuadDiTBlockStack.

    This is the main entry point for adding controlled plasticity to
    Phase Quad. It:
    1. Creates IA³ gates for each block (primary adaptation)
    2. Optionally wraps projection matrices with LoRA (secondary)
    3. Freezes base model weights when adaptation is enabled
    4. Provides utilities for saving/loading/merging adapters

    Usage:
        model = PhaseQuadDiTBlockStack(...)
        config = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=False),
        )
        adapter = PhaseQuadAdaptationManager(model, config)

        # Training: only adapter params have gradients
        optimizer = torch.optim.AdamW(adapter.trainable_parameters(), lr=5e-4)

        # Forward: use adapter.forward() instead of model.forward()
        output = adapter(x, meta, time_embed, ...)

    Args:
        block_stack: The PhaseQuadDiTBlockStack to adapt.
        config: Adaptation configuration.
    """

    def __init__(
        self,
        block_stack: nn.Module,
        config: AdaptationConfig,
    ):
        super().__init__()
        self.block_stack = block_stack
        self.config = config

        # Create IA³ gates per block
        self.ia3_gates = nn.ModuleList()
        if config.ia3.enable:
            for block in block_stack.blocks:
                embed_dim = block.embed_dim
                # Infer FFN hidden dim from the block's FFN
                ffn_dim = block.ffn[0].out_features  # First linear's output
                self.ia3_gates.append(
                    IA3BlockGates(embed_dim, ffn_dim, config.ia3)
                )
        else:
            # Empty list — no IA³ gates
            for _ in block_stack.blocks:
                self.ia3_gates.append(None)

        # Apply LoRA to projection matrices
        self._lora_modules: List[LoRALinear] = []
        if config.lora.enable:
            self._apply_lora(block_stack, config.lora)

        # Freeze base model if configured
        if config.freeze_base:
            self._freeze_base(block_stack)

    def _apply_lora(self, block_stack: nn.Module, lora_config: LoRAConfig) -> None:
        """Apply LoRA to target projection matrices in QuadRetriever."""
        for block in block_stack.blocks:
            # Only apply to QuadRetriever projections (surgical placement)
            quad = block.quad
            for module_name in lora_config.target_modules:
                if hasattr(quad, module_name):
                    base_linear = getattr(quad, module_name)
                    if isinstance(base_linear, nn.Linear):
                        lora_layer = LoRALinear(
                            base_linear,
                            rank=lora_config.rank,
                            alpha=lora_config.alpha,
                            dropout=lora_config.dropout,
                        )
                        setattr(quad, module_name, lora_layer)
                        self._lora_modules.append(lora_layer)

    def _freeze_base(self, block_stack: nn.Module) -> None:
        """Freeze all base model parameters.

        Only IA³ gates and LoRA A/B matrices remain trainable.
        """
        for param in block_stack.parameters():
            param.requires_grad = False

        # Unfreeze IA³ gates
        for gates in self.ia3_gates:
            if gates is not None:
                for param in gates.parameters():
                    param.requires_grad = True

        # Unfreeze LoRA A/B (may have been frozen by block_stack freeze above
        # since LoRA modules are set as attributes on block_stack's sub-modules)
        for lora_module in self._lora_modules:
            lora_module.lora_A.requires_grad = True
            lora_module.lora_B.requires_grad = True

    def forward(
        self,
        x: Tensor,
        meta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        timestep: Optional[Tensor] = None,
        control=None,
    ) -> Tensor:
        """Forward pass through adapted block stack.

        Injects IA³ scaling at the appropriate points in each block's
        forward pass. Uses hooks rather than modifying the original
        forward method, to keep the base model code untouched.

        This method re-implements the block stack forward with IA³
        gates inserted at the correct positions.

        Args:
            x: Input tokens [B, N, D].
            meta: PatchMeta with spatial info.
            time_embed: Timestep embedding [B, D].
            text_cond: Optional text embeddings.
            timestep: Raw timestep values [B].
            control: Optional BlockControl.

        Returns:
            x: Output tokens [B, N, D].
        """
        from symbolu.vision.controls import QuadControl
        from symbolu.vision.phase_quad_dit_block import compute_phase_strength

        for block, gates in zip(self.block_stack.blocks, self.ia3_gates):
            x = self._adapted_block_forward(
                block, gates, x, meta, time_embed,
                text_cond, timestep, control,
            )
        return x

    def _adapted_block_forward(
        self,
        block,
        gates: Optional[IA3BlockGates],
        x: Tensor,
        meta,
        time_embed: Tensor,
        text_cond: Optional[Tensor] = None,
        timestep: Optional[Tensor] = None,
        control=None,
    ) -> Tensor:
        """Forward through a single block with IA³ gates injected.

        Mirrors PhaseQuadDiTBlock.forward() but inserts IA³ scaling
        at three points:
        1. After local attention output, before residual add
        2. After quad cross-attention output, before residual add
        3. Inside FFN, after GELU activation, before second linear

        If gates is None, falls back to the original forward.
        """
        from symbolu.vision.controls import QuadControl
        from symbolu.vision.phase_quad_dit_block import compute_phase_strength

        if gates is None:
            return block(x, meta, time_embed, text_cond, timestep, control)

        # Get control settings
        enable_quad = control.enable_quad if control else True
        enable_phase = control.enable_phase if control else True
        enable_local = control.enable_local if control else True

        # AdaLN-Zero: compute modulation parameters
        (
            x_norm, shift_attn, scale_attn, gate_attn,
            shift_ffn, scale_ffn, gate_ffn
        ) = block.adaln(x, time_embed)

        # Local path with IA³ scaling
        if enable_local:
            x_local_in = block.adaln.modulate(
                block.norm_local(x), shift_attn, scale_attn
            )
            x_local = block.local(x_local_in, meta, text_cond)
            x_local = gates.scale_local_attn(x_local)  # IA³: scale attention output
            x = x + gate_attn * x_local

        # Phase path (unchanged — IA³ does not touch phase math)
        if enable_phase:
            phase_control = control.get_phase_control() if control else None
            S = block.phase2d(x, meta, phase_control)

            if timestep is not None:
                phase_strength = compute_phase_strength(
                    timestep, block.t_max,
                    block.phase_min_strength, block.phase_max_strength
                )
                while phase_strength.dim() < S.dim():
                    phase_strength = phase_strength.unsqueeze(-1)
                S = S * phase_strength
        else:
            S = x.mean(dim=1, keepdim=True).expand_as(x)

        # Quad retrieval (LoRA is inside W_q/W_k/W_v if enabled)
        quad_control = QuadControl(enable_quad=enable_quad)
        proposals, scores = block.quad(x, S, meta, quad_control)

        # Proposal integration with IA³ scaling
        x_cross_in = block.adaln.modulate(
            block.norm_cross(x), shift_attn, scale_attn
        )

        if block.use_bcvf and block.proposal_mixer is not None:
            x_cross = block.proposal_mixer(x_cross_in, proposals, scores, S)
        else:
            x_cross = block.cross_attn_proposals(x_cross_in, proposals, scores)

        x_cross = gates.scale_quad_attn(x_cross)  # IA³: scale quad output
        x = x + gate_attn * x_cross

        # FFN with IA³ scaling on hidden activations
        x_ffn_in = block.adaln.modulate(
            block.norm_ffn(x), shift_ffn, scale_ffn
        )
        # Manually step through FFN to insert IA³ gate between activation and down_proj
        # FFN structure: Linear(D->H) -> GELU -> Dropout -> Linear(H->D) -> Dropout
        ffn_modules = list(block.ffn.children())
        h = ffn_modules[0](x_ffn_in)      # up_proj: [B, N, ffn_dim]
        h = ffn_modules[1](h)              # GELU activation
        h = gates.scale_ffn_hidden(h)      # IA³: scale after activation
        h = ffn_modules[2](h)              # Dropout
        h = ffn_modules[3](h)              # down_proj: [B, N, D]
        h = ffn_modules[4](h)              # Dropout

        x = x + gate_ffn * h

        return x

    def trainable_parameters(self) -> List[nn.Parameter]:
        """Get all trainable parameters (IA³ gates + LoRA A/B).

        Use this for the optimizer instead of model.parameters().
        """
        params = []

        # IA³ gates
        for gates in self.ia3_gates:
            if gates is not None:
                params.extend(gates.parameters())

        # LoRA parameters
        for lora_module in self._lora_modules:
            params.extend([lora_module.lora_A, lora_module.lora_B])

        return params

    def num_trainable_params(self) -> int:
        """Total count of trainable adaptation parameters."""
        return sum(p.numel() for p in self.trainable_parameters())

    def num_base_params(self) -> int:
        """Total count of frozen base model parameters."""
        return sum(
            p.numel() for p in self.block_stack.parameters()
            if not p.requires_grad
        )

    def regularization_loss(self) -> Tensor:
        """Compute total regularization loss for IA³ gates.

        Returns ||g - 1||² averaged across all gates, scaled by lambda.
        """
        if not self.config.ia3.enable:
            return torch.tensor(0.0)

        total_loss = torch.tensor(0.0)
        count = 0
        for gates in self.ia3_gates:
            if gates is not None:
                total_loss = total_loss + gates.regularization_loss().to(
                    total_loss.device
                )
                count += 1

        if count > 0:
            total_loss = total_loss / count

        return self.config.ia3.regularization_lambda * total_loss

    def merge_lora(self) -> None:
        """Merge all LoRA weights into base model for zero-overhead inference."""
        for lora_module in self._lora_modules:
            lora_module.merge_weights()

    def unmerge_lora(self) -> None:
        """Reverse LoRA merge for continued training."""
        for lora_module in self._lora_modules:
            lora_module.unmerge_weights()

    def save_adapter(self, path: str) -> None:
        """Save only the adaptation weights (IA³ + LoRA).

        Produces a small file (typically <1% of base model size).
        """
        state = {}

        # IA³ gates
        for i, gates in enumerate(self.ia3_gates):
            if gates is not None:
                for name, param in gates.named_parameters():
                    state[f"ia3.block_{i}.{name}"] = param.data.clone()

        # LoRA weights
        for i, lora_module in enumerate(self._lora_modules):
            state[f"lora.{i}.A"] = lora_module.lora_A.data.clone()
            state[f"lora.{i}.B"] = lora_module.lora_B.data.clone()

        state["config"] = {
            "ia3_enable": self.config.ia3.enable,
            "ia3_gate_attention": self.config.ia3.gate_attention,
            "ia3_gate_mlp": self.config.ia3.gate_mlp,
            "ia3_gate_quad": self.config.ia3.gate_quad,
            "lora_enable": self.config.lora.enable,
            "lora_rank": self.config.lora.rank,
            "lora_alpha": self.config.lora.alpha,
        }

        torch.save(state, path)

    def load_adapter(self, path: str) -> None:
        """Load adaptation weights from a saved adapter file."""
        state = torch.load(path, weights_only=True)

        # IA³ gates
        for i, gates in enumerate(self.ia3_gates):
            if gates is not None:
                for name, param in gates.named_parameters():
                    key = f"ia3.block_{i}.{name}"
                    if key in state:
                        param.data.copy_(state[key])

        # LoRA weights
        for i, lora_module in enumerate(self._lora_modules):
            a_key = f"lora.{i}.A"
            b_key = f"lora.{i}.B"
            if a_key in state:
                lora_module.lora_A.data.copy_(state[a_key])
            if b_key in state:
                lora_module.lora_B.data.copy_(state[b_key])

    def get_adaptation_summary(self) -> Dict[str, int]:
        """Get summary of adaptation parameter counts."""
        ia3_params = 0
        lora_params = 0

        for gates in self.ia3_gates:
            if gates is not None:
                ia3_params += sum(p.numel() for p in gates.parameters())

        for lora_module in self._lora_modules:
            lora_params += lora_module.num_trainable_params

        base_params = self.num_base_params()
        total_trainable = ia3_params + lora_params

        return {
            "base_params_frozen": base_params,
            "ia3_params": ia3_params,
            "lora_params": lora_params,
            "total_trainable": total_trainable,
            "adaptation_ratio": total_trainable / max(base_params, 1),
            "num_blocks": len(self.block_stack.blocks),
            "num_lora_modules": len(self._lora_modules),
        }

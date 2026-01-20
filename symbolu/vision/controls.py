"""
Control dataclasses for Phase-Quad Image Generator.

These dataclasses encapsulate control signals that modulate the behavior
of various components while adhering to the no-write contract.
"""

from dataclasses import dataclass, field
from typing import Optional, Callable, Any

import torch
from torch import Tensor


@dataclass
class PatchMeta:
    """
    Metadata from patch embedding.

    Contains spatial information about the patch grid that is needed
    by downstream components for 2D operations.

    Attributes:
        H_p: Number of patch rows (patch grid height).
        W_p: Number of patch columns (patch grid width).
        coords: Integer coordinates for each patch [N, 2] where coords[i] = (row, col).
        patch_size: The patch size used for embedding.
        in_channels: Number of input channels from VAE latent.
    """
    H_p: int
    W_p: int
    coords: Tensor  # [N, 2] integer (row, col) coordinates
    patch_size: int = 2
    in_channels: int = 4

    @property
    def N(self) -> int:
        """Total number of patches."""
        return self.H_p * self.W_p

    def to(self, device: torch.device) -> "PatchMeta":
        """Move coordinates to specified device."""
        return PatchMeta(
            H_p=self.H_p,
            W_p=self.W_p,
            coords=self.coords.to(device),
            patch_size=self.patch_size,
            in_channels=self.in_channels,
        )


@dataclass
class PhaseControl:
    """
    Control signals for PhaseIntegrator.

    All tensor fields must adhere to the no-write contract:
    - Allowed shapes: [], [H], [B, H], [B, H, 1]
    - Forbidden: [B, N, ...] or any token-position-specific shape

    Attributes:
        intent_phase: Phase rotation bias. Rotates the phase angle by a
            broadcastable offset. Shape: [] or [H] or [B, H].
        phase_gain: Scaling factor for phase projection. Shape: [] or [H] or [B, H].
        strict_contract: If True (default), validate control shapes and raise
            ContractViolationError on violations.
    """
    intent_phase: Optional[Tensor] = None
    phase_gain: Optional[Tensor] = None
    strict_contract: bool = True

    def validate(self, num_heads: int, batch_size: Optional[int] = None) -> None:
        """Validate all control signals against no-write contract."""
        if not self.strict_contract:
            return

        from symbolu.vision.contracts import assert_control_shape
        assert_control_shape(self.intent_phase, "intent_phase", num_heads, batch_size)
        assert_control_shape(self.phase_gain, "phase_gain", num_heads, batch_size)


@dataclass
class QuadControl:
    """
    Control signals for QuadRetriever.

    Attributes:
        enable_quad: If False, QuadRetriever returns zeros (for ablation testing).
    """
    enable_quad: bool = True


@dataclass
class GateControl:
    """
    Control signals for GateMixer.

    All tensor fields must adhere to the no-write contract.

    Attributes:
        tau: Temperature for sigmoid gating. Higher values make gates softer,
            allowing more proposals to receive gradient. Should start high (~2.0)
            and decay to ~1.0 during training.
        s_align: Alignment score for modulating gate output. Shape: [] or [H] or [B, H].
        clamp_min: Minimum clamp value for alignment modulation.
        clamp_max: Maximum clamp value for alignment modulation.
    """
    tau: float = 1.0
    s_align: Optional[Tensor] = None
    clamp_min: float = 0.8
    clamp_max: float = 1.2

    def validate(self, num_heads: int, batch_size: Optional[int] = None) -> None:
        """Validate all control signals against no-write contract."""
        from symbolu.vision.contracts import assert_control_shape
        assert_control_shape(self.s_align, "s_align", num_heads, batch_size)


@dataclass
class BlockControl:
    """
    Control signals for full CognadeVisionBlock.

    Aggregates controls for all sub-components.

    Attributes:
        enable_quad: If False, disable Quad retrieval (returns zeros).
        enable_phase: If False, replace Phase with mean pooling (for ablation).
        enable_local: If False, skip LocalMixer (for ablation).
        tau: Temperature for gate sigmoid.
        phase_control: Detailed control for PhaseIntegrator2D.
        gate_control: Detailed control for GateMixer.
    """
    enable_quad: bool = True
    enable_phase: bool = True
    enable_local: bool = True
    tau: float = 1.0
    phase_control: Optional[PhaseControl] = None
    gate_control: Optional[GateControl] = None

    def get_phase_control(self) -> PhaseControl:
        """Get PhaseControl, creating default if None."""
        return self.phase_control or PhaseControl()

    def get_gate_control(self) -> GateControl:
        """Get GateControl with tau, creating if needed."""
        if self.gate_control is not None:
            # Update tau from block-level setting
            return GateControl(
                tau=self.tau,
                s_align=self.gate_control.s_align,
                clamp_min=self.gate_control.clamp_min,
                clamp_max=self.gate_control.clamp_max,
            )
        return GateControl(tau=self.tau)

    def get_quad_control(self) -> QuadControl:
        """Get QuadControl based on enable_quad setting."""
        return QuadControl(enable_quad=self.enable_quad)


@dataclass
class GeneratorControl:
    """
    Control signals for the full PhaseQuadImageGenerator.

    Attributes:
        tau: Global temperature for all blocks.
        enable_quad: Global enable/disable for Quad retrieval.
        enable_phase: Global enable/disable for Phase integration.
        per_block_controls: Optional per-block control overrides.
    """
    tau: float = 1.0
    enable_quad: bool = True
    enable_phase: bool = True
    per_block_controls: Optional[dict[int, BlockControl]] = None

    def get_block_control(self, block_idx: int) -> BlockControl:
        """Get control for a specific block."""
        if self.per_block_controls and block_idx in self.per_block_controls:
            return self.per_block_controls[block_idx]
        return BlockControl(
            enable_quad=self.enable_quad,
            enable_phase=self.enable_phase,
            tau=self.tau,
        )

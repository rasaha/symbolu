"""
PhaseIntegrator3D: Tri-axial phase accumulation for video generation.

This module extends PhaseIntegrator2D with a temporal axis for video.
The same Phase accumulation mechanism that provides spatial memory
extends naturally to temporal memory.

Key insight from design doc:
    Image:  Phase2D(row, col) → spatial coherence
    Video:  Phase3D(row, col, time) → spatial + temporal coherence

Architecture:
    1. Row integrator (per frame, per row)
    2. Col integrator (per frame, per column)
    3. Time integrator (per spatial position across frames)
    4. Merge: S = Norm(Linear([S_row, S_col, S_time]))

Complexity: O(T·H·W·D) - linear in video size
"""

from typing import Tuple, Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.phase_integrator import PhaseIntegrator1D
from symbolu.vision.controls import PhaseControl


class VideoMeta:
    """
    Metadata for video patches.

    Attributes:
        T: Number of temporal positions (latent frames).
        H_p: Number of patch rows per frame.
        W_p: Number of patch columns per frame.
        coords: [N, 3] integer (t, row, col) coordinates.
        patch_size: Spatial patch size.
        temporal_patch_size: Temporal patch size (usually 1).
        in_channels: Number of input channels from VAE latent.
    """

    def __init__(
        self,
        T: int,
        H_p: int,
        W_p: int,
        coords: Optional[Tensor] = None,
        patch_size: int = 2,
        temporal_patch_size: int = 1,
        in_channels: int = 4,
    ):
        self.T = T
        self.H_p = H_p
        self.W_p = W_p
        self.patch_size = patch_size
        self.temporal_patch_size = temporal_patch_size
        self.in_channels = in_channels

        # Generate default coords if not provided
        if coords is not None:
            self.coords = coords
        else:
            # Create (t, row, col) coordinates for all patches
            t_idx = torch.arange(T)
            h_idx = torch.arange(H_p)
            w_idx = torch.arange(W_p)
            # Meshgrid: [T, H_p, W_p, 3]
            grid_t, grid_h, grid_w = torch.meshgrid(t_idx, h_idx, w_idx, indexing='ij')
            self.coords = torch.stack([grid_t.flatten(), grid_h.flatten(), grid_w.flatten()], dim=-1)

    @property
    def N(self) -> int:
        """Total number of patches."""
        return self.T * self.H_p * self.W_p

    @property
    def spatial_shape(self) -> Tuple[int, int]:
        """Spatial patch grid shape."""
        return (self.H_p, self.W_p)

    @property
    def shape(self) -> Tuple[int, int, int]:
        """Full patch grid shape (T, H_p, W_p)."""
        return (self.T, self.H_p, self.W_p)

    def to(self, device: torch.device) -> "VideoMeta":
        """Move coordinates to specified device."""
        return VideoMeta(
            T=self.T,
            H_p=self.H_p,
            W_p=self.W_p,
            coords=self.coords.to(device),
            patch_size=self.patch_size,
            temporal_patch_size=self.temporal_patch_size,
            in_channels=self.in_channels,
        )


class PhaseIntegrator3D(nn.Module):
    """
    Tri-axial phase integration for video.

    Extends PhaseIntegrator2D with temporal axis. Uses three independent
    PhaseIntegrator1D instances for row, column, and time dimensions.

    The time integrator has special significance for video:
    - High gamma (~0.99): Strong temporal coherence (objects persist)
    - Low gamma (~0.7): More temporal variation (allows scene changes)

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        decay_gamma: Default decay factor for all axes.
        learned_decay: If True, learn per-head decay for each axis.
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        decay_gamma: float = 0.9,
        learned_decay: bool = True,
    ):
        super().__init__()

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        if embed_dim % num_heads != 0:
            raise ValueError(
                f"embed_dim ({embed_dim}) must be divisible by "
                f"num_heads ({num_heads})"
            )

        # Separate integrators for each axis
        self.row_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.col_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.time_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )

        # Merge all three axes: 3D -> D
        self.merge = nn.Linear(3 * embed_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        x: Tensor,
        meta: VideoMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tensor:
        """
        Compute tri-axial phase state.

        Args:
            x: Input tensor [B, T, H_p, W_p, D] or [B, N, D].
            meta: VideoMeta with T, H_p, W_p dimensions.
            control: Optional PhaseControl (gamma_scale affects temporal coherence).

        Returns:
            S: Phase state [B, N, D] with temporal coherence.
        """
        B = x.shape[0]
        T, H_p, W_p = meta.T, meta.H_p, meta.W_p
        N = T * H_p * W_p
        D = self.embed_dim

        # Reshape to [B, T, H_p, W_p, D] if flattened
        if x.dim() == 3:
            x = x.view(B, T, H_p, W_p, D)

        # Row scan: within each frame, within each row
        # [B, T, H_p, W_p, D] → [B*T*H_p, W_p, D]
        x_row = x.reshape(B * T * H_p, W_p, D)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = S_row.view(B, T, H_p, W_p, D)

        # Col scan: within each frame, within each column
        # [B, T, H_p, W_p, D] → [B, T, W_p, H_p, D] → [B*T*W_p, H_p, D]
        x_col = x.permute(0, 1, 3, 2, 4).reshape(B * T * W_p, H_p, D)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        # [B*T*W_p, H_p, D] → [B, T, W_p, H_p, D] → [B, T, H_p, W_p, D]
        S_col = S_col.view(B, T, W_p, H_p, D).permute(0, 1, 3, 2, 4)

        # Time scan: across frames, per spatial position
        # [B, T, H_p, W_p, D] → [B, H_p, W_p, T, D] → [B*H_p*W_p, T, D]
        x_time = x.permute(0, 2, 3, 1, 4).reshape(B * H_p * W_p, T, D)
        S_time_re, S_time_im = self.time_integrator(x_time, control)
        S_time = self._complex_to_features(S_time_re, S_time_im)
        # [B*H_p*W_p, T, D] → [B, H_p, W_p, T, D] → [B, T, H_p, W_p, D]
        S_time = S_time.view(B, H_p, W_p, T, D).permute(0, 3, 1, 2, 4)

        # Merge all three axes
        S_cat = torch.cat([S_row, S_col, S_time], dim=-1)  # [B, T, H_p, W_p, 3D]
        S = self.norm(self.merge(S_cat))                   # [B, T, H_p, W_p, D]

        # Flatten to [B, N, D]
        S = S.reshape(B, N, D)

        return S

    def _complex_to_features(self, S_re: Tensor, S_im: Tensor) -> Tensor:
        """
        Convert complex state to real features.

        Args:
            S_re, S_im: [B, N, H, D_h] real/imaginary parts.

        Returns:
            features: [B, N, D] real feature tensor.
        """
        B, N, H, D_h = S_re.shape
        # Use real part (can also use magnitude or concat)
        return S_re.reshape(B, N, H * D_h)

    def get_health_metrics(self) -> dict:
        """Get health metrics from all three integrators."""
        row_metrics = self.row_integrator.get_health_metrics()
        col_metrics = self.col_integrator.get_health_metrics()
        time_metrics = self.time_integrator.get_health_metrics()
        return {
            "row_amplitude_mean": row_metrics["amplitude_mean"],
            "row_amplitude_std": row_metrics["amplitude_std"],
            "col_amplitude_mean": col_metrics["amplitude_mean"],
            "col_amplitude_std": col_metrics["amplitude_std"],
            "time_amplitude_mean": time_metrics["amplitude_mean"],
            "time_amplitude_std": time_metrics["amplitude_std"],
        }

    def get_decay_gammas(self) -> dict:
        """Get learned decay values for each axis."""
        return {
            "row_gamma": self.row_integrator._get_decay().detach().cpu(),
            "col_gamma": self.col_integrator._get_decay().detach().cpu(),
            "time_gamma": self.time_integrator._get_decay().detach().cpu(),
        }

    @staticmethod
    def compute_phase_correlation(
        x: Tensor, y: Tensor, eps: float = 1e-8,
    ) -> Tensor:
        """
        Compute phase correlation between feature vectors in diffusion
        embedding space.

        Uses the PhaseIntegrator's complex phasor interpretation:
        feature dimensions are split into real/imaginary pairs and
        phase correlation is computed as the average cosine of phase
        differences.

        Patent formula U1:
            C[i,j] = (1/W) * sum_k cos(phi_i[k] - phi_j[k])

        This bridges the ontological phase correlation (token-level)
        with diffusion-level hidden states for FSCS-V.

        Args:
            x: Features [..., D]. Must have even D.
            y: Features [..., D].
            eps: Numerical stability.

        Returns:
            phase_corr: Phase correlation in [-1, 1], shape [...].
        """
        D = x.shape[-1]
        half_D = D // 2

        x_re, x_im = x[..., :half_D], x[..., half_D : 2 * half_D]
        y_re, y_im = y[..., :half_D], y[..., half_D : 2 * half_D]

        # Cross-correlation: Re(x * conj(y))
        cross_re = x_re * y_re + x_im * y_im

        # Magnitudes
        x_mag = torch.sqrt(x_re ** 2 + x_im ** 2 + eps)
        y_mag = torch.sqrt(y_re ** 2 + y_im ** 2 + eps)

        # Normalized per-component phase correlation
        phase_corr = cross_re / (x_mag * y_mag + eps)

        # Average over feature components (formula U1)
        return phase_corr.mean(dim=-1)

    def get_scan_states(
        self,
        x: Tensor,
        meta: VideoMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tuple[Tensor, Tensor, Tensor]:
        """
        Get separate row, column, and time states (for diagnostics).

        Args:
            x: Input tensor [B, N, D] or [B, T, H_p, W_p, D].
            meta: VideoMeta containing grid dimensions.
            control: Optional PhaseControl.

        Returns:
            S_row: [B, N, D] row scan state.
            S_col: [B, N, D] column scan state.
            S_time: [B, N, D] time scan state.
        """
        B = x.shape[0]
        T, H_p, W_p = meta.T, meta.H_p, meta.W_p
        N = T * H_p * W_p
        D = self.embed_dim

        # Reshape if flattened
        if x.dim() == 3:
            x = x.view(B, T, H_p, W_p, D)

        # Row scan
        x_row = x.reshape(B * T * H_p, W_p, D)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = S_row.view(B, N, D)

        # Col scan
        x_col = x.permute(0, 1, 3, 2, 4).reshape(B * T * W_p, H_p, D)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        S_col = S_col.view(B, T, W_p, H_p, D).permute(0, 1, 3, 2, 4).reshape(B, N, D)

        # Time scan
        x_time = x.permute(0, 2, 3, 1, 4).reshape(B * H_p * W_p, T, D)
        S_time_re, S_time_im = self.time_integrator(x_time, control)
        S_time = self._complex_to_features(S_time_re, S_time_im)
        S_time = S_time.view(B, H_p, W_p, T, D).permute(0, 3, 1, 2, 4).reshape(B, N, D)

        return S_row, S_col, S_time

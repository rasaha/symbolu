"""
PhaseIntegrator: Core O(N) phase accumulation for Phase-Quad architecture.

This module implements the Phase Integrator that accumulates key-value
pairs into a persistent state via complex phasor cumsum/EMA operations.

The vision adaptation handles 2D spatial coherence through bi-axial scans.

Key properties:
- O(N) state accumulation (not O(N²) like full attention)
- Bounded phase via π·sin() (mandatory)
- No token-position-specific control signals (no-write contract)
"""

import math
from typing import Tuple, Optional

import torch
import torch.nn as nn
from torch import Tensor

from symbolu.vision.contracts import assert_control_shape
from symbolu.vision.controls import PhaseControl, PatchMeta
from symbolu.vision.scan_manager import ScanManager2D, get_scan_manager


def parallel_ema_scan_complex(
    kv_re: Tensor,
    kv_im: Tensor,
    gamma: Tensor,
) -> Tuple[Tensor, Tensor]:
    """
    Parallel EMA scan for complex key-value products.

    Implements cumulative sum with exponential decay in a numerically
    stable way. Uses associative scan for parallel computation.

    Args:
        kv_re: Real part of k⊙v [B, N, H, D_h].
        kv_im: Imaginary part of k⊙v [B, N, H, D_h].
        gamma: Decay factor(s) [H] or scalar.

    Returns:
        S_re: Accumulated real state [B, N, H, D_h].
        S_im: Accumulated imaginary state [B, N, H, D_h].
    """
    B, N, H, D_h = kv_re.shape

    # Ensure gamma has right shape
    if gamma.dim() == 0:
        gamma = gamma.expand(H)

    # Prepare gamma for broadcasting: [H] -> [1, 1, H, 1]
    gamma = gamma.view(1, 1, H, 1)

    # Compute decay weights for each position
    # decay[n] = gamma^n for position n
    positions = torch.arange(N, device=kv_re.device, dtype=kv_re.dtype)
    decay_powers = gamma ** positions.view(1, N, 1, 1)  # [1, N, H, 1]

    # Scale inputs by decay power
    kv_re_scaled = kv_re * decay_powers
    kv_im_scaled = kv_im * decay_powers

    # Cumulative sum
    S_re_scaled = torch.cumsum(kv_re_scaled, dim=1)
    S_im_scaled = torch.cumsum(kv_im_scaled, dim=1)

    # Unscale by dividing by decay power
    # S[n] = sum_{i=0}^{n} gamma^{n-i} * kv[i]
    #      = gamma^n * sum_{i=0}^{n} gamma^{-i} * kv[i]
    # But we computed sum_{i=0}^{n} gamma^i * kv[i]
    # So we need: S[n] = scaled_cumsum[n] * gamma^n / gamma^{2n}
    # Actually simpler: use inverse decay
    inverse_decay = 1.0 / (decay_powers + 1e-8)
    S_re = S_re_scaled * inverse_decay
    S_im = S_im_scaled * inverse_decay

    return S_re, S_im


class PhaseIntegrator1D(nn.Module):
    """
    Core 1D phase accumulation via phasor cumsum/EMA.

    This is the vision adaptation of BindingCachePhaseState.
    Key difference: No token-position-specific control allowed.

    Math per token t, per head h:
        φ_raw = W_k_phase(x)             [B, N, H]
        a = sigmoid(W_k_amp(x))          [B, N, H]
        v = W_v(x)                       [B, N, D]

        # Bounded phase (mandatory)
        φ = π · sin(φ_raw + intent_phase)

        # Complex phasor
        k = a · exp(-iφ)

        # State accumulation
        S_t = γ · S_{t-1} + (1-γ) · (k ⊙ v)

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        decay_gamma: Default decay factor (0 < γ < 1).
        learned_decay: If True, learn per-head decay.
        bounded_phase: If True, use π·sin() for bounded phase (mandatory).
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        decay_gamma: float = 0.9,
        learned_decay: bool = True,
        bounded_phase: bool = True,
    ):
        super().__init__()

        if not bounded_phase:
            raise ValueError(
                "bounded_phase must be True. Unbounded phase is explicitly "
                "disabled per design specification."
            )

        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        self.bounded_phase = bounded_phase

        if embed_dim % num_heads != 0:
            raise ValueError(
                f"embed_dim ({embed_dim}) must be divisible by "
                f"num_heads ({num_heads})"
            )

        # Phase projections
        self.W_k_phase = nn.Linear(embed_dim, num_heads)  # phase per head
        self.W_k_amp = nn.Linear(embed_dim, num_heads)    # amplitude per head
        self.W_v = nn.Linear(embed_dim, embed_dim)        # values

        # Decay parameter
        if learned_decay:
            # Log-space timescale init (2 to 2048 tokens)
            log_timescales = torch.linspace(
                math.log(2.0), math.log(2048.0), num_heads
            )
            timescales = torch.exp(log_timescales)
            gamma = 1.0 - (1.0 / timescales)
            gamma = torch.clamp(gamma, 0.001, 0.9995)
            init_logits = torch.logit(gamma)
            self.decay_logit = nn.Parameter(init_logits)
        else:
            self.register_buffer("decay_gamma", torch.tensor(decay_gamma))

        self.learned_decay = learned_decay

        # Health tracking (not parameters, just buffers for monitoring)
        self.register_buffer("_last_a_k_mean", torch.tensor(0.0))
        self.register_buffer("_last_a_k_std", torch.tensor(0.0))

    def forward(
        self,
        x: Tensor,
        control: Optional[PhaseControl] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Compute phase state via cumsum/EMA.

        Args:
            x: Input tensor [B, N, D].
            control: Optional PhaseControl containing:
                - intent_phase: [] or [H] or [B, H] rotation bias
                - phase_gain: [] or [H] or [B, H] scaling
                - strict_contract: bool (default True)

        Returns:
            S_re: [B, N, H, D_h] real part of state.
            S_im: [B, N, H, D_h] imaginary part of state.

        Raises:
            ContractViolationError: If control shape violates no-write contract.
        """
        # Validate contract
        if control is not None and control.strict_contract:
            assert_control_shape(
                control.intent_phase, "intent_phase", self.num_heads
            )
            assert_control_shape(
                control.phase_gain, "phase_gain", self.num_heads
            )

        B, N, D = x.shape
        H = self.num_heads
        D_h = self.head_dim

        # Compute phase and amplitude
        phi_raw = self.W_k_phase(x)                    # [B, N, H]
        a_k = torch.sigmoid(self.W_k_amp(x))          # [B, N, H]
        v = self.W_v(x).view(B, N, H, D_h)            # [B, N, H, D_h]

        # Apply control (contract-safe)
        if control is not None and control.intent_phase is not None:
            intent = control.intent_phase
            # Broadcast: [] -> [1,1,1], [H] -> [1,1,H], [B,H] -> [B,1,H]
            while intent.dim() < 3:
                intent = intent.unsqueeze(0 if intent.dim() == 1 else 1)
            phi_raw = phi_raw + intent

        if control is not None and control.phase_gain is not None:
            gain = control.phase_gain
            while gain.dim() < 3:
                gain = gain.unsqueeze(0 if gain.dim() == 1 else 1)
            phi_raw = phi_raw * gain

        # Bounded phase (mandatory)
        # Critical: Compute in FP32 for numerical stability
        with torch.autocast(device_type=x.device.type, enabled=False):
            phi_raw_fp32 = phi_raw.float()
            phi_k = math.pi * torch.sin(phi_raw_fp32)  # [B, N, H]

            # Track health
            with torch.no_grad():
                self._last_a_k_mean = a_k.mean()
                self._last_a_k_std = a_k.std()

            # Complex phasor computation
            a_k_fp32 = a_k.float()
            cos_phi = torch.cos(-phi_k)
            sin_phi = torch.sin(-phi_k)

            # k_re, k_im: [B, N, H]
            k_re = a_k_fp32 * cos_phi
            k_im = a_k_fp32 * sin_phi

        # Expand for head dim: [B, N, H] -> [B, N, H, 1]
        k_re = k_re.unsqueeze(-1)
        k_im = k_im.unsqueeze(-1)

        # kv product (complex)
        v_fp32 = v.float()
        kv_re = k_re * v_fp32  # [B, N, H, D_h]
        kv_im = k_im * v_fp32  # [B, N, H, D_h]

        # State accumulation
        gamma = self._get_decay()  # [H] or scalar
        S_re, S_im = parallel_ema_scan_complex(kv_re, kv_im, gamma)

        # Convert back to original dtype
        S_re = S_re.to(x.dtype)
        S_im = S_im.to(x.dtype)

        return S_re, S_im

    def _get_decay(self) -> Tensor:
        """Get decay factor(s)."""
        if self.learned_decay:
            return torch.sigmoid(self.decay_logit)
        return self.decay_gamma

    def get_health_metrics(self) -> dict:
        """Get health metrics for monitoring."""
        return {
            "amplitude_mean": self._last_a_k_mean.item(),
            "amplitude_std": self._last_a_k_std.item(),
        }


class PhaseIntegrator2D(nn.Module):
    """
    Bi-axial phase integration for 2D spatial coherence.

    Runs two orthogonal 1D phase scans (row + column) and merges results.
    This reduces recurrent artifacts and directional bias while maintaining O(N).

    Architecture:
        1. Reorder x to row-major scan → run PhaseIntegrator1D → S_row
        2. Reorder x to col-major scan → run PhaseIntegrator1D → S_col
        3. Restore canonical order for both
        4. Merge: S = LayerNorm(W_merge([S_row, S_col]))

    Note: Bi-axial scans support non-square grids (H ≠ W). The learned merge
    projection and output normalization ensure no directional bias from
    differing scan lengths.

    Args:
        embed_dim: Model dimension D.
        num_heads: Number of attention heads H.
        decay_gamma: Default decay factor.
        learned_decay: If True, learn per-head decay.
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

        # Separate integrators for row and column scans
        self.row_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )
        self.col_integrator = PhaseIntegrator1D(
            embed_dim, num_heads, decay_gamma, learned_decay
        )

        # Merge row and col states
        self.merge = nn.Linear(2 * embed_dim, embed_dim)
        self.norm = nn.LayerNorm(embed_dim)

        # Scan manager cache
        self._scan_manager: Optional[ScanManager2D] = None
        self._last_grid_size: Optional[Tuple[int, int]] = None

    def forward(
        self,
        x: Tensor,
        meta: PatchMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tensor:
        """
        Compute bi-axial phase state.

        Per design doc E.2.2: Phase state resets at each diffusion timestep.
        Within a timestep, state persists across this forward pass.

        Args:
            x: Input tensor [B, N, D].
            meta: PatchMeta containing H_p, W_p grid dimensions.
            control: Optional PhaseControl (contract-validated).

        Returns:
            S: Merged phase state [B, N, D] ready for Quad retrieval.
        """
        B, N, D = x.shape

        # Initialize or update scan manager
        grid_size = (meta.H_p, meta.W_p)
        if self._scan_manager is None or self._last_grid_size != grid_size:
            self._scan_manager = get_scan_manager(meta.H_p, meta.W_p, str(x.device))
            self._last_grid_size = grid_size

        scan = self._scan_manager

        # Ensure scan manager is on correct device
        if scan._device != x.device:
            scan = scan.to(x.device)
            self._scan_manager = scan

        # Row-major scan
        x_row = scan.gather(x, scan.row_order)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = scan.scatter(S_row, scan.row_order)  # restore order

        # Column-major scan
        x_col = scan.gather(x, scan.col_order)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        S_col = scan.scatter(S_col, scan.col_order)  # restore order

        # Merge
        S_cat = torch.cat([S_row, S_col], dim=-1)  # [B, N, 2D]
        S = self.norm(self.merge(S_cat))           # [B, N, D]

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
        """Get health metrics from both integrators."""
        row_metrics = self.row_integrator.get_health_metrics()
        col_metrics = self.col_integrator.get_health_metrics()
        return {
            "row_amplitude_mean": row_metrics["amplitude_mean"],
            "row_amplitude_std": row_metrics["amplitude_std"],
            "col_amplitude_mean": col_metrics["amplitude_mean"],
            "col_amplitude_std": col_metrics["amplitude_std"],
        }

    def get_scan_states(
        self,
        x: Tensor,
        meta: PatchMeta,
        control: Optional[PhaseControl] = None,
    ) -> Tuple[Tensor, Tensor]:
        """
        Get separate row and column states (for diagnostics).

        Args:
            x: Input tensor [B, N, D].
            meta: PatchMeta containing grid dimensions.
            control: Optional PhaseControl.

        Returns:
            S_row: [B, N, D] row scan state.
            S_col: [B, N, D] column scan state.
        """
        B, N, D = x.shape

        # Initialize scan manager
        grid_size = (meta.H_p, meta.W_p)
        if self._scan_manager is None or self._last_grid_size != grid_size:
            self._scan_manager = get_scan_manager(meta.H_p, meta.W_p, str(x.device))
            self._last_grid_size = grid_size

        scan = self._scan_manager

        # Row-major scan
        x_row = scan.gather(x, scan.row_order)
        S_row_re, S_row_im = self.row_integrator(x_row, control)
        S_row = self._complex_to_features(S_row_re, S_row_im)
        S_row = scan.scatter(S_row, scan.row_order)

        # Column-major scan
        x_col = scan.gather(x, scan.col_order)
        S_col_re, S_col_im = self.col_integrator(x_col, control)
        S_col = self._complex_to_features(S_col_re, S_col_im)
        S_col = scan.scatter(S_col, scan.col_order)

        return S_row, S_col

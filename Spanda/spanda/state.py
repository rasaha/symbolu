"""
SpandaState: Psi state evolution module.

Computes Delta_t = MLP(h_t) and evolves Psi via leaky integration + norm clamping.
Psi is computed per-sequence (no module-level mutable state).

For T <= PARALLEL_THRESHOLD: sequential loop with per-step norm clamping.
For T > PARALLEL_THRESHOLD: chunked parallel discounted cumsum with per-chunk
    norm clamping, preserving sequential semantics while keeping GPU parallelism.

V2: Dual timescale memory — fast (gamma_fast) + slow (gamma_slow) accumulators
    combined via learnable weights. Backward compatible: loads single-gamma
    checkpoints seamlessly.
"""

import math
import torch
import torch.nn as nn


class SpandaState(nn.Module):
    """
    Spanda state evolution: Delta computation + Psi recurrence.

    Psi_raw_t = gamma * Psi_{t-1} + Delta_t
    Psi_t = Psi_raw_t / max(1, ||Psi_raw_t|| / c)

    V2: Optional dual timescale mode. When enabled:
        F_t = gamma_fast * F_{t-1} + Delta_t   (fast memory, ~200 step horizon)
        S_t = gamma_slow * S_{t-1} + Delta_t   (slow memory, ~1000 step horizon)
        Psi_t = Wf * F_t + Ws * S_t            (learnable combination)

    Args:
        embed_dim: Dimension of input hidden states h_t.
        psi_dim: Dimension of Psi state vector (default 256).
        decay_gamma: Leaky integration factor for single-timescale mode (default 0.99).
        dual_timescale: Enable fast+slow memory combination (default False).
        fast_horizon: Fast memory horizon in steps (default 200). gamma_fast = 1 - 1/horizon.
        slow_horizon: Slow memory horizon in steps (default 1000). gamma_slow = 1 - 1/horizon.
    """

    # Threshold for switching from sequential loop to chunked parallel cumsum.
    PARALLEL_THRESHOLD = 512

    def __init__(
        self,
        embed_dim: int,
        psi_dim: int = 256,
        decay_gamma: float = 0.99,
        dual_timescale: bool = False,
        fast_horizon: int = 200,
        slow_horizon: int = 1000,
    ):
        super().__init__()
        self.psi_dim = psi_dim
        self.decay_gamma = decay_gamma
        self.norm_clamp_c = math.sqrt(psi_dim)
        self.dual_timescale = dual_timescale

        # Delta MLP: h_t -> Delta_t
        self.delta_mlp = nn.Sequential(
            nn.Linear(embed_dim, embed_dim // 2),
            nn.GELU(),
            nn.Linear(embed_dim // 2, psi_dim),
        )

        # V2: Dual timescale parameters
        if dual_timescale:
            self.gamma_fast = 1.0 - (1.0 / fast_horizon)   # 0.995 for h=200
            self.gamma_slow = 1.0 - (1.0 / slow_horizon)   # 0.999 for h=1000
            # Learnable combination weights (initialized to equal)
            self.timescale_logits = nn.Parameter(torch.zeros(2))  # softmax → [0.5, 0.5]

    def _norm_clamp(self, psi: torch.Tensor) -> torch.Tensor:
        """Clamp Psi norm to ceiling c, preserving direction and magnitude below c.

        psi / max(1, ||psi|| / c)  -- identity when ||psi|| <= c, scales down otherwise.
        """
        norms = psi.norm(dim=-1, keepdim=True)
        scale = torch.clamp(norms / self.norm_clamp_c, min=1.0)
        return psi / scale

    def _sequential_forward(self, delta: torch.Tensor, gamma: float = None) -> torch.Tensor:
        """Sequential loop with per-step norm clamping. Used for T <= PARALLEL_THRESHOLD."""
        B, T, D = delta.shape
        if gamma is None:
            gamma = self.decay_gamma
        psi = torch.zeros(B, 1, D, device=delta.device, dtype=delta.dtype)
        psi_seq = []
        for t in range(T):
            psi = gamma * psi + delta[:, t : t + 1, :]
            psi = self._norm_clamp(psi)
            psi_seq.append(psi)
        return torch.cat(psi_seq, dim=1)  # [B, T, psi_dim]

    def _parallel_cumsum_chunk(
        self,
        delta_chunk: torch.Tensor,
        gamma: float,
        psi_carry: torch.Tensor,
    ) -> tuple:
        """Parallel discounted cumsum for a single chunk, with carry-in state.

        Args:
            delta_chunk: [B, C, D] — chunk of delta values.
            gamma: Decay factor.
            psi_carry: [B, 1, D] — carry-over state from previous chunk.

        Returns:
            psi_chunk: [B, C, D] — Psi values for this chunk (norm clamped).
            psi_last: [B, 1, D] — Last Psi value for carry-over to next chunk.
        """
        B, C, D = delta_chunk.shape

        # Geometric weights for this chunk
        powers = gamma ** torch.arange(C, device=delta_chunk.device, dtype=delta_chunk.dtype)
        powers = powers.unsqueeze(0).unsqueeze(-1)  # [1, C, 1]
        inv_powers = 1.0 / powers.clamp(min=1e-30)

        # Discounted cumsum within chunk
        delta_scaled = delta_chunk * inv_powers
        cumsum = torch.cumsum(delta_scaled, dim=1)
        psi_from_delta = cumsum * powers  # [B, C, D]

        # Add carry-over: psi_carry decays geometrically across the chunk
        # carry contribution at position t: gamma^(t+1) * psi_carry
        carry_powers = gamma ** torch.arange(1, C + 1, device=delta_chunk.device, dtype=delta_chunk.dtype)
        carry_powers = carry_powers.unsqueeze(0).unsqueeze(-1)  # [1, C, 1]
        psi_chunk = psi_from_delta + psi_carry * carry_powers

        # Per-chunk norm clamping — matches sequential semantics
        psi_chunk = self._norm_clamp(psi_chunk)

        psi_last = psi_chunk[:, -1:, :]  # [B, 1, D]
        return psi_chunk, psi_last

    def _chunked_parallel_forward(self, delta: torch.Tensor, gamma: float = None) -> torch.Tensor:
        """Chunked parallel discounted cumsum with per-chunk norm clamping.

        Processes long sequences in PARALLEL_THRESHOLD-sized chunks. Within each
        chunk, uses O(C) parallel cumsum. Between chunks, chains the carry-over
        state. Norm clamping at chunk boundaries preserves the saturation dynamics
        of the sequential path.

        This is O(T) compute with O(PARALLEL_THRESHOLD) sequential depth,
        matching sequential behavior while keeping GPU parallelism.
        """
        B, T, D = delta.shape
        if gamma is None:
            gamma = self.decay_gamma
        chunk_size = self.PARALLEL_THRESHOLD

        psi_carry = torch.zeros(B, 1, D, device=delta.device, dtype=delta.dtype)
        psi_parts = []

        for start in range(0, T, chunk_size):
            end = min(start + chunk_size, T)
            delta_chunk = delta[:, start:end, :]
            psi_chunk, psi_carry = self._parallel_cumsum_chunk(delta_chunk, gamma, psi_carry)
            psi_parts.append(psi_chunk)

        return torch.cat(psi_parts, dim=1)  # [B, T, D]

    def forward(self, h: torch.Tensor) -> tuple:
        """
        Compute Psi state sequence from hidden states.

        Args:
            h: [B, T, embed_dim] -- full sequence of hidden states from backbone.

        Returns:
            psi: [B, T, psi_dim] -- Psi state trajectory.
            delta: [B, T, psi_dim] -- Delta sequence (for regularizers).
        """
        delta = self.delta_mlp(h)  # [B, T, psi_dim]
        T = delta.size(1)

        if self.dual_timescale:
            # V2: Dual timescale — compute fast and slow accumulators
            weights = torch.softmax(self.timescale_logits, dim=0)
            psi_fast = self._evolve(delta, T, self.gamma_fast)
            psi_slow = self._evolve(delta, T, self.gamma_slow)
            psi = weights[0] * psi_fast + weights[1] * psi_slow
        else:
            psi = self._evolve(delta, T, self.decay_gamma)

        return psi, delta

    def _evolve(self, delta: torch.Tensor, T: int, gamma: float) -> torch.Tensor:
        """Run state evolution with the appropriate method for sequence length."""
        if T <= self.PARALLEL_THRESHOLD:
            return self._sequential_forward(delta, gamma)
        else:
            return self._chunked_parallel_forward(delta, gamma)

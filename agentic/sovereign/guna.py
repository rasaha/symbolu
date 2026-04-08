"""
Sovereign-1 Guna Computer: Hardened Cognitive State Dynamics
=============================================================

The Guna Computer derives the 16-D Guna Pulse from attention patterns
and hidden states. This replaces placeholder math with robust,
physically-grounded computations.

The Three Gunas (Sanskrit: qualities/attributes):
- Sattva (Clarity): Shannon Entropy of attention distribution
- Rajas (Motion): Variance of head outputs (activation energy)
- Tamas (Inertia): Cosine similarity to previous token state

Key Property: Conservation of Guna Energy
-----------------------------------------
Sum(Sattva, Rajas, Tamas) = 1.0 (enforced via softmax)
This ensures the system is always in a valid cognitive state.

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 2.4.2
"""

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class SovereignGunaComputer(nn.Module):
    """
    Computes the 16-D Guna Pulse from attention and hidden states.

    Hardened implementation using information-theoretic measures:
    - Sattva: Shannon Entropy (measure of attention clarity)
    - Rajas: Variance across heads (measure of activation energy)
    - Tamas: Cosine similarity to previous state (measure of inertia)

    All outputs are normalized via softmax to ensure conservation.
    """

    def __init__(
        self,
        embed_dim: int = 768,
        num_heads: int = 12,
        max_seq_len: int = 8192,
    ):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        # Maximum entropy for normalization (entropy of uniform distribution)
        # For a sequence of length N, max entropy is log(N)
        self.register_buffer(
            'max_entropy_base',
            torch.tensor(math.log(max_seq_len))
        )

        # Learnable temperature for softmax normalization
        self.temperature = nn.Parameter(torch.ones(1))

        # Output projection to expand 3D Guna to 16D
        self.guna_expand = nn.Linear(3, 16, bias=False)

        # Initialize expansion to preserve Guna structure
        # Sattva -> dims 0-4, Rajas -> dims 5-9, Tamas -> dims 10-15
        with torch.no_grad():
            expand_weight = torch.zeros(16, 3)
            expand_weight[0:5, 0] = 1.0 / 5  # Sattva
            expand_weight[5:10, 1] = 1.0 / 5  # Rajas
            expand_weight[10:16, 2] = 1.0 / 6  # Tamas
            self.guna_expand.weight.copy_(expand_weight)

    def compute_sattva(
        self,
        attention_weights: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Sattva (Clarity) from Shannon Entropy of attention.

        Sattva = 1 - H(attention) / H_max

        High Sattva = focused attention (low entropy)
        Low Sattva = dispersed attention (high entropy)

        Args:
            attention_weights: [B, H, N, N] attention probability matrix

        Returns:
            [B] Sattva scores in [0, 1]
        """
        B, H, N, _ = attention_weights.shape

        # Clamp to avoid log(0)
        attn = attention_weights.clamp(min=1e-9)

        # Shannon Entropy: H = -Σ p * log(p)
        entropy = -(attn * torch.log(attn)).sum(dim=-1)  # [B, H, N]

        # Average over heads and positions
        mean_entropy = entropy.mean(dim=[1, 2])  # [B]

        # Normalize by maximum possible entropy (log(N))
        max_entropy = torch.log(torch.tensor(N, dtype=torch.float, device=attn.device))
        normalized_entropy = mean_entropy / max_entropy.clamp(min=1e-9)

        # Sattva = 1 - normalized_entropy
        # High entropy → Low Sattva (dispersed)
        # Low entropy → High Sattva (focused)
        sattva = 1.0 - normalized_entropy.clamp(0, 1)

        return sattva

    def compute_rajas(
        self,
        head_outputs: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute Rajas (Motion/Energy) from Variance of head outputs.

        Rajas = σ²(head_outputs) / σ²_max

        High Rajas = high variance across heads (energetic processing)
        Low Rajas = uniform head outputs (quiescent)

        Args:
            head_outputs: [B, H, N, d] outputs from each attention head
                         before concatenation

        Returns:
            [B] Rajas scores in [0, 1]
        """
        B, H, N, d = head_outputs.shape

        # Variance across heads for each position
        # First compute mean across heads
        mean_output = head_outputs.mean(dim=1, keepdim=True)  # [B, 1, N, d]

        # Variance across heads: Var = E[(X - μ)²]
        variance = ((head_outputs - mean_output) ** 2).mean(dim=1)  # [B, N, d]

        # Average variance across positions and dimensions
        mean_variance = variance.mean(dim=[1, 2])  # [B]

        # Normalize: assume max variance is around 1.0 for normalized vectors
        # Use sigmoid for smooth [0, 1] mapping
        rajas = torch.sigmoid(mean_variance * 2 - 1)

        return rajas

    def compute_tamas(
        self,
        hidden_states: torch.Tensor,
        prev_hidden_states: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute Tamas (Inertia) from Cosine Similarity to previous state.

        Tamas = CosSim(h_t, h_{t-1})

        High Tamas = high similarity to previous (inertial/stable)
        Low Tamas = large change from previous (dynamic)

        Args:
            hidden_states: [B, N, D] current hidden states
            prev_hidden_states: [B, N, D] or [B, D] previous states (optional)

        Returns:
            [B] Tamas scores in [0, 1]
        """
        B, N, D = hidden_states.shape

        if prev_hidden_states is None:
            # No previous state: assume neutral Tamas
            return torch.full((B,), 0.5, device=hidden_states.device)

        # Handle different prev_hidden shapes
        if prev_hidden_states.dim() == 2:
            prev_hidden_states = prev_hidden_states.unsqueeze(1)

        if prev_hidden_states.shape[1] != N:
            # Use last position of previous for comparison with first of current
            prev_rep = prev_hidden_states[:, -1:, :].expand(-1, N, -1)
        else:
            prev_rep = prev_hidden_states

        # Cosine similarity between current and previous
        # Compute element-wise for each position, then average
        curr_norm = F.normalize(hidden_states, p=2, dim=-1)
        prev_norm = F.normalize(prev_rep, p=2, dim=-1)

        similarity = (curr_norm * prev_norm).sum(dim=-1)  # [B, N]

        # Average across positions
        tamas = similarity.mean(dim=1)  # [B]

        # Ensure [0, 1] range
        tamas = (tamas + 1) / 2  # Convert from [-1, 1] to [0, 1]

        return tamas.clamp(0, 1)

    def forward(
        self,
        attention_weights: Optional[torch.Tensor] = None,
        head_outputs: Optional[torch.Tensor] = None,
        hidden_states: Optional[torch.Tensor] = None,
        prev_hidden_states: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute full 16-D Guna Pulse.

        Args:
            attention_weights: [B, H, N, N] attention probability matrix
            head_outputs: [B, H, N, d] per-head outputs before concat
            hidden_states: [B, N, D] current hidden states
            prev_hidden_states: [B, N, D] previous hidden states

        Returns:
            Dict with:
                - guna: [B, 16] full Guna pulse
                - guna_3d: [B, 3] raw (Sattva, Rajas, Tamas)
                - sattva: [B] Sattva component
                - rajas: [B] Rajas component
                - tamas: [B] Tamas component
        """
        device = hidden_states.device if hidden_states is not None else \
                 attention_weights.device if attention_weights is not None else \
                 head_outputs.device
        B = hidden_states.shape[0] if hidden_states is not None else \
            attention_weights.shape[0] if attention_weights is not None else \
            head_outputs.shape[0]

        # Compute each Guna component
        if attention_weights is not None:
            sattva = self.compute_sattva(attention_weights)
        else:
            sattva = torch.full((B,), 0.33, device=device)

        if head_outputs is not None:
            rajas = self.compute_rajas(head_outputs)
        elif hidden_states is not None:
            # Estimate from hidden state variance
            rajas = torch.sigmoid(hidden_states.var(dim=-1).mean(dim=-1) * 2 - 1)
        else:
            rajas = torch.full((B,), 0.33, device=device)

        tamas = self.compute_tamas(hidden_states, prev_hidden_states)

        # Stack and normalize via softmax (conservation of Guna energy)
        guna_raw = torch.stack([sattva, rajas, tamas], dim=-1)  # [B, 3]

        # Apply temperature-scaled softmax for normalization
        guna_3d = F.softmax(guna_raw / self.temperature, dim=-1)  # [B, 3]

        # Expand to 16D
        guna = self.guna_expand(guna_3d)  # [B, 16]

        return {
            'guna': guna,
            'guna_3d': guna_3d,
            'sattva': guna_3d[:, 0],
            'rajas': guna_3d[:, 1],
            'tamas': guna_3d[:, 2],
        }


class GunaMonitor:
    """
    Utility class for monitoring Guna dynamics during training/inference.

    Tracks Guna evolution over time and detects anomalies:
    - Guna collapse (one component dominating)
    - Guna oscillation (rapid changes)
    - Guna stagnation (no change over many steps)
    """

    def __init__(
        self,
        collapse_threshold: float = 0.9,
        oscillation_threshold: float = 0.3,
        stagnation_window: int = 10,
    ):
        self.collapse_threshold = collapse_threshold
        self.oscillation_threshold = oscillation_threshold
        self.stagnation_window = stagnation_window

        self.history: list = []

    def update(self, guna_3d: torch.Tensor) -> Dict[str, bool]:
        """
        Update monitor with new Guna reading.

        Args:
            guna_3d: [B, 3] or [3] Guna values (Sattva, Rajas, Tamas)

        Returns:
            Dict with anomaly flags
        """
        if guna_3d.dim() == 2:
            guna_3d = guna_3d.mean(dim=0)

        guna_np = guna_3d.detach().cpu().numpy()
        self.history.append(guna_np)

        # Limit history size
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return self.check_anomalies()

    def check_anomalies(self) -> Dict[str, bool]:
        """Check for Guna anomalies."""
        if len(self.history) < 2:
            return {'collapse': False, 'oscillation': False, 'stagnation': False}

        current = self.history[-1]

        # Collapse: one Guna > threshold
        collapse = any(g > self.collapse_threshold for g in current)

        # Oscillation: large change from previous
        prev = self.history[-2]
        oscillation = sum(abs(c - p) for c, p in zip(current, prev)) > self.oscillation_threshold

        # Stagnation: no significant change over window
        stagnation = False
        if len(self.history) >= self.stagnation_window:
            window = self.history[-self.stagnation_window:]
            total_change = 0
            for i in range(1, len(window)):
                total_change += sum(abs(window[i][j] - window[i-1][j]) for j in range(3))
            stagnation = total_change < 0.05

        return {
            'collapse': collapse,
            'oscillation': oscillation,
            'stagnation': stagnation,
        }

    def get_dominant_guna(self) -> str:
        """Get the currently dominant Guna."""
        if not self.history:
            return "unknown"

        current = self.history[-1]
        names = ["sattva", "rajas", "tamas"]
        return names[int(current.argmax())]

    def get_statistics(self) -> Dict[str, float]:
        """Get statistics over the history window."""
        if len(self.history) < 2:
            return {}

        import numpy as np
        history_np = np.array(self.history)

        return {
            'sattva_mean': float(history_np[:, 0].mean()),
            'sattva_std': float(history_np[:, 0].std()),
            'rajas_mean': float(history_np[:, 1].mean()),
            'rajas_std': float(history_np[:, 1].std()),
            'tamas_mean': float(history_np[:, 2].mean()),
            'tamas_std': float(history_np[:, 2].std()),
        }

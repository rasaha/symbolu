"""
ExperientialLossSignal: Multi-modal, cross-frequency loss for CG training.

Current AI loss is a scalar — it has no texture. To approximate embodiment,
loss must propagate differently across modalities simultaneously. Error in a
semantic prediction also affects a rhythmic/temporal stream and a
somatic-analog state vector.

This implements cross-modal, cross-frequency interference — not a clean
gradient but a wave of reorganization across the whole system. Maps directly
to FSCS (Frequency-Stratified Coherence Scoring) where different layers of
the signal carry different kinds of error, and loss at one frequency
resonates into others.

Loss Bands (explicit decomposition):
    L_token  = CE(logits, targets)               — semantic (high freq)
    L_temporal = ||smooth(h_t) - smooth(h_{t+1})||^2  — temporal (mid freq)
    L_coherence = 1 - cos(band_i, band_j)         — somatic (low freq)

Total:
    L_exp = w_s * L_semantic + w_t * L_temporal + w_c * L_somatic
          + λ_cross * Σ_{i≠j} C(L_i, L_j)
          + λ_latent * L_latent_alignment

Where C(L_i, L_j) is a low-rank bilinear coupling that forces error in one
band to resonate into others, and L_latent_alignment integrates feedback
from the model's coherence/latent state (CSR alignment).

State Feedback: The loss accepts optional coherence_state input from the
existing chitta-vritti / coherence pipeline, closing the feedback loop
between state estimation and loss computation.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ExperientialLossConfig:
    """Configuration for experiential multi-modal loss.

    Attributes:
        d_model: Model hidden dimension
        num_bands: Number of frequency bands (semantic, temporal, somatic)
        coupling_lambda: Weight for cross-frequency coupling terms
        semantic_weight: Weight for semantic (high-freq) band
        temporal_weight: Weight for temporal (mid-freq) band
        somatic_weight: Weight for somatic (low-freq) band
        coupling_rank: Rank of learned coupling matrices
        interference_decay: Decay rate for cross-band interference
        min_loss_texture: Minimum texture (prevents collapse to scalar)
    """
    d_model: int = 128
    num_bands: int = 3
    coupling_lambda: float = 0.1
    semantic_weight: float = 1.0
    temporal_weight: float = 0.5
    somatic_weight: float = 0.3
    coupling_rank: int = 16
    interference_decay: float = 0.9
    min_loss_texture: float = 1e-4
    latent_alignment_weight: float = 0.1


class FrequencyBandProjector(nn.Module):
    """Projects hidden states into frequency-specific error representations.

    Each band captures a different temporal scale of error:
    - Semantic: position-level, high-resolution error
    - Temporal: window-level, sequence coherence error
    - Somatic: global, system-wide consistency error
    """

    def __init__(self, d_model: int, d_band: int, band_type: str):
        super().__init__()
        self.band_type = band_type
        self.d_band = d_band

        self.proj = nn.Linear(d_model, d_band)

        if band_type == "temporal":
            # Causal conv for temporal smoothing
            self.temporal_smooth = nn.Conv1d(
                d_band, d_band, kernel_size=5, padding=2, groups=d_band
            )
        elif band_type == "somatic":
            # Global pooling + expansion for system-wide signal
            self.global_proj = nn.Sequential(
                nn.Linear(d_band, d_band),
                nn.Tanh(),
            )

        self._init_weights()

    def _init_weights(self):
        nn.init.xavier_normal_(self.proj.weight, gain=0.5)
        nn.init.zeros_(self.proj.bias)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """Project hidden states into band-specific representation.

        Args:
            hidden: [B, T, D] hidden states

        Returns:
            [B, T, d_band] band-specific error representation
        """
        x = self.proj(hidden)  # [B, T, d_band]

        if self.band_type == "temporal":
            # Apply temporal smoothing via causal conv
            x_t = x.transpose(1, 2)  # [B, d_band, T]
            x_t = self.temporal_smooth(x_t)
            x = x_t.transpose(1, 2)  # [B, T, d_band]
        elif self.band_type == "somatic":
            # Global mean then expand — somatic is system-wide
            global_signal = x.mean(dim=1, keepdim=True)  # [B, 1, d_band]
            global_signal = self.global_proj(global_signal)
            x = x + global_signal.expand_as(x)

        return x


class CrossFrequencyCoupling(nn.Module):
    """Learned coupling between frequency bands.

    When error occurs in one band, this module computes how much that error
    should resonate into other bands — creating the cross-modal interference
    that makes loss "embodied" rather than isolated.

    C(L_i, L_j) = L_i^T @ W_ij @ L_j (low-rank bilinear coupling)
    """

    def __init__(self, d_band: int, rank: int = 16):
        super().__init__()
        self.A = nn.Parameter(torch.randn(d_band, rank) * 0.01)
        self.B = nn.Parameter(torch.randn(d_band, rank) * 0.01)

    def forward(
        self, band_i: torch.Tensor, band_j: torch.Tensor
    ) -> torch.Tensor:
        """Compute coupling between two frequency bands.

        Args:
            band_i: [B, T, d_band] error representation from band i
            band_j: [B, T, d_band] error representation from band j

        Returns:
            Scalar coupling loss (interference magnitude)
        """
        # Low-rank bilinear: band_i^T @ A @ B^T @ band_j
        proj_i = band_i @ self.A  # [B, T, rank]
        proj_j = band_j @ self.B  # [B, T, rank]

        # Element-wise product then sum — measures cross-band interference
        coupling = (proj_i * proj_j).sum(dim=-1)  # [B, T]

        # Return mean absolute coupling as loss
        return coupling.abs().mean()


class ExperientialLossSignal(nn.Module):
    """Multi-modal, cross-frequency experiential loss.

    Replaces scalar loss with textured, multi-band loss that forces
    error in one modality to resonate across all modalities —
    approximating the embodied nature of experiential learning.

    Architecture:
        hidden -> [semantic_proj, temporal_proj, somatic_proj]
                       |              |              |
                  L_semantic     L_temporal      L_somatic
                       \\            |            /
                    Cross-Frequency Coupling C(L_i, L_j)
                              |
                    L_experiential = Σ w_b * L_b + λ * Σ C(L_i, L_j)

    Args:
        config: ExperientialLossConfig with hyperparameters
    """

    BAND_NAMES = ["semantic", "temporal", "somatic"]

    def __init__(self, config: ExperientialLossConfig):
        super().__init__()
        self.config = config
        d_band = config.d_model // config.num_bands

        # Frequency band projectors
        self.band_projectors = nn.ModuleDict({
            "semantic": FrequencyBandProjector(config.d_model, d_band, "semantic"),
            "temporal": FrequencyBandProjector(config.d_model, d_band, "temporal"),
            "somatic": FrequencyBandProjector(config.d_model, d_band, "somatic"),
        })

        # Per-band loss heads (project band repr to scalar loss)
        self.band_loss_heads = nn.ModuleDict({
            name: nn.Sequential(
                nn.Linear(d_band, d_band // 2),
                nn.GELU(),
                nn.Linear(d_band // 2, 1),
            )
            for name in self.BAND_NAMES
        })

        # Cross-frequency coupling matrices (one per band pair)
        self.couplings = nn.ModuleDict()
        for i, name_i in enumerate(self.BAND_NAMES):
            for j, name_j in enumerate(self.BAND_NAMES):
                if i < j:
                    key = f"{name_i}__{name_j}"
                    self.couplings[key] = CrossFrequencyCoupling(
                        d_band, config.coupling_rank
                    )

        # Band weights
        self.band_weights = {
            "semantic": config.semantic_weight,
            "temporal": config.temporal_weight,
            "somatic": config.somatic_weight,
        }

        # Latent alignment projection (state feedback)
        d_band = config.d_model // config.num_bands
        self.latent_alignment_proj = nn.Sequential(
            nn.Linear(config.d_model, d_band),
            nn.GELU(),
            nn.Linear(d_band, d_band),
        )

        # Running interference history (for temporal texture)
        self.register_buffer(
            "interference_ema",
            torch.zeros(config.num_bands),
        )

    def forward(
        self,
        hidden: torch.Tensor,
        target_hidden: torch.Tensor,
        base_loss: Optional[torch.Tensor] = None,
        coherence_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute experiential loss across frequency bands.

        Args:
            hidden: [B, T, D] predicted hidden states
            target_hidden: [B, T, D] target hidden states (or shifted)
            base_loss: Optional scalar base loss to modulate
            coherence_state: Optional [B, T, D] or [B, D] latent state from
                coherence/CSR pipeline. Closes the feedback loop between
                state estimation and loss computation.

        Returns:
            Dict with:
                'loss': Total experiential loss (scalar)
                'band_losses': {band_name: scalar} per-band losses
                'coupling_losses': {pair: scalar} cross-band coupling losses
                'loss_texture': [num_bands] per-band loss magnitudes
                'interference_magnitude': scalar cross-band interference
                'latent_alignment_loss': scalar latent alignment loss
        """
        # Compute error signal (difference between predicted and target)
        error = hidden - target_hidden  # [B, T, D]

        # Project error into each frequency band
        band_reprs = {}
        band_losses = {}
        loss_texture = []

        for name in self.BAND_NAMES:
            band_repr = self.band_projectors[name](error)  # [B, T, d_band]
            band_reprs[name] = band_repr

            # Per-band loss: mean of projected scalar
            band_scalar = self.band_loss_heads[name](band_repr)  # [B, T, 1]
            band_loss = band_scalar.squeeze(-1).pow(2).mean()
            band_losses[name] = band_loss
            loss_texture.append(band_loss.detach())

        # Cross-frequency coupling losses
        coupling_losses = {}
        total_coupling = torch.tensor(0.0, device=hidden.device)

        for i, name_i in enumerate(self.BAND_NAMES):
            for j, name_j in enumerate(self.BAND_NAMES):
                if i < j:
                    key = f"{name_i}__{name_j}"
                    c_loss = self.couplings[key](
                        band_reprs[name_i], band_reprs[name_j]
                    )
                    coupling_losses[key] = c_loss
                    total_coupling = total_coupling + c_loss

        # Weighted sum of band losses
        total_band_loss = sum(
            self.band_weights[name] * band_losses[name]
            for name in self.BAND_NAMES
        )

        # Latent alignment loss (state feedback from coherence pipeline)
        latent_alignment_loss = torch.tensor(0.0, device=hidden.device)
        if coherence_state is not None:
            # Project coherence state and compare with somatic band
            if coherence_state.dim() == 2:
                # [B, D] -> [B, 1, D] -> expand
                coherence_state = coherence_state.unsqueeze(1).expand_as(hidden)
            latent_proj = self.latent_alignment_proj(coherence_state)
            somatic_repr = band_reprs["somatic"]
            # Alignment: somatic error should agree with coherence state
            latent_alignment_loss = (1.0 - torch.cosine_similarity(
                latent_proj, somatic_repr, dim=-1
            )).mean()

        # Total experiential loss
        total_loss = (
            total_band_loss
            + self.config.coupling_lambda * total_coupling
            + self.config.latent_alignment_weight * latent_alignment_loss
        )

        # Add base loss modulation if provided
        if base_loss is not None:
            total_loss = total_loss + base_loss

        # Ensure minimum texture (prevents collapse to flat scalar)
        texture_tensor = torch.stack(loss_texture)
        texture_variance = texture_tensor.var()
        if texture_variance < self.config.min_loss_texture:
            total_loss = total_loss + self.config.min_loss_texture - texture_variance

        # Update interference EMA
        with torch.no_grad():
            self.interference_ema.mul_(self.config.interference_decay).add_(
                texture_tensor * (1 - self.config.interference_decay)
            )

        return {
            "loss": total_loss,
            "band_losses": band_losses,
            "coupling_losses": coupling_losses,
            "loss_texture": texture_tensor,
            "interference_magnitude": total_coupling.detach(),
            "interference_ema": self.interference_ema.clone(),
            "latent_alignment_loss": latent_alignment_loss.detach(),
        }

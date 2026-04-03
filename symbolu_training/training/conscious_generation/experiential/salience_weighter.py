"""
SalienceWeighter: Consequence-based error weighting for CG training.

Natural intelligence weights loss by existential stakes. AI weights loss
uniformly unless hand-engineered. To approximate this, the system needs
an internal model of what matters and why — learned through interaction
with consequence, not assigned externally.

Key principle: errors that cause downstream cascade failures should leave
deeper traces than isolated errors. The system develops "scar tissue" —
regions that are more carefully regulated because they've been burned before.

Salience Sources:
    1. Error magnitude — absolute size of the error
    2. Cascade depth — how many downstream steps the error affects
    3. Error recurrence — repeated errors in the same region
    4. Cross-modal impact — errors that affect multiple frequency bands
    5. Scar tissue — historical record of damaging errors per region

Weighting:
    w_salience(e) = magnitude(e) * cascade(e) * (1 + scar(region))

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class SalienceConfig:
    """Configuration for salience weighting.

    Attributes:
        d_model: Model dimension
        num_regions: Number of model regions to track
        cascade_depth: Number of downstream steps to track for cascade
        scar_decay: Decay rate for scar tissue (slow decay = long memory)
        scar_growth_rate: How fast scar tissue forms from errors
        recurrence_window: Steps to look back for recurrence detection
        magnitude_scale: Scaling for error magnitude contribution
        cascade_scale: Scaling for cascade depth contribution
        min_salience: Floor for salience (prevents zero weighting)
        max_salience: Ceiling for salience (prevents gradient explosion)
    """
    d_model: int = 128
    num_regions: int = 12
    cascade_depth: int = 4
    scar_decay: float = 0.999
    scar_growth_rate: float = 0.05
    recurrence_window: int = 50
    magnitude_scale: float = 1.0
    cascade_scale: float = 2.0
    min_salience: float = 0.01
    max_salience: float = 10.0


class CascadeTracker(nn.Module):
    """Tracks how errors propagate downstream through model regions.

    An error at region l affects region l+1, l+2, etc. with diminishing
    but non-zero impact. Errors that cause deep cascades are more
    consequential than isolated errors.

    Cascade is estimated via a simple causal attention mechanism:
    each region attends to all upstream regions' error signals.
    """

    def __init__(self, d_model: int, num_regions: int, cascade_depth: int = 4):
        super().__init__()
        self.num_regions = num_regions
        self.cascade_depth = cascade_depth

        # Causal cascade attention: region l attends to regions < l
        self.cascade_proj = nn.Linear(d_model, d_model)
        self.cascade_gate = nn.Linear(d_model * 2, 1)

        # Causal mask (lower triangular)
        mask = torch.tril(torch.ones(num_regions, num_regions))
        # Limit cascade depth
        for i in range(num_regions):
            for j in range(num_regions):
                if i - j > cascade_depth:
                    mask[i, j] = 0.0
        self.register_buffer("causal_mask", mask)

    def forward(self, error_per_region: torch.Tensor) -> torch.Tensor:
        """Estimate cascade depth of errors.

        Args:
            error_per_region: [B, num_regions, D] error signal per region

        Returns:
            cascade_scores: [B, num_regions] cascade depth in [0, 1]
        """
        B, R, D = error_per_region.shape

        # Project errors
        projected = self.cascade_proj(error_per_region)  # [B, R, D]

        # Compute cascade via causal attention
        # Attention: [B, R, R] = projected @ projected^T
        attn = torch.bmm(projected, projected.transpose(1, 2))  # [B, R, R]
        attn = attn / (D ** 0.5)

        # Apply causal mask
        attn = attn.masked_fill(self.causal_mask.unsqueeze(0) == 0, float("-inf"))
        attn = torch.softmax(attn, dim=-1)

        # Cascade score: how much upstream error flows to each region
        error_norms = error_per_region.norm(dim=-1, keepdim=True)  # [B, R, 1]
        cascade_flow = torch.bmm(attn, error_norms).squeeze(-1)  # [B, R]

        # Normalize to [0, 1]
        cascade_scores = torch.sigmoid(cascade_flow)

        return cascade_scores


class ScarTissueRegistry:
    """Persistent record of regions that have been damaged by errors.

    Scar tissue forms slowly when a region experiences repeated high-magnitude
    errors. It decays very slowly — the system remembers where it's been
    burned. Scarred regions get higher salience weighting, meaning future
    errors there are treated as more consequential.
    """

    def __init__(self, num_regions: int, decay: float = 0.999, growth_rate: float = 0.05):
        self.num_regions = num_regions
        self.decay = decay
        self.growth_rate = growth_rate
        self.scar_tissue = torch.zeros(num_regions)
        self.error_counts = torch.zeros(num_regions, dtype=torch.long)

    def update(self, error_magnitudes: torch.Tensor) -> None:
        """Update scar tissue from observed error magnitudes.

        Args:
            error_magnitudes: [num_regions] mean error magnitude per region
        """
        # Decay existing scar tissue (very slow)
        self.scar_tissue *= self.decay

        # Grow scar tissue where errors are large
        growth = self.growth_rate * error_magnitudes.detach().cpu()
        self.scar_tissue += growth

        # Clamp to [0, 1]
        self.scar_tissue = self.scar_tissue.clamp(0.0, 1.0)

        # Track error counts
        self.error_counts += (error_magnitudes.detach().cpu() > 0.1).long()

    def get_scar_levels(self) -> torch.Tensor:
        """Get current scar tissue levels per region."""
        return self.scar_tissue.clone()

    def get_most_scarred(self, k: int = 3) -> list:
        """Get the k most scarred regions."""
        values, indices = self.scar_tissue.topk(k)
        return list(zip(indices.tolist(), values.tolist()))


class SalienceWeighter(nn.Module):
    """Consequence-based error weighting with scar tissue memory.

    Computes per-region salience weights that modulate how deeply
    errors are allowed to restructure the model. High-consequence
    errors (large, cascading, recurring, in scarred regions) get
    amplified; trivial errors are attenuated.

    w(e, r) = magnitude(e) * (1 + cascade(e)) * (1 + scar(r)) * recurrence(r)

    Args:
        config: SalienceConfig
    """

    def __init__(self, config: SalienceConfig):
        super().__init__()
        self.config = config

        self.cascade_tracker = CascadeTracker(
            config.d_model, config.num_regions, config.cascade_depth
        )
        self.scar_registry = ScarTissueRegistry(
            config.num_regions, config.scar_decay, config.scar_growth_rate
        )

        # Recurrence detection: sliding window of error magnitudes per region
        self.register_buffer(
            "error_window",
            torch.zeros(config.recurrence_window, config.num_regions),
        )
        self.register_buffer(
            "window_ptr", torch.tensor(0, dtype=torch.long)
        )

        # Learned salience modulation
        self.salience_proj = nn.Sequential(
            nn.Linear(3, 16),  # magnitude, cascade, scar
            nn.GELU(),
            nn.Linear(16, 1),
            nn.Softplus(),
        )

    def forward(
        self,
        error_signal: torch.Tensor,
        cross_modal_impact: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute salience weights for error signals.

        Args:
            error_signal: [B, num_regions, D] error per region
            cross_modal_impact: Optional [B, num_regions] cross-band impact

        Returns:
            Dict with:
                'salience_weights': [B, num_regions] per-region weights
                'cascade_scores': [B, num_regions] cascade depth
                'scar_levels': [num_regions] scar tissue levels
                'recurrence': [num_regions] recurrence scores
        """
        B = error_signal.shape[0]
        device = error_signal.device

        # 1. Error magnitude
        magnitude = error_signal.norm(dim=-1)  # [B, num_regions]
        mean_magnitude = magnitude.mean(dim=0)  # [num_regions]

        # 2. Cascade depth
        cascade_scores = self.cascade_tracker(error_signal)  # [B, num_regions]

        # 3. Scar tissue
        scar_levels = self.scar_registry.get_scar_levels().to(device)

        # 4. Recurrence detection
        recurrence = self._compute_recurrence(mean_magnitude)

        # Update scar tissue and error window
        with torch.no_grad():
            self.scar_registry.update(mean_magnitude)
            self._update_error_window(mean_magnitude)

        # Compose salience features
        features = torch.stack([
            magnitude * self.config.magnitude_scale,
            cascade_scores * self.config.cascade_scale,
            scar_levels.unsqueeze(0).expand(B, -1),
        ], dim=-1)  # [B, num_regions, 3]

        # Learned salience modulation
        raw_salience = self.salience_proj(features).squeeze(-1)  # [B, num_regions]

        # Boost from recurrence
        raw_salience = raw_salience * (1.0 + recurrence.unsqueeze(0))

        # Boost from cross-modal impact
        if cross_modal_impact is not None:
            raw_salience = raw_salience * (1.0 + 0.5 * cross_modal_impact)

        # Clamp to [min, max]
        salience_weights = raw_salience.clamp(
            self.config.min_salience, self.config.max_salience
        )

        return {
            "salience_weights": salience_weights,
            "cascade_scores": cascade_scores,
            "scar_levels": scar_levels,
            "recurrence": recurrence,
            "mean_magnitude": mean_magnitude,
        }

    def _compute_recurrence(self, current_magnitude: torch.Tensor) -> torch.Tensor:
        """Detect recurring error patterns from sliding window.

        Args:
            current_magnitude: [num_regions] current error magnitudes

        Returns:
            recurrence: [num_regions] recurrence score in [0, 1]
        """
        # Count steps in window where magnitude was above threshold
        threshold = 0.1
        active_steps = (self.error_window > threshold).float().sum(dim=0)
        recurrence = active_steps / self.config.recurrence_window
        return recurrence

    def _update_error_window(self, magnitude: torch.Tensor) -> None:
        """Update sliding window of error magnitudes."""
        ptr = self.window_ptr.item()
        self.error_window[ptr % self.config.recurrence_window] = magnitude.detach()
        self.window_ptr += 1

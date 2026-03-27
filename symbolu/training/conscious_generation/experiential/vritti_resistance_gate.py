"""
VrittiResistanceGate: Vritti-gated update mechanism for CG training.

Continuous plasticity scaling — no binary branching. Gradients are scaled
by the product of salience and resistance openness:

    g_eff = s_t * r_t * g

Where:
    s_t = salience (computed independently)
    r_t = resistance openness in [0, 1] (from vritti field)
    g = raw gradient

Gates are:
    - State-dependent: High vritti activation in a region resists update
    - Stake-sensitive: Consequential errors force gates open
    - Temporally variable: Resistance rises and falls like emotional states
    - Damped: Bounded gain prevents oscillation/instability

Stability Constraints:
    - Max gain clamped to prevent gradient explosion
    - EMA smoothing on resistance prevents discontinuities
    - Damping coefficient ensures bounded control loop behavior

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class VrittiResistanceConfig:
    """Configuration for vritti resistance gating.

    Attributes:
        d_model: Model dimension
        num_regions: Number of gatable regions in the model
        num_vritti_modes: Number of vritti cognitive modes (5 classical)
        gate_temperature: Temperature for gate sigmoid (lower = sharper)
        resistance_decay: Temporal decay of resistance state
        resistance_floor: Minimum resistance (prevents zero-resistance)
        resistance_ceiling: Maximum resistance (prevents total lockout)
        adaptation_rate: How fast resistance adapts to update patterns
        max_gain: Maximum plasticity gain (stability constraint)
        damping: Damping coefficient for resistance dynamics
    """
    d_model: int = 128
    num_regions: int = 12
    num_vritti_modes: int = 5
    gate_temperature: float = 0.5
    resistance_decay: float = 0.95
    resistance_floor: float = 0.05
    resistance_ceiling: float = 0.95
    adaptation_rate: float = 0.01
    max_gain: float = 3.0
    damping: float = 0.1


class VrittiFieldEstimator(nn.Module):
    """Estimates the current vritti (cognitive mode) field for each region.

    The vritti field represents the cognitive state of a model region —
    akin to the psychological resistance a human experiences when
    confronted with information that challenges their current understanding.

    High vritti activation = the region is in a coherent cognitive state
    and resists perturbation. Low activation = the region is in flux
    and more receptive to updates.

    Maps to Patanjali's 5 vrittis:
        0: Pramana (valid cognition) - high resistance, correctly configured
        1: Viparyaya (misperception) - low resistance, needs correction
        2: Vikalpa (conceptual branching) - medium resistance, exploring
        3: Smrti (memory) - high resistance, consolidated pattern
        4: Nidra (dormancy) - low resistance, inactive region
    """

    def __init__(self, d_model: int, num_regions: int, num_vritti: int = 5):
        super().__init__()
        self.num_regions = num_regions
        self.num_vritti = num_vritti

        # Per-region vritti classifier: region_state -> vritti distribution
        self.vritti_classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, num_vritti),
        )

        # Vritti-to-resistance mapping (learned, initialized with priors)
        # Pramana/Smrti = high resistance, Viparyaya/Nidra = low
        default_resistance = torch.tensor([0.8, 0.2, 0.5, 0.8, 0.2])
        self.vritti_resistance = nn.Parameter(
            default_resistance[:num_vritti].clone()
        )

        self._init_weights()

    def _init_weights(self):
        for layer in self.vritti_classifier:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight, gain=0.3)
                nn.init.zeros_(layer.bias)

    def forward(
        self, region_states: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Estimate vritti field and resistance for each region.

        Args:
            region_states: [B, num_regions, D] state per region

        Returns:
            vritti_dist: [B, num_regions, num_vritti] vritti probabilities
            resistance: [B, num_regions] resistance level per region
        """
        # Classify each region's cognitive mode
        vritti_logits = self.vritti_classifier(region_states)
        vritti_dist = torch.softmax(vritti_logits, dim=-1)

        # Compute resistance as weighted sum of vritti-specific resistances
        resistance = (vritti_dist * self.vritti_resistance.unsqueeze(0).unsqueeze(0)).sum(dim=-1)

        return vritti_dist, resistance


class StakesEstimator(nn.Module):
    """Estimates the stakes (consequence level) of a given error signal.

    High-stakes errors = errors that, if not corrected, would cause
    downstream cascade failures. These should force resistance gates open.

    Stakes are estimated from:
        1. Error magnitude (absolute size of gradient)
        2. Error coherence (is the error consistent across the batch?)
        3. Historical error pattern (is this a recurring error?)
    """

    def __init__(self, d_model: int, num_regions: int):
        super().__init__()
        self.stakes_proj = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.GELU(),
            nn.Linear(d_model // 4, 1),
            nn.Sigmoid(),
        )
        self._init_weights()

    def _init_weights(self):
        for layer in self.stakes_proj:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_normal_(layer.weight, gain=0.3)
                nn.init.zeros_(layer.bias)

    def forward(
        self, error_signal: torch.Tensor, error_history: Optional[torch.Tensor] = None
    ) -> torch.Tensor:
        """Estimate stakes from error signal.

        Args:
            error_signal: [B, num_regions, D] per-region error
            error_history: Optional [num_regions] historical error magnitude

        Returns:
            stakes: [B, num_regions] stakes level per region in [0, 1]
        """
        stakes = self.stakes_proj(error_signal).squeeze(-1)

        # Boost stakes for historically problematic regions
        if error_history is not None:
            history_boost = error_history.unsqueeze(0)  # [1, num_regions]
            stakes = stakes + 0.1 * history_boost
            stakes = stakes.clamp(0.0, 1.0)

        return stakes


class VrittiResistanceGate(nn.Module):
    """Continuous plasticity scaling via vritti resistance field.

    NO binary branching. All updates flow through — scaled by the
    product of independent salience and resistance signals:

        plasticity = s_t * r_t
        g_eff = clamp(plasticity, 0, max_gain) * g

    Stability constraints:
        - Max gain bounded to prevent gradient explosion
        - EMA smoothing on resistance prevents discontinuities
        - Damping term prevents oscillation in the control loop

    The deferred sample buffer records high-salience, low-plasticity
    samples for periodic replay — but this is a SECONDARY diagnostic
    mechanism, not a branching decision.

    Args:
        config: VrittiResistanceConfig
    """

    def __init__(self, config: VrittiResistanceConfig):
        super().__init__()
        self.config = config

        self.vritti_estimator = VrittiFieldEstimator(
            config.d_model, config.num_regions, config.num_vritti_modes
        )
        self.stakes_estimator = StakesEstimator(config.d_model, config.num_regions)

        # Persistent resistance state (EMA-smoothed, evolves across steps)
        self.register_buffer(
            "persistent_resistance",
            torch.full((config.num_regions,), 0.5),
        )

        # Error history for scar tissue effect
        self.register_buffer(
            "error_history",
            torch.zeros(config.num_regions),
        )

        # Deferred sample buffer: high-salience, low-plasticity samples
        # for periodic replay (not a branching mechanism)
        self.deferred_buffer: list = []
        self._deferred_capacity = 256

    def forward(
        self,
        region_states: torch.Tensor,
        error_signal: torch.Tensor,
        proposed_update: torch.Tensor,
        salience_weights: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Scale proposed updates via continuous plasticity field.

        The effective gradient is:
            g_eff = plasticity * proposed_update

        Where plasticity = clamp(salience * resistance_openness, 0, max_gain)

        Salience and resistance are computed INDEPENDENTLY and composed
        multiplicatively — neither determines the other.

        Args:
            region_states: [B, num_regions, D] current state per region
            error_signal: [B, num_regions, D] error signal per region
            proposed_update: [B, num_regions, D] proposed gradient update
            salience_weights: Optional [B, num_regions] external salience
                              (if None, stakes estimator is used)

        Returns:
            Dict with:
                'gated_update': [B, num_regions, D] plasticity-scaled update
                'plasticity': [B, num_regions] effective plasticity in [0, max_gain]
                'resistance': [B, num_regions] resistance per region
                'resistance_openness': [B, num_regions] 1 - resistance (gate values)
                'stakes': [B, num_regions] stakes per region
                'vritti_dist': [B, num_regions, num_vritti] vritti probs
                'deferred_count': items added to deferred buffer this step
        """
        B = region_states.shape[0]

        # === Independent signal 1: Resistance field ===
        vritti_dist, instantaneous_resistance = self.vritti_estimator(region_states)

        # EMA-smooth with persistent state (prevents discontinuities)
        resistance = (
            (1 - self.config.damping) * instantaneous_resistance
            + self.config.damping * self.persistent_resistance.unsqueeze(0)
        )

        # Clamp resistance to [floor, ceiling]
        resistance = resistance.clamp(
            self.config.resistance_floor, self.config.resistance_ceiling
        )

        # Resistance openness: how much this region allows updates
        resistance_openness = 1.0 - resistance  # [B, num_regions] in [0, 1]

        # === Independent signal 2: Stakes/Salience ===
        stakes = self.stakes_estimator(error_signal, self.error_history)

        if salience_weights is not None:
            # Use externally-provided salience (from SalienceWeighter)
            effective_salience = salience_weights
        else:
            effective_salience = stakes

        # === Compose: continuous plasticity = salience * openness ===
        # Both signals are independent; neither determines the other
        plasticity = effective_salience * resistance_openness

        # Stability constraint: bound the gain
        plasticity = plasticity.clamp(0.0, self.config.max_gain)

        # Apply plasticity scaling to proposed update
        gated_update = proposed_update * plasticity.unsqueeze(-1)

        # === Secondary: record deferred samples for replay ===
        deferred_count = 0
        with torch.no_grad():
            # High salience but low plasticity = worth replaying later
            high_salience = effective_salience > 0.5
            low_plasticity = plasticity < 0.2
            defer_mask = high_salience & low_plasticity

            if defer_mask.any() and len(self.deferred_buffer) < self._deferred_capacity:
                for b in range(B):
                    defer_regions = defer_mask[b].nonzero(as_tuple=True)[0]
                    if len(defer_regions) > 0:
                        self.deferred_buffer.append({
                            "error": error_signal[b, defer_regions].detach().cpu(),
                            "regions": defer_regions.detach().cpu(),
                            "salience": effective_salience[b, defer_regions].mean().item(),
                        })
                        deferred_count += len(defer_regions)

            # Update persistent resistance (EMA dynamics)
            mean_resistance = resistance.mean(dim=0).detach()
            self.persistent_resistance.mul_(self.config.resistance_decay).add_(
                mean_resistance * (1 - self.config.resistance_decay)
            )

            # Update error history (scar tissue)
            error_magnitude = error_signal.norm(dim=-1).mean(dim=0).detach()
            self.error_history.mul_(0.99).add_(error_magnitude * 0.01)

        return {
            "gated_update": gated_update,
            "plasticity": plasticity,
            "resistance": resistance,
            "resistance_openness": resistance_openness,
            "stakes": stakes,
            "vritti_dist": vritti_dist,
            "deferred_count": deferred_count,
        }

    def drain_deferred_buffer(self) -> list:
        """Drain and return deferred samples for periodic replay.

        Returns:
            List of deferred items (dicts with error, regions, salience)
        """
        items = list(self.deferred_buffer)
        self.deferred_buffer.clear()
        return items

    def get_resistance_state(self) -> Dict[str, torch.Tensor]:
        """Get current resistance state for diagnostics."""
        return {
            "persistent_resistance": self.persistent_resistance.clone(),
            "error_history": self.error_history.clone(),
            "deferred_depth": len(self.deferred_buffer),
        }

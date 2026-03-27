"""
VrittiResistanceGate: Vritti-gated update mechanism for CG training.

The most radical analog — instead of loss propagating freely through all
weights, resistance fields gate how much a given update restructures a
given region.

Gates are:
    - State-dependent: High vritti activation in a region resists update
    - Stake-sensitive: Consequential errors force gates open
    - Temporally variable: Resistance rises and falls like emotional states

This extends the Reflective Latent Block (RLB) concept — the reflection
loop before committing an update mirrors the pause before a human
integrates a difficult truth. The missing piece: gates must be EARNED
open by sufficient error magnitude, not just architecturally present.

Gate Mechanics:
    r_t = vritti_field(region_state)           # Current resistance
    s_t = salience(error_magnitude)            # Stakes of this error
    gate = sigmoid((s_t - r_t) / temperature)  # Open only if stakes > resistance
    effective_grad = gate * raw_grad            # Gated gradient

Temporal Dynamics:
    r_{t+1} = decay * r_t + (1-decay) * update_impact  # Resistance evolves

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
        stakes_threshold: Minimum stakes to attempt gate opening
        adaptation_rate: How fast resistance adapts to update patterns
        queue_capacity: Max items in consolidation queue
    """
    d_model: int = 128
    num_regions: int = 12
    num_vritti_modes: int = 5
    gate_temperature: float = 0.5
    resistance_decay: float = 0.95
    resistance_floor: float = 0.05
    resistance_ceiling: float = 0.95
    stakes_threshold: float = 0.1
    adaptation_rate: float = 0.01
    queue_capacity: int = 256


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
    """Vritti-gated gradient modulation for experiential learning.

    Core idea: gradients must overcome the system's own resistance to
    propagate. The resistance is not arbitrary — it emerges from the
    system's current cognitive state (vritti field). High-stakes errors
    can force gates open; low-stakes errors are queued for offline
    consolidation.

    Architecture:
        region_state -> VrittiFieldEstimator -> resistance_field
        error_signal -> StakesEstimator -> stakes_field
        gate = sigmoid((stakes - resistance) / temperature)
        effective_update = gate * proposed_update

    Items that fail to pass the gate are queued for offline consolidation
    (sleep analog), implementing the "pause before integration" that
    characterizes deep experiential learning.

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

        # Persistent resistance state (evolves across training steps)
        self.register_buffer(
            "persistent_resistance",
            torch.full((config.num_regions,), 0.5),
        )

        # Error history for scar tissue effect
        self.register_buffer(
            "error_history",
            torch.zeros(config.num_regions),
        )

        # Consolidation queue: items that failed to pass the gate
        self.consolidation_queue: list = []

    def forward(
        self,
        region_states: torch.Tensor,
        error_signal: torch.Tensor,
        proposed_update: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Gate proposed updates through vritti resistance field.

        Args:
            region_states: [B, num_regions, D] current state per region
            error_signal: [B, num_regions, D] error signal per region
            proposed_update: [B, num_regions, D] proposed gradient update

        Returns:
            Dict with:
                'gated_update': [B, num_regions, D] modulated update
                'gate_values': [B, num_regions] gate openness in [0, 1]
                'resistance': [B, num_regions] resistance per region
                'stakes': [B, num_regions] stakes per region
                'vritti_dist': [B, num_regions, num_vritti] vritti probs
                'queued_count': number of items queued for consolidation
        """
        B = region_states.shape[0]

        # Estimate vritti field and resistance
        vritti_dist, instantaneous_resistance = self.vritti_estimator(region_states)

        # Blend instantaneous with persistent resistance
        resistance = (
            0.7 * instantaneous_resistance
            + 0.3 * self.persistent_resistance.unsqueeze(0)
        )

        # Clamp resistance to [floor, ceiling]
        resistance = resistance.clamp(
            self.config.resistance_floor, self.config.resistance_ceiling
        )

        # Estimate stakes of this error
        stakes = self.stakes_estimator(error_signal, self.error_history)

        # Gate computation: open when stakes exceed resistance
        gate_logit = (stakes - resistance) / self.config.gate_temperature
        gate_values = torch.sigmoid(gate_logit)  # [B, num_regions]

        # Apply gate to proposed update
        gated_update = proposed_update * gate_values.unsqueeze(-1)

        # Queue items that failed to pass gate for consolidation
        with torch.no_grad():
            blocked_mask = gate_values < 0.3  # Substantially blocked
            queued_count = 0
            if blocked_mask.any() and len(self.consolidation_queue) < self.config.queue_capacity:
                # Store the blocked error signals for offline processing
                for b in range(B):
                    blocked_regions = blocked_mask[b].nonzero(as_tuple=True)[0]
                    if len(blocked_regions) > 0:
                        self.consolidation_queue.append({
                            "error": error_signal[b, blocked_regions].detach().cpu(),
                            "regions": blocked_regions.detach().cpu(),
                            "stakes": stakes[b, blocked_regions].detach().cpu(),
                            "resistance": resistance[b, blocked_regions].detach().cpu(),
                        })
                        queued_count += len(blocked_regions)

            # Update persistent resistance (temporal dynamics)
            update_impact = gate_values.mean(dim=0).detach()
            self.persistent_resistance.mul_(self.config.resistance_decay).add_(
                update_impact * (1 - self.config.resistance_decay)
            )

            # Update error history (scar tissue)
            error_magnitude = error_signal.norm(dim=-1).mean(dim=0).detach()
            self.error_history.mul_(0.99).add_(error_magnitude * 0.01)

        return {
            "gated_update": gated_update,
            "gate_values": gate_values,
            "resistance": resistance,
            "stakes": stakes,
            "vritti_dist": vritti_dist,
            "queued_count": queued_count,
        }

    def drain_consolidation_queue(self) -> list:
        """Drain and return all items queued for offline consolidation.

        Returns:
            List of queued items (dicts with error, regions, stakes, resistance)
        """
        items = list(self.consolidation_queue)
        self.consolidation_queue.clear()
        return items

    def get_resistance_state(self) -> Dict[str, torch.Tensor]:
        """Get current resistance state for diagnostics."""
        return {
            "persistent_resistance": self.persistent_resistance.clone(),
            "error_history": self.error_history.clone(),
            "queue_depth": len(self.consolidation_queue),
        }

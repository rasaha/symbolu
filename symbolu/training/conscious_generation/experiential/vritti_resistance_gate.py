"""
VrittiResistanceGate: Resistance-driven adaptive plasticity controller.

Core equation (post-ablation consolidation):

    g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

Where:
    resistance_eff = resistance * exp(-k_m * misalignment)
    openness = (1 - resistance_eff) + w_s * salience
    plasticity = sigmoid(k * openness + bias)
    d_t = 1 / (1 + gradient_variance / coherence_stability)
    max_gain_t = base_gain * coherence_factor * phase_factor

Ablation-validated properties:
    - Resistance is the primary control signal (load-bearing)
    - Salience is merged into openness as modulation (not a competing signal)
    - Misalignment uses exponential coupling for real influence at high values
    - Historical consistency retained for diagnostics only (not load-bearing)
    - Damping and adaptive gain are load-bearing (rate-limited)
    - Biased sigmoid prevents dead zones (load-bearing)

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import math
import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class VrittiResistanceConfig:
    """Configuration for vritti resistance gating.

    Consolidated from 13 → 11 tunable parameters after ablation.
    Removed: latent_dominance (replaced by misalignment_strength with
    exponential coupling), consistency modulation (retained for diagnostics only).

    Attributes:
        d_model: Model dimension
        num_regions: Number of gatable regions in the model
        num_vritti_modes: Number of vritti cognitive modes (5 classical)
        resistance_decay: Temporal decay of resistance EMA state
        resistance_floor: Minimum resistance (prevents zero-resistance)
        resistance_ceiling: Maximum resistance (prevents total lockout)
        base_max_gain: Base maximum plasticity gain (before adaptation)
        plasticity_floor: Minimum plasticity (prevents dead zones)
        damping_sensitivity: How much gradient variance reduces gain
        ema_momentum: Momentum for resistance EMA smoothing
        misalignment_strength: Exponential coupling strength for latent misalignment.
            resistance_eff = resistance * exp(-k * misalignment).
            k=0: no effect. k=2: misalignment=1 → resistance drops to 13%.
        deferred_capacity: Max items in deferred buffer
        deferred_ttl: Time-to-live for deferred items (steps)
        consistency_window: Steps to track for historical consistency (diagnostics)
    """
    d_model: int = 128
    num_regions: int = 12
    num_vritti_modes: int = 5
    resistance_decay: float = 0.95
    resistance_floor: float = 0.05
    resistance_ceiling: float = 0.95
    base_max_gain: float = 3.0
    plasticity_floor: float = 0.05
    damping_sensitivity: float = 1.0
    ema_momentum: float = 0.9
    misalignment_strength: float = 2.0
    deferred_capacity: int = 128
    deferred_ttl: int = 200
    consistency_window: int = 50


class VrittiFieldEstimator(nn.Module):
    """Estimates the current vritti (cognitive mode) field for each region.

    Maps to Patanjali's 5 vrittis:
        0: Pramana (valid cognition) - high resistance
        1: Viparyaya (misperception) - low resistance
        2: Vikalpa (conceptual branching) - medium resistance
        3: Smrti (memory) - high resistance
        4: Nidra (dormancy) - low resistance
    """

    def __init__(self, d_model: int, num_regions: int, num_vritti: int = 5):
        super().__init__()
        self.num_regions = num_regions
        self.num_vritti = num_vritti

        self.vritti_classifier = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.GELU(),
            nn.Linear(d_model // 2, num_vritti),
        )

        # Vritti-to-resistance mapping (learned, initialized with priors)
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
        vritti_logits = self.vritti_classifier(region_states)
        vritti_dist = torch.softmax(vritti_logits, dim=-1)
        resistance = (vritti_dist * self.vritti_resistance.unsqueeze(0).unsqueeze(0)).sum(dim=-1)
        return vritti_dist, resistance


class StakesEstimator(nn.Module):
    """Estimates the stakes (consequence level) of a given error signal.

    Used as fallback salience when external salience weights are not provided.
    After ablation: salience is modulation, not primary control.
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
        stakes = self.stakes_proj(error_signal).squeeze(-1)
        if error_history is not None:
            history_boost = error_history.unsqueeze(0)
            stakes = stakes + 0.1 * history_boost
            stakes = stakes.clamp(0.0, 1.0)
        return stakes


class AdaptiveGainController:
    """Computes adaptive max_gain based on training state.

    max_gain_t = base_gain * coherence_factor * phase_factor

    Rate-limited: gain cannot change by more than max_delta per step.
    Load-bearing per ablation: removing adaptive gain collapses gain to constant.
    """

    def __init__(self, base_max_gain: float = 3.0, max_delta_fraction: float = 0.1):
        self.base_max_gain = base_max_gain
        self.max_delta_fraction = max_delta_fraction
        self._prev_gain: Optional[float] = None

    def compute(
        self,
        coherence: Optional[float] = None,
        step: int = 0,
        warmup_steps: int = 1000,
    ) -> float:
        """Compute adaptive max gain with rate limiting."""
        phase_factor = min(1.0, 0.5 + 0.5 * step / max(warmup_steps, 1))

        if coherence is not None:
            coherence_factor = 0.5 + 0.5 / (1.0 + math.exp(-(coherence - 0.5) * 4))
        else:
            coherence_factor = 0.75

        target_gain = self.base_max_gain * coherence_factor * phase_factor

        if self._prev_gain is not None:
            max_delta = self.base_max_gain * self.max_delta_fraction
            clamped = max(
                self._prev_gain - max_delta,
                min(self._prev_gain + max_delta, target_gain),
            )
            self._prev_gain = clamped
            return clamped
        else:
            self._prev_gain = target_gain
            return target_gain


class DampingComputer:
    """Computes explicit damping factor d_t.

    d_t = 1 / (1 + sensitivity * gradient_variance / coherence_stability)

    Load-bearing per ablation: sensitivity=0 locks damping at 1.0.
    """

    def __init__(self, sensitivity: float = 1.0, ema_decay: float = 0.95, max_delta: float = 0.1):
        self.sensitivity = sensitivity
        self._grad_var_ema = 0.0
        self._coherence_ema = 0.5
        self._ema_decay = ema_decay
        self._max_delta = max_delta
        self._prev_d_t: Optional[float] = None

    def compute(
        self,
        gradient_variance: float,
        coherence_stability: Optional[float] = None,
    ) -> float:
        """Compute damping factor in (0, 1]."""
        self._grad_var_ema = (
            self._ema_decay * self._grad_var_ema
            + (1 - self._ema_decay) * gradient_variance
        )

        if coherence_stability is not None:
            self._coherence_ema = (
                self._ema_decay * self._coherence_ema
                + (1 - self._ema_decay) * coherence_stability
            )

        coh = max(self._coherence_ema, 1e-6)
        d_t = 1.0 / (1.0 + self.sensitivity * self._grad_var_ema / coh)
        d_t = max(d_t, 0.01)

        if self._prev_d_t is not None:
            d_t = max(self._prev_d_t - self._max_delta,
                      min(self._prev_d_t + self._max_delta, d_t))
        self._prev_d_t = d_t

        return d_t


class VrittiResistanceGate(nn.Module):
    """Resistance-driven adaptive plasticity controller.

    Post-ablation consolidated architecture:

        resistance_eff = resistance * exp(-k_m * misalignment)
        openness = (1 - resistance_eff) + w_s * salience
        plasticity = sigmoid(k * openness + bias)
        g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

    Key design decisions (ablation-validated):
        - Resistance is primary: ablation causes largest behavioral shift
        - Salience is merged into openness (modulation, not competing signal)
        - Exponential misalignment coupling: exp(-k*m) forces real influence
        - Historical consistency: diagnostics only (not load-bearing for gating)
        - Biased sigmoid: load-bearing (prevents dead zones)
        - Damping and adaptive gain: load-bearing (rate-limited)

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

        # Consolidated learned parameters (3 total):
        #   k: scaling for merged openness signal
        #   w_s: weight for salience contribution to openness
        #   bias: ensures plasticity > sigmoid(bias) > 0 always
        self.coupling_k = nn.Parameter(torch.tensor(2.0))
        self.coupling_w_s = nn.Parameter(torch.tensor(0.5))
        self.coupling_bias = nn.Parameter(torch.tensor(-1.0))

        # Persistent resistance state (EMA-smoothed)
        self.register_buffer(
            "persistent_resistance",
            torch.full((config.num_regions,), 0.5),
        )

        # Error history for scar tissue
        self.register_buffer("error_history", torch.zeros(config.num_regions))

        # Historical consistency tracking (diagnostics only — not used in gating)
        self.register_buffer(
            "resistance_history",
            torch.zeros(config.consistency_window, config.num_regions),
        )
        self.register_buffer(
            "history_ptr", torch.tensor(0, dtype=torch.long)
        )

        # Adaptive gain controller and damping computer
        self.gain_controller = AdaptiveGainController(config.base_max_gain)
        self.damping_computer = DampingComputer(config.damping_sensitivity)

        # Deferred buffer: strict constraints
        self.deferred_buffer: list = []

    def forward(
        self,
        region_states: torch.Tensor,
        error_signal: torch.Tensor,
        proposed_update: torch.Tensor,
        salience_weights: Optional[torch.Tensor] = None,
        latent_misalignment: Optional[torch.Tensor] = None,
        coherence: Optional[float] = None,
    ) -> Dict[str, torch.Tensor]:
        """Scale proposed updates via resistance-driven plasticity field.

        Consolidated equation:
            resistance_eff = resistance * exp(-k_m * misalignment)
            openness = (1 - resistance_eff) + w_s * salience
            plasticity = sigmoid(k * openness + bias)
            g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

        Args:
            region_states: [B, num_regions, D] current state per region
            error_signal: [B, num_regions, D] error signal per region
            proposed_update: [B, num_regions, D] proposed gradient update
            salience_weights: Optional [B, num_regions] salience (merged into openness)
            latent_misalignment: Optional [B, num_regions] misalignment from
                coherence pipeline (exponential coupling into resistance)
            coherence: Optional scalar coherence measure for adaptive gain

        Returns:
            Dict with all signals and diagnostics
        """
        B = region_states.shape[0]
        step = self.history_ptr.item()

        # === Step 1: Base resistance from vritti field ===
        vritti_dist, instantaneous_resistance = self.vritti_estimator(region_states)

        # EMA-smooth with persistent state
        resistance = (
            self.config.ema_momentum * self.persistent_resistance.unsqueeze(0)
            + (1 - self.config.ema_momentum) * instantaneous_resistance
        )

        # === Step 2: Exponential misalignment coupling ===
        # exp(-k * m): m=0 → factor=1, m=1 → factor=exp(-k)
        # With k=2: m=1 → factor≈0.13 (much stronger than linear 1-0.3=0.7)
        if latent_misalignment is not None:
            misalignment_factor = torch.exp(
                -self.config.misalignment_strength * latent_misalignment.clamp(0, 1)
            )
            resistance = resistance * misalignment_factor

        # Clamp resistance
        resistance = resistance.clamp(
            self.config.resistance_floor, self.config.resistance_ceiling
        )

        # === Step 3: Merged openness signal ===
        # Salience is folded into openness (not a competing signal)
        stakes = self.stakes_estimator(error_signal, self.error_history)
        effective_salience = salience_weights if salience_weights is not None else stakes

        # openness = (1 - resistance) + w_s * salience
        openness = (1.0 - resistance) + self.coupling_w_s * effective_salience

        # === Step 4: Biased sigmoid plasticity (load-bearing) ===
        # plasticity = sigmoid(k * openness + bias)
        plasticity_logit = self.coupling_k * openness + self.coupling_bias
        plasticity = torch.sigmoid(plasticity_logit)

        # === Step 5: Adaptive gain ceiling (load-bearing) ===
        max_gain_t = self.gain_controller.compute(
            coherence=coherence, step=step
        )

        # === Step 6: Explicit damping (load-bearing) ===
        grad_variance = proposed_update.var().item()
        d_t = self.damping_computer.compute(
            gradient_variance=grad_variance,
            coherence_stability=coherence,
        )

        # === Step 7: Final output ===
        # g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g
        plasticity = plasticity.clamp(self.config.plasticity_floor, max_gain_t)
        effective_gain = d_t * plasticity

        gated_update = proposed_update * effective_gain.unsqueeze(-1)

        # === Deferred buffer ===
        deferred_count = self._update_deferred_buffer(
            effective_salience, plasticity, error_signal, step
        )

        # === Update persistent state + diagnostics ===
        consistency = self._compute_historical_consistency()

        with torch.no_grad():
            mean_resistance = resistance.mean(dim=0).detach()
            self.persistent_resistance.mul_(self.config.resistance_decay).add_(
                mean_resistance * (1 - self.config.resistance_decay)
            )

            # Record resistance history (diagnostics only)
            ptr = self.history_ptr.item() % self.config.consistency_window
            self.resistance_history[ptr] = mean_resistance
            self.history_ptr += 1

            # Update error history (scar tissue)
            error_magnitude = error_signal.norm(dim=-1).mean(dim=0).detach()
            self.error_history.mul_(0.99).add_(error_magnitude * 0.01)

        return {
            "gated_update": gated_update,
            "plasticity": plasticity,
            "effective_gain": effective_gain,
            "damping": torch.tensor(d_t),
            "max_gain_t": torch.tensor(max_gain_t),
            "resistance": resistance,
            "resistance_openness": openness,
            "consistency": consistency,
            "stakes": stakes,
            "vritti_dist": vritti_dist,
            "deferred_count": deferred_count,
        }

    def _compute_historical_consistency(self) -> torch.Tensor:
        """Compute resistance consistency over the window (diagnostics only).

        Low variance = high consistency = stable beliefs.
        Not used in gating after ablation showed it's not load-bearing.
        """
        filled = min(self.history_ptr.item(), self.config.consistency_window)
        if filled < 2:
            return torch.ones(self.config.num_regions, device=self.persistent_resistance.device)

        history = self.resistance_history[:filled]
        variance = history.var(dim=0)
        consistency = 1.0 / (1.0 + 10.0 * variance)
        return consistency

    def _update_deferred_buffer(
        self,
        salience: torch.Tensor,
        plasticity: torch.Tensor,
        error_signal: torch.Tensor,
        step: int,
    ) -> int:
        """Update deferred buffer with strict constraints."""
        deferred_count = 0

        with torch.no_grad():
            self.deferred_buffer = [
                item for item in self.deferred_buffer
                if step - item.get("step", 0) < self.config.deferred_ttl
            ]

            high_salience = salience > 0.5
            low_plasticity = plasticity < 0.2
            defer_mask = high_salience & low_plasticity

            if defer_mask.any() and len(self.deferred_buffer) < self.config.deferred_capacity:
                B = salience.shape[0]
                for b in range(B):
                    defer_regions = defer_mask[b].nonzero(as_tuple=True)[0]
                    if len(defer_regions) > 0:
                        self.deferred_buffer.append({
                            "regions": defer_regions.detach().cpu().tolist(),
                            "salience": salience[b, defer_regions].mean().item(),
                            "step": step,
                        })
                        deferred_count += len(defer_regions)

        return deferred_count

    def drain_deferred_buffer(self) -> list:
        """Drain and return deferred samples for periodic replay."""
        items = list(self.deferred_buffer)
        self.deferred_buffer.clear()
        return items

    def get_resistance_state(self) -> Dict[str, torch.Tensor]:
        """Get current resistance state for diagnostics."""
        return {
            "persistent_resistance": self.persistent_resistance.clone(),
            "error_history": self.error_history.clone(),
            "deferred_depth": len(self.deferred_buffer),
            "consistency": self._compute_historical_consistency(),
        }

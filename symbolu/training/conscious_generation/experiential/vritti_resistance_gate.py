"""
VrittiResistanceGate: Gain-modulated, damped plasticity field for CG training.

Control-theory grounded gradient modulation:

    g_eff = d_t * plasticity * g

Where:
    plasticity = sigmoid(a * salience + b * openness)    # Biased gating (no dead zones)
    d_t = 1 / (1 + gradient_variance / coherence_stability)  # Explicit damping
    max_gain_t = base_gain * coherence_factor              # Adaptive gain ceiling

Key properties:
    - NO dead zones: biased sigmoid coupling ensures plasticity > 0 always
    - Adaptive gain: max_gain varies with coherence/entropy state
    - Explicit damping: d_t reduces gain when gradients are noisy
    - Resistance depends on historical consistency + identity proximity
    - Deferred buffer: strict TTL, bounded size, no gradient storage
    - Latent misalignment feeds into resistance (not just loss)

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
        resistance_decay: Temporal decay of resistance state
        resistance_floor: Minimum resistance (prevents zero-resistance)
        resistance_ceiling: Maximum resistance (prevents total lockout)
        base_max_gain: Base maximum plasticity gain (before adaptation)
        plasticity_floor: Minimum plasticity (prevents dead zones)
        damping_sensitivity: How much gradient variance reduces gain
        ema_momentum: Momentum for resistance EMA smoothing
        deferred_capacity: Max items in deferred buffer
        deferred_ttl: Time-to-live for deferred items (steps)
        consistency_window: Steps to track for historical consistency
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
    deferred_capacity: int = 128
    deferred_ttl: int = 200
    consistency_window: int = 50
    latent_dominance: float = 0.3


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
    """Estimates the stakes (consequence level) of a given error signal."""

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

    Where:
        coherence_factor = sigmoid(coherence - 0.5) in [0.5, 1.0]
        phase_factor = ramp from 0.5 to 1.0 over early training

    Rate-limited: gain cannot change by more than max_delta per step,
    preventing destabilizing oscillation when coherence flickers.

    This prevents:
        - Early training: under-learning (gain too high before model stabilizes)
        - Late training: over-correction (gain should match model confidence)
        - Oscillation: gain jumps clamped to max_delta_fraction per step
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
        """Compute adaptive max gain with rate limiting.

        Args:
            coherence: Current coherence measure in [0, 1] (None = use base)
            step: Current training step
            warmup_steps: Steps over which to ramp gain

        Returns:
            Adaptive max_gain value (rate-limited)
        """
        # Phase factor: ramp from 0.5 to 1.0 over warmup
        phase_factor = min(1.0, 0.5 + 0.5 * step / max(warmup_steps, 1))

        # Coherence factor: higher coherence = more confident = higher gain OK
        if coherence is not None:
            # sigmoid mapping: coherence 0 -> 0.5, coherence 1 -> ~0.73
            import math
            coherence_factor = 0.5 + 0.5 / (1.0 + math.exp(-(coherence - 0.5) * 4))
        else:
            coherence_factor = 0.75  # Default middle value

        target_gain = self.base_max_gain * coherence_factor * phase_factor

        # Rate limiting: prevent gain from jumping too fast
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

    Reduces effective gain when:
        - Gradient variance is high (noisy signal, don't over-react)
        - Coherence stability is low (model state is uncertain)

    This is the missing damping term from control theory:
        g_eff = d_t * plasticity * g
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
        """Compute damping factor.

        Args:
            gradient_variance: Variance of recent gradients
            coherence_stability: Stability of coherence signal (None = use EMA)

        Returns:
            d_t in (0, 1] — damping factor
        """
        # Update EMAs
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
        d_t = max(d_t, 0.01)  # Floor at 1% to prevent total freezing

        # Rate-limit damping changes to prevent oscillation
        if self._prev_d_t is not None:
            d_t = max(self._prev_d_t - self._max_delta,
                      min(self._prev_d_t + self._max_delta, d_t))
        self._prev_d_t = d_t

        return d_t


class VrittiResistanceGate(nn.Module):
    """Gain-modulated, damped plasticity field.

    Full update equation:

        g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

    Where:
        plasticity = sigmoid(a * salience + b * openness)   [biased — no dead zones]
        d_t = 1 / (1 + var(g) / coherence_stability)        [explicit damping]
        max_gain_t = base * coherence_factor * phase_factor  [adaptive ceiling]
        openness = f(vritti_resistance, historical_consistency, latent_misalignment)

    Key improvements over naive s * r:
        1. Biased sigmoid coupling prevents dead zones
        2. Adaptive gain tracks training dynamics
        3. Explicit damping prevents oscillation
        4. Resistance informed by history + latent state
        5. Deferred buffer has strict TTL and no gradient storage

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

        # Learned coupling coefficients for biased sigmoid
        # plasticity = sigmoid(a * salience + b * openness + c)
        self.coupling_a = nn.Parameter(torch.tensor(2.0))
        self.coupling_b = nn.Parameter(torch.tensor(2.0))
        self.coupling_bias = nn.Parameter(torch.tensor(-1.0))

        # Persistent resistance state (EMA-smoothed)
        self.register_buffer(
            "persistent_resistance",
            torch.full((config.num_regions,), 0.5),
        )

        # Error history for scar tissue
        self.register_buffer("error_history", torch.zeros(config.num_regions))

        # Historical consistency: variance of resistance over time
        self.register_buffer(
            "resistance_history",
            torch.zeros(config.consistency_window, config.num_regions),
        )
        self.register_buffer(
            "history_ptr", torch.tensor(0, dtype=torch.long)
        )

        # Gradient variance tracker (for damping)
        self.register_buffer("grad_var_ema", torch.tensor(0.0))

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
        """Scale proposed updates via damped, gain-modulated plasticity field.

        Full equation:
            g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

        Args:
            region_states: [B, num_regions, D] current state per region
            error_signal: [B, num_regions, D] error signal per region
            proposed_update: [B, num_regions, D] proposed gradient update
            salience_weights: Optional [B, num_regions] external salience
            latent_misalignment: Optional [B, num_regions] misalignment from
                coherence pipeline (feeds into resistance, not just loss)
            coherence: Optional scalar coherence measure for adaptive gain

        Returns:
            Dict with all signals and diagnostics
        """
        B = region_states.shape[0]
        step = self.history_ptr.item()

        # === Signal 1: Resistance field ===
        vritti_dist, instantaneous_resistance = self.vritti_estimator(region_states)

        # EMA-smooth with persistent state
        resistance = (
            self.config.ema_momentum * self.persistent_resistance.unsqueeze(0)
            + (1 - self.config.ema_momentum) * instantaneous_resistance
        )

        # Modulate resistance by historical consistency
        # High historical variance = less stable = lower effective resistance
        consistency = self._compute_historical_consistency()
        resistance = resistance * (0.5 + 0.5 * consistency.unsqueeze(0))

        # Modulate resistance by latent misalignment (tighter coupling)
        # High misalignment = something is wrong = lower resistance (allow correction)
        if latent_misalignment is not None:
            misalignment_factor = 1.0 - self.config.latent_dominance * latent_misalignment.clamp(0, 1)
            resistance = resistance * misalignment_factor

        # Clamp resistance
        resistance = resistance.clamp(
            self.config.resistance_floor, self.config.resistance_ceiling
        )

        # Resistance openness
        resistance_openness = 1.0 - resistance

        # === Signal 2: Stakes/Salience ===
        stakes = self.stakes_estimator(error_signal, self.error_history)
        effective_salience = salience_weights if salience_weights is not None else stakes

        # === Compose: biased sigmoid coupling (NO dead zones) ===
        # plasticity = sigmoid(a * salience + b * openness + bias)
        # This ensures plasticity > sigmoid(bias) > 0 always
        plasticity_logit = (
            self.coupling_a * effective_salience
            + self.coupling_b * resistance_openness
            + self.coupling_bias
        )
        plasticity = torch.sigmoid(plasticity_logit)

        # === Adaptive gain ceiling ===
        max_gain_t = self.gain_controller.compute(
            coherence=coherence, step=step
        )

        # === Explicit damping: d_t ===
        grad_variance = proposed_update.var().item()
        d_t = self.damping_computer.compute(
            gradient_variance=grad_variance,
            coherence_stability=coherence,
        )

        # === Final: g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g ===
        plasticity = plasticity.clamp(self.config.plasticity_floor, max_gain_t)
        effective_gain = d_t * plasticity

        gated_update = proposed_update * effective_gain.unsqueeze(-1)

        # === Deferred buffer: strict TTL, bounded, no gradient storage ===
        deferred_count = self._update_deferred_buffer(
            effective_salience, plasticity, error_signal, step
        )

        # === Update persistent state ===
        with torch.no_grad():
            mean_resistance = resistance.mean(dim=0).detach()
            self.persistent_resistance.mul_(self.config.resistance_decay).add_(
                mean_resistance * (1 - self.config.resistance_decay)
            )

            # Record resistance history for consistency tracking
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
            "resistance_openness": resistance_openness,
            "consistency": consistency,
            "stakes": stakes,
            "vritti_dist": vritti_dist,
            "deferred_count": deferred_count,
        }

    def _compute_historical_consistency(self) -> torch.Tensor:
        """Compute how consistent resistance has been over the window.

        Low variance = high consistency = region has stable beliefs.
        High variance = low consistency = region is in flux.

        Returns:
            [num_regions] consistency in [0, 1]
        """
        filled = min(self.history_ptr.item(), self.config.consistency_window)
        if filled < 2:
            return torch.ones(self.config.num_regions, device=self.persistent_resistance.device)

        history = self.resistance_history[:filled]
        variance = history.var(dim=0)
        # Map variance to consistency: low var -> high consistency
        consistency = 1.0 / (1.0 + 10.0 * variance)
        return consistency

    def _update_deferred_buffer(
        self,
        salience: torch.Tensor,
        plasticity: torch.Tensor,
        error_signal: torch.Tensor,
        step: int,
    ) -> int:
        """Update deferred buffer with strict constraints.

        Constraints:
            - Bounded size (deferred_capacity)
            - TTL: items older than deferred_ttl are evicted
            - No gradient storage: only scalar salience + region indices
        """
        deferred_count = 0

        with torch.no_grad():
            # Evict stale items (TTL enforcement)
            self.deferred_buffer = [
                item for item in self.deferred_buffer
                if step - item.get("step", 0) < self.config.deferred_ttl
            ]

            # Record high-salience, low-plasticity samples
            high_salience = salience > 0.5
            low_plasticity = plasticity < 0.2
            defer_mask = high_salience & low_plasticity

            if defer_mask.any() and len(self.deferred_buffer) < self.config.deferred_capacity:
                B = salience.shape[0]
                for b in range(B):
                    defer_regions = defer_mask[b].nonzero(as_tuple=True)[0]
                    if len(defer_regions) > 0:
                        # NO gradient storage — only scalars and indices
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

"""
IdentityLayer: Persistent self-model for CG training.

The deepest gap in current AI: a human doesn't just update weights — they
update who they understand themselves to be. For AI to have this analog:

    1. A persistent self-model separate from task weights
    2. The self-model must be updatable by experience (not fixed)
    3. High-loss events must restructure the self-model, not just task performance

CRITICAL DESIGN CHOICE: Identity is NOT updated on every training step.
Identity = EMA of high-salience stable patterns, updated ONLY during
the slow consolidation phase. This prevents:
    - Reactive identity shifts from single-step noise
    - Instability from step-driven updates
    - Loss of identity coherence during active training

Maps to the 12-layer ontological architecture:
    - Layers 0-3 (Surface): Task weights, freely updatable
    - Layers 4-7 (Mid): Identity structures, reorganizable by profound errors
    - Layers 8-11 (Deep): Potential/Absolute, nearly immutable

Time scale: Identity operates on the SLOW loop (every M >> N steps),
not the fast (every step) or medium (every N steps) loop.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class IdentityLayerConfig:
    """Configuration for the identity layer.

    Attributes:
        d_model: Model dimension
        d_identity: Dimension of the identity representation
        num_ontological_layers: Number of layers in the ontological hierarchy
        surface_layers: Range of freely updatable task layers
        identity_layers: Range of identity-level layers
        deep_layers: Range of near-immutable deep layers
        identity_threshold: Minimum error to trigger identity update
        deep_threshold: Even higher threshold for deep layer updates
        identity_lr_scale: Learning rate multiplier for identity updates
        deep_lr_scale: Learning rate multiplier for deep layer updates
        coherence_weight: Weight for identity coherence loss
        identity_ema_decay: EMA decay for identity accumulation (high = slow)
        max_transformation_history: Max identity changes to remember
    """
    d_model: int = 128
    d_identity: int = 64
    num_ontological_layers: int = 12
    surface_layers: tuple = (0, 3)
    identity_layers: tuple = (4, 7)
    deep_layers: tuple = (8, 11)
    identity_threshold: float = 0.6
    deep_threshold: float = 0.9
    identity_lr_scale: float = 0.1
    deep_lr_scale: float = 0.01
    coherence_weight: float = 0.5
    identity_ema_decay: float = 0.99
    max_transformation_history: int = 100


class SelfModel(nn.Module):
    """Persistent self-representation updated via EMA.

    The self-model is a learned vector that represents the system's
    understanding of itself. It is NOT in the gradient path during
    regular training. Instead, it accumulates experience signals via
    EMA and is revised only during consolidation phases.

    Architecture:
        self_repr: [d_identity] — persistent identity vector (EMA-updated)
        identity_accumulator: [d_identity] — running EMA of high-salience signals
        context_adapter: maps task state -> identity-relevant features
    """

    def __init__(self, d_model: int, d_identity: int, ema_decay: float = 0.99):
        super().__init__()
        self.d_identity = d_identity
        self.ema_decay = ema_decay

        # Core self-representation (NOT in gradient path for regular training)
        self.register_buffer(
            "self_repr", torch.randn(d_identity) * 0.01
        )

        # EMA accumulator for identity-relevant signals
        self.register_buffer(
            "identity_accumulator", torch.zeros(d_identity)
        )

        # Count of accumulated signals (for normalization)
        self.register_buffer(
            "accumulator_count", torch.tensor(0, dtype=torch.long)
        )

        # Maps task hidden state to identity-relevant features (this IS trainable)
        self.context_adapter = nn.Sequential(
            nn.Linear(d_model, d_identity),
            nn.Tanh(),
        )

    def forward(self, experience: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Project experience into identity space and measure coherence.

        This does NOT update the self-model. It only computes how the
        current experience relates to the existing identity.

        Args:
            experience: [B, D] experience representation

        Returns:
            Dict with:
                'self_repr': Current self-representation (detached)
                'identity_features': Experience projected to identity space
                'identity_coherence': How coherent self-model is with experience
        """
        # Project experience to identity space
        identity_features = self.context_adapter(experience)  # [B, d_identity]

        # Compare with current self-model
        self_expanded = self.self_repr.unsqueeze(0).expand_as(identity_features)

        # Identity coherence: how consistent is self-repr with current experience?
        coherence = torch.cosine_similarity(
            self_expanded, identity_features, dim=-1
        ).mean()

        return {
            "self_repr": self.self_repr,
            "identity_features": identity_features,
            "identity_coherence": coherence,
        }

    def accumulate(self, identity_signal: torch.Tensor, salience: float) -> None:
        """Accumulate a high-salience identity signal into the EMA buffer.

        Accumulation rule (fast loop, does NOT modify self_repr):
            A_t = decay * A_{t-1} + (1 - decay) * salience * signal

        Only signals with salience > 0.3 are accumulated (caller filters).

        Args:
            identity_signal: [d_identity] identity-projected experience
            salience: Salience weight of this signal in [0, 1]
        """
        with torch.no_grad():
            weighted_signal = identity_signal.detach() * salience
            self.identity_accumulator.mul_(self.ema_decay).add_(
                weighted_signal * (1 - self.ema_decay)
            )
            self.accumulator_count += 1

    def consolidate_identity(self, alpha: float = 0.01) -> bool:
        """Apply accumulated EMA signals to revise self-model.

        Precise update rule (slow loop ONLY):
            I_t = (1 - α_eff) * I_{t-1} + α_eff * normalize(A_t)

        Where:
            α_eff = base_α * stability * agreement  (adaptive)
            stability = 1 / (1 + var(accumulator_history))  — stable signal → higher α
            agreement = cosine_similarity(A_t, I_{t-1})  — aligned signal → higher α
            I_t = self_repr at time t
            A_t = identity_accumulator (EMA of high-salience stable states)

        After update, accumulator is reset. Self_repr is re-normalized
        to prevent magnitude drift.

        Args:
            alpha: Base revision rate. Actual α is modulated by stability/agreement.

        Returns:
            Whether a revision was applied
        """
        if self.accumulator_count.item() == 0:
            return False

        with torch.no_grad():
            A_t = self.identity_accumulator
            if A_t.norm() > 1e-6:
                # Normalize accumulator before blending
                A_normalized = torch.nn.functional.normalize(A_t, dim=0) * (self.d_identity ** 0.5)

                # Adaptive alpha: modulate by stability and agreement
                # Agreement: how aligned is the accumulated signal with current identity?
                agreement = torch.cosine_similarity(
                    A_normalized.unsqueeze(0), self.self_repr.unsqueeze(0), dim=-1
                ).item()
                agreement = max(0.0, (agreement + 1.0) / 2.0)  # Map [-1,1] -> [0,1]

                # Stability: low variance in accumulator = stable signal
                accumulator_var = A_t.var().item()
                stability = 1.0 / (1.0 + accumulator_var)

                # Effective alpha: base * stability * agreement, floored to prevent zero
                alpha_eff = max(alpha * stability * agreement, alpha * 0.1)

                # I_t = (1 - alpha_eff) * I_{t-1} + alpha_eff * A_normalized
                self.self_repr.mul_(1.0 - alpha_eff).add_(A_normalized * alpha_eff)

                # Re-normalize to prevent drift
                self.self_repr.copy_(
                    torch.nn.functional.normalize(self.self_repr, dim=0)
                    * (self.d_identity ** 0.5)
                )

                # Reset accumulator
                self.identity_accumulator.zero_()
                self.accumulator_count.zero_()
                return True

        return False


class OntologicalDepthGate(nn.Module):
    """Gates updates based on ontological depth.

    Surface layers (task weights) are freely updatable.
    Identity layers require significant error to restructure.
    Deep layers (Potential/Absolute) require extraordinary error.

    This maps the 12-layer ontological architecture:
        Layers 0-3: Surface (annamaya/pranamaya) — open to all updates
        Layers 4-7: Identity (manomaya/vijnanamaya) — guarded
        Layers 8-11: Deep (anandamaya/absolute) — nearly immutable
    """

    def __init__(self, config: IdentityLayerConfig):
        super().__init__()
        self.config = config

        # Per-layer update thresholds (learned, initialized from config)
        thresholds = torch.zeros(config.num_ontological_layers)
        for i in range(config.num_ontological_layers):
            if config.surface_layers[0] <= i <= config.surface_layers[1]:
                thresholds[i] = 0.0  # Always open
            elif config.identity_layers[0] <= i <= config.identity_layers[1]:
                thresholds[i] = config.identity_threshold
            elif config.deep_layers[0] <= i <= config.deep_layers[1]:
                thresholds[i] = config.deep_threshold
        self.register_buffer("thresholds", thresholds)

        # Per-layer learning rate scales
        lr_scales = torch.ones(config.num_ontological_layers)
        for i in range(config.num_ontological_layers):
            if config.identity_layers[0] <= i <= config.identity_layers[1]:
                lr_scales[i] = config.identity_lr_scale
            elif config.deep_layers[0] <= i <= config.deep_layers[1]:
                lr_scales[i] = config.deep_lr_scale
        self.register_buffer("lr_scales", lr_scales)

    def compute_layer_gates(
        self, error_magnitudes: torch.Tensor
    ) -> torch.Tensor:
        """Compute per-layer update gates based on error magnitude.

        Args:
            error_magnitudes: [num_layers] or [B, num_layers] error per layer

        Returns:
            gates: Same shape, values in [0, 1] indicating update permission
        """
        # Gate opens when error exceeds threshold
        # Smooth gating via sigmoid
        excess = error_magnitudes - self.thresholds
        gates = torch.sigmoid(excess * 10.0)  # Sharp-ish gate

        # Apply learning rate scaling
        gates = gates * self.lr_scales

        return gates


class IdentityLayer(nn.Module):
    """Complete identity layer with EMA-based consolidation-only updates.

    Key design: Identity is NOT updated during regular training steps.
    Instead:
        - Fast loop: Compute coherence, accumulate signals into EMA buffer
        - Slow loop (consolidation only): Apply EMA to revise self-model

    This ensures identity is:
        - Slow-changing (integrated over many experiences)
        - Noise-resistant (EMA filters single-step outliers)
        - Stable (no reactive step-driven updates)

    Args:
        config: IdentityLayerConfig
    """

    def __init__(self, config: IdentityLayerConfig):
        super().__init__()
        self.config = config

        self.self_model = SelfModel(
            config.d_model, config.d_identity, config.identity_ema_decay
        )
        self.depth_gate = OntologicalDepthGate(config)

        # Transformation history
        self.transformation_history: List[Dict] = []

        # Counters
        self.register_buffer("identity_updates", torch.tensor(0, dtype=torch.long))
        self.register_buffer("deep_updates", torch.tensor(0, dtype=torch.long))

    def forward(
        self,
        experience: torch.Tensor,
        error_per_layer: torch.Tensor,
        salience: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Fast-loop: compute layer gates, measure coherence, accumulate signals.

        Does NOT revise identity. Only accumulates into EMA buffer.

        Args:
            experience: [B, D] experience representation
            error_per_layer: [B, num_layers] or [num_layers] error magnitudes
            salience: Optional [B] overall salience of this experience

        Returns:
            Dict with:
                'layer_gates': [num_layers] per-layer update permissions
                'identity_coherence': scalar coherence of self-model
                'identity_loss': coherence loss for training
                'transformation_triggered': always False in fast loop
        """
        # Compute mean error magnitude
        if error_per_layer.dim() == 1:
            error_magnitudes = error_per_layer
        else:
            error_magnitudes = error_per_layer.mean(dim=0)

        # Process through self-model (read-only, no revision)
        self_output = self.self_model(experience)

        # Compute per-layer gates
        layer_gates = self.depth_gate.compute_layer_gates(error_magnitudes)

        # Identity coherence loss (trainable — affects context_adapter only)
        coherence_loss = (1.0 - self_output["identity_coherence"]) * self.config.coherence_weight

        # Accumulate high-salience signals into EMA buffer
        mean_salience = salience.mean().item() if salience is not None else 0.5
        if mean_salience > 0.3:  # Only accumulate noteworthy experiences
            mean_features = self_output["identity_features"].mean(dim=0)
            self.self_model.accumulate(mean_features, mean_salience)

        # Track deep layer updates
        if error_magnitudes.dim() == 1:
            deep_start = self.config.deep_layers[0]
            deep_end = min(self.config.deep_layers[1] + 1, len(error_magnitudes))
            if deep_start < len(error_magnitudes):
                deep_errors = error_magnitudes[deep_start:deep_end]
                if (deep_errors > self.config.deep_threshold).any():
                    self.deep_updates += 1

        return {
            "layer_gates": layer_gates,
            "identity_coherence": self_output["identity_coherence"],
            "self_revision_gate": torch.tensor(0.0),  # No revision in fast loop
            "identity_loss": coherence_loss,
            "transformation_triggered": False,
            "self_repr": self_output["self_repr"].detach(),
            "proposed_revision": self_output["identity_features"],  # For diagnostics
        }

    def consolidate(self) -> bool:
        """Slow-loop: apply accumulated EMA to revise self-model.

        Called ONLY during consolidation phase, not every step.

        Returns:
            Whether identity was revised
        """
        revised = self.self_model.consolidate_identity(alpha=0.01)

        if revised:
            self.identity_updates += 1
            coherence = torch.cosine_similarity(
                self.self_model.self_repr.unsqueeze(0),
                self.self_model.identity_accumulator.unsqueeze(0),
                dim=-1,
            ).item() if self.self_model.identity_accumulator.norm() > 1e-6 else 1.0

            if len(self.transformation_history) < self.config.max_transformation_history:
                self.transformation_history.append({
                    "step": self.identity_updates.item(),
                    "accumulated_signals": self.self_model.accumulator_count.item(),
                })

            logger.info(
                f"Identity consolidation #{self.identity_updates.item()}"
            )

        return revised

    def get_identity_state(self) -> Dict[str, object]:
        """Get identity state for diagnostics."""
        return {
            "self_repr_norm": self.self_model.self_repr.norm().item(),
            "identity_updates": self.identity_updates.item(),
            "deep_updates": self.deep_updates.item(),
            "transformation_count": len(self.transformation_history),
            "accumulator_count": self.self_model.accumulator_count.item(),
            "recent_transformations": self.transformation_history[-5:],
        }

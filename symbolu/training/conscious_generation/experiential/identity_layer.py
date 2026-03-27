"""
IdentityLayer: Persistent self-model for CG training.

The deepest gap in current AI: a human doesn't just update weights — they
update who they understand themselves to be. For AI to have this analog:

    1. A persistent self-model separate from task weights
    2. The self-model must be updatable by experience (not fixed)
    3. High-loss events must restructure the self-model, not just task performance

Maps to the 12-layer ontological architecture:
    - Layers 0-3 (Surface): Task weights, freely updatable
    - Layers 4-7 (Mid): Identity structures, reorganizable by profound errors
    - Layers 8-11 (Deep): Potential/Absolute, nearly immutable

The identity layer maintains:
    - Self-representation: "who the system understands itself to be"
    - Update threshold: how much error is needed to revise self-model
    - Identity coherence: consistency of self-representation across contexts
    - Transformation record: history of identity-level changes

Some weights ARE identity, and identity should be hard but not impossible
to restructure.

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
    max_transformation_history: int = 100


class SelfModel(nn.Module):
    """Persistent self-representation.

    The self-model is a learned vector that represents the system's
    understanding of itself — its competencies, biases, reliable patterns,
    and known failure modes. It is separate from task weights and updated
    only by significant experiential events.

    Architecture:
        self_repr: [d_identity] — persistent identity vector
        context_adapter: maps task state -> identity-relevant features
        update_gate: decides whether an experience warrants self-revision
    """

    def __init__(self, d_model: int, d_identity: int):
        super().__init__()
        self.d_identity = d_identity

        # Core self-representation (persistent, rarely updated)
        self.self_repr = nn.Parameter(torch.randn(d_identity) * 0.01)

        # Maps task hidden state to identity-relevant features
        self.context_adapter = nn.Sequential(
            nn.Linear(d_model, d_identity),
            nn.Tanh(),
        )

        # Update gate: decides if experience warrants self-revision
        self.update_gate = nn.Sequential(
            nn.Linear(d_identity * 2, d_identity),
            nn.GELU(),
            nn.Linear(d_identity, 1),
            nn.Sigmoid(),
        )

        # Proposed revision network
        self.revision_net = nn.Sequential(
            nn.Linear(d_identity * 2, d_identity),
            nn.GELU(),
            nn.Linear(d_identity, d_identity),
            nn.Tanh(),
        )

    def forward(
        self, experience: torch.Tensor, error_magnitude: float
    ) -> Dict[str, torch.Tensor]:
        """Process an experience and potentially revise self-model.

        Args:
            experience: [B, D] experience representation (from error signal)
            error_magnitude: scalar magnitude of the triggering error

        Returns:
            Dict with:
                'self_repr': Current self-representation
                'identity_features': Experience projected to identity space
                'update_gate': Whether to revise self-model
                'proposed_revision': What the revision would be
                'identity_coherence': How coherent the self-model is
        """
        # Project experience to identity space
        identity_features = self.context_adapter(experience)  # [B, d_identity]

        # Compare with current self-model
        self_expanded = self.self_repr.unsqueeze(0).expand_as(identity_features)
        combined = torch.cat([self_expanded, identity_features], dim=-1)

        # Gate: should we update?
        gate_value = self.update_gate(combined)  # [B, 1]

        # Proposed revision
        proposed = self.revision_net(combined)  # [B, d_identity]

        # Identity coherence: how consistent is self-repr with current experience?
        coherence = torch.cosine_similarity(
            self_expanded, identity_features, dim=-1
        ).mean()

        return {
            "self_repr": self.self_repr,
            "identity_features": identity_features,
            "update_gate": gate_value,
            "proposed_revision": proposed,
            "identity_coherence": coherence,
        }

    def apply_revision(self, revision: torch.Tensor, gate: float) -> None:
        """Apply a revision to the self-model.

        Args:
            revision: [d_identity] proposed revision direction
            gate: Gate value (how much to apply)
        """
        with torch.no_grad():
            # Soft update: blend current self with revision
            self.self_repr.data = (
                (1 - gate) * self.self_repr.data + gate * revision
            )
            # Re-normalize to prevent drift
            self.self_repr.data = torch.nn.functional.normalize(
                self.self_repr.data, dim=0
            ) * (self.d_identity ** 0.5)


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
    """Complete identity layer for experiential learning.

    Orchestrates:
        1. Self-model maintenance and revision
        2. Ontological depth gating
        3. Identity coherence enforcement
        4. Transformation history tracking

    The identity layer sits alongside the main model and gates how
    experiences restructure different depths of the model. Surface
    tasks update freely; identity-level restructuring requires
    earning the right through sufficient error magnitude.

    Args:
        config: IdentityLayerConfig
    """

    def __init__(self, config: IdentityLayerConfig):
        super().__init__()
        self.config = config

        self.self_model = SelfModel(config.d_model, config.d_identity)
        self.depth_gate = OntologicalDepthGate(config)

        # Identity coherence loss: self-model should be consistent
        self.coherence_proj = nn.Linear(config.d_identity, config.d_identity)

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
        """Process experience through identity layer.

        Args:
            experience: [B, D] experience representation
            error_per_layer: [B, num_layers] or [num_layers] error magnitudes
            salience: Optional [B] overall salience of this experience

        Returns:
            Dict with:
                'layer_gates': [num_layers] per-layer update permissions
                'identity_coherence': scalar coherence of self-model
                'self_revision_gate': whether self-model should be revised
                'identity_loss': coherence loss for training
                'transformation_triggered': whether identity changed
        """
        # Compute mean error magnitude for self-model gating
        if error_per_layer.dim() == 1:
            error_magnitudes = error_per_layer
        else:
            error_magnitudes = error_per_layer.mean(dim=0)

        mean_error = error_magnitudes.mean().item()

        # Process through self-model
        self_output = self.self_model(experience, mean_error)

        # Compute per-layer gates
        layer_gates = self.depth_gate.compute_layer_gates(error_magnitudes)

        # Identity coherence loss
        projected_self = self.coherence_proj(self_output["self_repr"])
        coherence_loss = (1.0 - self_output["identity_coherence"]) * self.config.coherence_weight

        # Determine if identity revision should be applied
        revision_gate = self_output["update_gate"].mean().item()
        transformation_triggered = False

        if mean_error >= self.config.identity_threshold and revision_gate > 0.5:
            # Apply identity revision
            proposed = self_output["proposed_revision"].mean(dim=0)
            self.self_model.apply_revision(proposed, revision_gate * 0.1)
            self.identity_updates += 1
            transformation_triggered = True

            # Record transformation
            if len(self.transformation_history) < self.config.max_transformation_history:
                self.transformation_history.append({
                    "step": self.identity_updates.item(),
                    "error_magnitude": mean_error,
                    "revision_gate": revision_gate,
                    "coherence_before": self_output["identity_coherence"].item(),
                })

            logger.info(
                f"Identity transformation #{self.identity_updates.item()}: "
                f"error={mean_error:.4f}, gate={revision_gate:.4f}"
            )

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
            "self_revision_gate": self_output["update_gate"],
            "identity_loss": coherence_loss,
            "transformation_triggered": transformation_triggered,
            "self_repr": self_output["self_repr"].detach(),
            "proposed_revision": self_output["proposed_revision"],
        }

    def get_identity_state(self) -> Dict[str, object]:
        """Get identity state for diagnostics."""
        return {
            "self_repr_norm": self.self_model.self_repr.norm().item(),
            "identity_updates": self.identity_updates.item(),
            "deep_updates": self.deep_updates.item(),
            "transformation_count": len(self.transformation_history),
            "recent_transformations": self.transformation_history[-5:],
        }

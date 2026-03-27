"""
ExperientialTrainingLoop: Orchestrator for experiential CG training.

Unifies all five experiential learning analogs into a single training
loop that processes each batch through the complete experiential pipeline:

    Input -> Prediction
         |
    Error Signal (multi-modal via ExperientialLossSignal)
         |
    Salience Gate (via SalienceWeighter — is this consequential?)
         |
    Vritti Resistance Field (via VrittiResistanceGate — resist this update?)
         |
    If resistance overcome -> propagate to identity layer
    If resistance holds -> queue for offline consolidation
         |
    Offline Cycle (via OfflineConsolidationCycle — sleep analog)
         |
    Emergent reorganization — self-model revision via IdentityLayer

This is not one paper. This is a research program. But the components
are individually tractable and several are present in the existing
patent portfolio in nascent form.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import torch
import torch.nn as nn
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import logging

from symbolu.training.conscious_generation.experiential.experiential_loss import (
    ExperientialLossSignal,
    ExperientialLossConfig,
)
from symbolu.training.conscious_generation.experiential.vritti_resistance_gate import (
    VrittiResistanceGate,
    VrittiResistanceConfig,
)
from symbolu.training.conscious_generation.experiential.offline_consolidation import (
    OfflineConsolidationCycle,
    ConsolidationConfig,
)
from symbolu.training.conscious_generation.experiential.salience_weighter import (
    SalienceWeighter,
    SalienceConfig,
)
from symbolu.training.conscious_generation.experiential.identity_layer import (
    IdentityLayer,
    IdentityLayerConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class ExperientialTrainingConfig:
    """Master configuration for experiential training.

    Attributes:
        d_model: Model hidden dimension
        num_regions: Number of gatable model regions (maps to ontological layers)
        enable_experiential_loss: Enable multi-modal loss
        enable_resistance_gate: Enable vritti resistance gating
        enable_consolidation: Enable offline consolidation cycles
        enable_salience: Enable consequence-based weighting
        enable_identity: Enable identity layer
        experiential_loss_weight: Weight for experiential loss component
        identity_loss_weight: Weight for identity coherence loss
        consolidation_interval: Steps between consolidation cycles
        log_interval: Steps between detailed logging
    """
    d_model: int = 128
    num_regions: int = 12
    enable_experiential_loss: bool = True
    enable_resistance_gate: bool = True
    enable_consolidation: bool = True
    enable_salience: bool = True
    enable_identity: bool = True
    experiential_loss_weight: float = 0.1
    identity_loss_weight: float = 0.05
    consolidation_interval: int = 100
    log_interval: int = 50


class ExperientialTrainingLoop(nn.Module):
    """Complete experiential training orchestrator.

    Wires together all five experiential analogs into a coherent
    training pipeline. Each training step:

    1. Compute multi-modal experiential loss (embodiment analog)
    2. Estimate salience of errors (consequence modeling)
    3. Gate updates through vritti resistance field
    4. Route high-stakes updates to identity layer
    5. Queue blocked updates for consolidation
    6. Periodically run offline consolidation

    The result is a training process where the system:
    - Resists easy updates (vritti resistance)
    - Consolidates offline (sleep analog)
    - Weights errors by consequence (salience)
    - Can restructure its self-model (identity)
    - Experiences loss as textured, not scalar (embodiment)

    Args:
        config: ExperientialTrainingConfig
    """

    def __init__(self, config: ExperientialTrainingConfig):
        super().__init__()
        self.config = config

        # 1. Multi-modal experiential loss
        if config.enable_experiential_loss:
            self.experiential_loss = ExperientialLossSignal(
                ExperientialLossConfig(
                    d_model=config.d_model,
                )
            )

        # 2. Salience weighting
        if config.enable_salience:
            self.salience_weighter = SalienceWeighter(
                SalienceConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                )
            )

        # 3. Vritti resistance gate
        if config.enable_resistance_gate:
            self.resistance_gate = VrittiResistanceGate(
                VrittiResistanceConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                )
            )

        # 4. Offline consolidation
        if config.enable_consolidation:
            self.consolidation = OfflineConsolidationCycle(
                ConsolidationConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                    consolidation_interval=config.consolidation_interval,
                )
            )

        # 5. Identity layer
        if config.enable_identity:
            self.identity_layer = IdentityLayer(
                IdentityLayerConfig(
                    d_model=config.d_model,
                    num_ontological_layers=config.num_regions,
                )
            )

        # Step counter
        self.register_buffer("global_step", torch.tensor(0, dtype=torch.long))

    def forward(
        self,
        hidden: torch.Tensor,
        target_hidden: torch.Tensor,
        region_states: Optional[torch.Tensor] = None,
        base_loss: Optional[torch.Tensor] = None,
        layer_states: Optional[List[torch.Tensor]] = None,
    ) -> Dict[str, Any]:
        """Run one experiential training step.

        Args:
            hidden: [B, T, D] predicted hidden states
            target_hidden: [B, T, D] target hidden states
            region_states: Optional [B, num_regions, D] per-region states.
                           If None, derived from hidden by chunking.
            base_loss: Optional scalar base loss (e.g., cross-entropy)
            layer_states: Optional list of per-layer hidden states

        Returns:
            Dict with all loss components and diagnostics:
                'total_loss': Final training loss
                'experiential_loss': Multi-modal loss breakdown
                'salience': Salience weights and diagnostics
                'resistance': Gate values and vritti distributions
                'identity': Identity layer outputs
                'consolidation': Consolidation metrics (if triggered)
        """
        B, T, D = hidden.shape
        device = hidden.device
        result: Dict[str, Any] = {}
        total_loss = torch.tensor(0.0, device=device)

        # Derive region states if not provided
        if region_states is None:
            region_states = self._derive_region_states(hidden)

        # ================================================================
        # Step 1: Multi-modal experiential loss (embodiment)
        # ================================================================
        if self.config.enable_experiential_loss:
            exp_loss_output = self.experiential_loss(hidden, target_hidden, base_loss)
            total_loss = total_loss + (
                self.config.experiential_loss_weight * exp_loss_output["loss"]
            )
            result["experiential_loss"] = exp_loss_output
        elif base_loss is not None:
            total_loss = total_loss + base_loss

        # ================================================================
        # Step 2: Compute error signal per region
        # ================================================================
        error_signal = self._compute_region_errors(hidden, target_hidden)

        # ================================================================
        # Step 3: Salience weighting (consequence modeling)
        # ================================================================
        if self.config.enable_salience:
            cross_modal = None
            if self.config.enable_experiential_loss:
                # Use loss texture as cross-modal impact indicator
                texture = exp_loss_output["loss_texture"]
                cross_modal = texture.unsqueeze(0).expand(B, -1)
                # Pad/trim to num_regions
                if cross_modal.shape[1] < self.config.num_regions:
                    pad = torch.zeros(
                        B, self.config.num_regions - cross_modal.shape[1],
                        device=device,
                    )
                    cross_modal = torch.cat([cross_modal, pad], dim=1)
                else:
                    cross_modal = cross_modal[:, :self.config.num_regions]

            salience_output = self.salience_weighter(error_signal, cross_modal)
            result["salience"] = salience_output
        else:
            salience_output = None

        # ================================================================
        # Step 4: Vritti resistance gate
        # ================================================================
        if self.config.enable_resistance_gate:
            # Propose update direction (simplified: negative error)
            proposed_update = -error_signal

            # Weight proposed update by salience
            if salience_output is not None:
                proposed_update = proposed_update * salience_output[
                    "salience_weights"
                ].unsqueeze(-1)

            resistance_output = self.resistance_gate(
                region_states, error_signal, proposed_update
            )
            result["resistance"] = resistance_output

            # Use gated update for downstream processing
            effective_update = resistance_output["gated_update"]
        else:
            effective_update = -error_signal

        # ================================================================
        # Step 5: Identity layer (self-model revision)
        # ================================================================
        if self.config.enable_identity:
            # Summarize experience for identity processing
            experience = effective_update.mean(dim=1)  # [B, num_regions, D] -> [B, D]
            # Average across regions
            if experience.dim() == 3:
                experience = experience.mean(dim=1)

            # Error per layer (use region errors as proxy)
            error_per_layer = error_signal.norm(dim=-1).mean(dim=0)

            identity_output = self.identity_layer(
                experience, error_per_layer
            )
            total_loss = total_loss + (
                self.config.identity_loss_weight * identity_output["identity_loss"]
            )
            result["identity"] = identity_output

        # ================================================================
        # Step 6: Offline consolidation (sleep analog)
        # ================================================================
        if self.config.enable_consolidation:
            self.consolidation.step()

            # Drain resistance gate queue into consolidation buffer
            if self.config.enable_resistance_gate:
                queued = self.resistance_gate.drain_consolidation_queue()
                if queued:
                    self.consolidation.ingest_queue(queued)

            # Run consolidation if it's time
            if self.consolidation.should_consolidate():
                consolidation_output = self.consolidation.consolidate(layer_states)
                result["consolidation"] = consolidation_output

                # Add coherence loss from consolidation
                if isinstance(consolidation_output.get("coherence_loss"), torch.Tensor):
                    total_loss = total_loss + (
                        0.01 * consolidation_output["coherence_loss"]
                    )

        # ================================================================
        # Finalize
        # ================================================================
        result["total_loss"] = total_loss
        self.global_step += 1

        # Periodic logging
        if self.global_step.item() % self.config.log_interval == 0:
            self._log_diagnostics(result)

        return result

    def _derive_region_states(self, hidden: torch.Tensor) -> torch.Tensor:
        """Derive per-region states from hidden states by chunking.

        Args:
            hidden: [B, T, D]

        Returns:
            [B, num_regions, D] — mean-pooled chunks of the sequence
        """
        B, T, D = hidden.shape
        R = self.config.num_regions

        if T >= R:
            chunk_size = T // R
            chunks = []
            for i in range(R):
                start = i * chunk_size
                end = start + chunk_size if i < R - 1 else T
                chunks.append(hidden[:, start:end, :].mean(dim=1))
            return torch.stack(chunks, dim=1)  # [B, R, D]
        else:
            # Pad with mean if sequence shorter than regions
            mean_hidden = hidden.mean(dim=1, keepdim=True)  # [B, 1, D]
            padded = mean_hidden.expand(B, R, D).clone()
            padded[:, :T, :] = hidden.mean(dim=1, keepdim=True).expand(B, T, D)
            return padded

    def _compute_region_errors(
        self, hidden: torch.Tensor, target_hidden: torch.Tensor
    ) -> torch.Tensor:
        """Compute per-region error signals.

        Args:
            hidden: [B, T, D] predicted
            target_hidden: [B, T, D] target

        Returns:
            [B, num_regions, D] error signal per region
        """
        error = hidden - target_hidden  # [B, T, D]
        return self._derive_region_states(error)

    def _log_diagnostics(self, result: Dict[str, Any]) -> None:
        """Log training diagnostics at intervals."""
        step = self.global_step.item()
        parts = [f"Step {step}"]

        if "experiential_loss" in result:
            exp = result["experiential_loss"]
            parts.append(f"exp_loss={exp['loss'].item():.4f}")
            parts.append(f"interference={exp['interference_magnitude'].item():.4f}")

        if "resistance" in result:
            res = result["resistance"]
            mean_gate = res["gate_values"].mean().item()
            parts.append(f"mean_gate={mean_gate:.3f}")
            parts.append(f"queued={res['queued_count']}")

        if "salience" in result:
            sal = result["salience"]
            parts.append(f"mean_salience={sal['salience_weights'].mean().item():.3f}")

        if "identity" in result:
            ident = result["identity"]
            parts.append(f"coherence={ident['identity_coherence'].item():.3f}")
            if ident["transformation_triggered"]:
                parts.append("IDENTITY_CHANGED")

        if "consolidation" in result:
            con = result["consolidation"]
            parts.append(
                f"consolidated(replay={con['replayed']}, "
                f"prune={con['pruned']}, deep={con['deepened']})"
            )

        parts.append(f"total_loss={result['total_loss'].item():.4f}")
        logger.info(" | ".join(parts))

    def get_full_state(self) -> Dict[str, Any]:
        """Get complete experiential training state for diagnostics."""
        state = {
            "global_step": self.global_step.item(),
        }

        if self.config.enable_resistance_gate:
            state["resistance"] = self.resistance_gate.get_resistance_state()

        if self.config.enable_consolidation:
            state["consolidation"] = self.consolidation.get_state()

        if self.config.enable_identity:
            state["identity"] = self.identity_layer.get_identity_state()

        if self.config.enable_salience:
            state["scar_tissue"] = {
                "levels": self.salience_weighter.scar_registry.get_scar_levels().tolist(),
                "most_scarred": self.salience_weighter.scar_registry.get_most_scarred(),
            }

        return state

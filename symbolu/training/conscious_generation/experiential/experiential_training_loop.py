"""
ExperientialTrainingLoop: Orchestrator for experiential CG training.

Explicit time-scale separation:

    FAST loop (every step):
        1. Compute multi-modal experiential loss (L_token + L_temporal + L_coherence)
        2. Compute salience (independent signal)
        3. Compute resistance (independent signal)
        4. Apply: g_eff = clamp(salience * resistance_openness, 0, max_gain) * g
        5. Accumulate high-salience signals into identity EMA buffer

    MEDIUM loop (every N steps):
        1. Replay high-salience deferred samples
        2. Prune stale/low-salience entries from buffer

    SLOW loop (every M >> N steps):
        1. Consolidate identity (apply EMA to self-model)

Stability constraints:
    - Bounded gain: plasticity clamped to [0, max_gain]
    - EMA damping on resistance: prevents discontinuous state changes
    - No binary branching: all updates flow through continuous scaling
    - Identity updates only via EMA consolidation (no step-driven revision)

Salience and resistance are INDEPENDENT signals composed multiplicatively.
Neither determines the other.

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
        consolidation_interval: Steps between medium-loop consolidation
        identity_interval: Steps between slow-loop identity consolidation
        max_gain: Maximum plasticity gain (stability constraint)
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
    identity_interval: int = 1000
    max_gain: float = 3.0
    log_interval: int = 50


class ExperientialTrainingLoop(nn.Module):
    """Complete experiential training with explicit time-scale separation.

    Three nested loops:

    FAST (every step):
        loss -> salience -> resistance -> g_eff = s * r * g
        (continuous scaling, no branching)

    MEDIUM (every N steps):
        replay deferred + prune stale

    SLOW (every M >> N steps):
        identity EMA consolidation

    Salience and resistance are INDEPENDENT signals composed as:
        plasticity = salience * resistance_openness
        g_eff = clamp(plasticity, 0, max_gain) * g

    Args:
        config: ExperientialTrainingConfig
    """

    def __init__(self, config: ExperientialTrainingConfig):
        super().__init__()
        self.config = config

        # 1. Multi-modal experiential loss
        if config.enable_experiential_loss:
            self.experiential_loss = ExperientialLossSignal(
                ExperientialLossConfig(d_model=config.d_model)
            )

        # 2. Salience weighting (independent signal)
        if config.enable_salience:
            self.salience_weighter = SalienceWeighter(
                SalienceConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                )
            )

        # 3. Vritti resistance gate (gain-modulated, damped)
        if config.enable_resistance_gate:
            self.resistance_gate = VrittiResistanceGate(
                VrittiResistanceConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                    base_max_gain=config.max_gain,
                )
            )

        # 4. Offline consolidation (medium + slow loop)
        if config.enable_consolidation:
            self.consolidation = OfflineConsolidationCycle(
                ConsolidationConfig(
                    d_model=config.d_model,
                    num_regions=config.num_regions,
                    consolidation_interval=config.consolidation_interval,
                    identity_interval=config.identity_interval,
                )
            )

        # 5. Identity layer (accumulates in fast loop, consolidates in slow loop)
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
        coherence_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Run one experiential training step (fast loop + conditionally medium/slow).

        Args:
            hidden: [B, T, D] predicted hidden states
            target_hidden: [B, T, D] target hidden states
            region_states: Optional [B, num_regions, D] per-region states
            base_loss: Optional scalar base loss (e.g., cross-entropy)
            coherence_state: Optional [B, T, D] or [B, D] coherence/CSR
                latent state for feedback into loss computation

        Returns:
            Dict with all loss components and diagnostics
        """
        B, T, D = hidden.shape
        device = hidden.device
        result: Dict[str, Any] = {}
        total_loss = torch.tensor(0.0, device=device)

        # Derive region states if not provided
        if region_states is None:
            region_states = self._derive_region_states(hidden)

        # ================================================================
        # FAST LOOP — Step 1: Multi-modal experiential loss
        # ================================================================
        if self.config.enable_experiential_loss:
            exp_loss_output = self.experiential_loss(
                hidden, target_hidden, base_loss,
                coherence_state=coherence_state,
            )
            total_loss = total_loss + (
                self.config.experiential_loss_weight * exp_loss_output["loss"]
            )
            result["experiential_loss"] = exp_loss_output
        elif base_loss is not None:
            total_loss = total_loss + base_loss

        # ================================================================
        # FAST LOOP — Step 2: Compute error signal per region
        # ================================================================
        error_signal = self._compute_region_errors(hidden, target_hidden)

        # ================================================================
        # FAST LOOP — Step 3: Salience (independent signal)
        # ================================================================
        if self.config.enable_salience:
            cross_modal = None
            if self.config.enable_experiential_loss:
                texture = exp_loss_output["loss_texture"]
                cross_modal = texture.unsqueeze(0).expand(B, -1)
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
            salience_weights = salience_output["salience_weights"]
        else:
            salience_output = None
            salience_weights = None

        # ================================================================
        # FAST LOOP — Step 4: Resistance gate (damped, gain-modulated)
        #   g_eff = d_t * clamp(sigmoid(a*s + b*r + c), floor, max_gain_t) * g
        # ================================================================
        if self.config.enable_resistance_gate:
            proposed_update = -error_signal

            # Compute latent misalignment from experiential loss (if available)
            latent_misalignment = None
            if (self.config.enable_experiential_loss
                    and exp_loss_output["latent_alignment_loss"].item() > 0):
                # Broadcast scalar misalignment to per-region
                misalign_val = exp_loss_output["latent_alignment_loss"].item()
                latent_misalignment = torch.full(
                    (B, self.config.num_regions), misalign_val, device=device
                )

            # Coherence from experiential loss interference EMA
            coherence_val = None
            if self.config.enable_experiential_loss:
                # Use mean interference EMA as proxy for coherence
                ema = exp_loss_output["interference_ema"]
                coherence_val = 1.0 - ema.mean().item()  # Low interference = high coherence

            resistance_output = self.resistance_gate(
                region_states, error_signal, proposed_update,
                salience_weights=salience_weights,
                latent_misalignment=latent_misalignment,
                coherence=coherence_val,
            )
            result["resistance"] = resistance_output
            effective_update = resistance_output["gated_update"]
        else:
            effective_update = -error_signal

        # ================================================================
        # FAST LOOP — Step 5: Identity accumulation (EMA buffer only)
        # ================================================================
        if self.config.enable_identity:
            experience = effective_update.mean(dim=1)
            if experience.dim() == 3:
                experience = experience.mean(dim=1)

            error_per_layer = error_signal.norm(dim=-1).mean(dim=0)
            mean_salience = salience_weights.mean(dim=0) if salience_weights is not None else None

            identity_output = self.identity_layer(
                experience, error_per_layer, salience=mean_salience
            )
            total_loss = total_loss + (
                self.config.identity_loss_weight * identity_output["identity_loss"]
            )
            result["identity"] = identity_output

        # ================================================================
        # MEDIUM LOOP — Replay + prune (every N steps)
        # ================================================================
        if self.config.enable_consolidation:
            self.consolidation.step()

            # Feed deferred samples into buffer
            if self.config.enable_resistance_gate:
                deferred = self.resistance_gate.drain_deferred_buffer()
                if deferred:
                    self.consolidation.ingest(deferred)

            if self.consolidation.should_consolidate():
                consolidation_output = self.consolidation.consolidate()
                result["consolidation"] = consolidation_output

            # ============================================================
            # SLOW LOOP — Identity consolidation (every M >> N steps)
            # ============================================================
            if (self.config.enable_identity
                    and self.consolidation.should_consolidate_identity()):
                identity_revised = self.identity_layer.consolidate()
                result["identity_consolidated"] = identity_revised

        # ================================================================
        # Finalize
        # ================================================================
        result["total_loss"] = total_loss
        self.global_step += 1

        if self.global_step.item() % self.config.log_interval == 0:
            self._log_diagnostics(result)

        return result

    def _derive_region_states(self, hidden: torch.Tensor) -> torch.Tensor:
        """Derive per-region states from hidden states by chunking."""
        B, T, D = hidden.shape
        R = self.config.num_regions

        if T >= R:
            chunk_size = T // R
            chunks = []
            for i in range(R):
                start = i * chunk_size
                end = start + chunk_size if i < R - 1 else T
                chunks.append(hidden[:, start:end, :].mean(dim=1))
            return torch.stack(chunks, dim=1)
        else:
            mean_hidden = hidden.mean(dim=1, keepdim=True)
            return mean_hidden.expand(B, R, D).clone()

    def _compute_region_errors(
        self, hidden: torch.Tensor, target_hidden: torch.Tensor
    ) -> torch.Tensor:
        """Compute per-region error signals."""
        error = hidden - target_hidden
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
            mean_plasticity = res["plasticity"].mean().item()
            parts.append(f"plasticity={mean_plasticity:.3f}")
            parts.append(f"damping={res['damping'].item():.3f}")
            parts.append(f"max_gain={res['max_gain_t'].item():.2f}")
            parts.append(f"deferred={res['deferred_count']}")

        if "salience" in result:
            sal = result["salience"]
            parts.append(f"salience={sal['salience_weights'].mean().item():.3f}")

        if "identity" in result:
            ident = result["identity"]
            parts.append(f"coherence={ident['identity_coherence'].item():.3f}")

        if "identity_consolidated" in result:
            parts.append(f"IDENTITY_CONSOLIDATED={result['identity_consolidated']}")

        if "consolidation" in result:
            con = result["consolidation"]
            parts.append(
                f"replay={con['replayed']}, prune={con['pruned_low_salience']}"
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

    def summary(self) -> str:
        """One-call system health report across all components.

        Returns a human-readable string summarizing:
            - Global step and loop counters
            - Resistance: mean persistent resistance, consistency, deferred depth
            - Salience: mean scar tissue, most scarred regions
            - Identity: coherence, update count, accumulator depth
            - Consolidation: buffer depth, consolidation count
        """
        lines = [f"=== Experiential System Summary (step {self.global_step.item()}) ==="]

        if self.config.enable_resistance_gate:
            rs = self.resistance_gate.get_resistance_state()
            lines.append(
                f"Resistance: mean={rs['persistent_resistance'].mean().item():.3f}, "
                f"consistency={rs['consistency'].mean().item():.3f}, "
                f"deferred={rs['deferred_depth']}"
            )

        if self.config.enable_salience:
            scars = self.salience_weighter.scar_registry.get_scar_levels()
            top = self.salience_weighter.scar_registry.get_most_scarred(k=3)
            lines.append(
                f"Salience: mean_scar={scars.mean().item():.4f}, "
                f"top_scarred={[(r, f'{v:.3f}') for r, v in top]}"
            )

        if self.config.enable_identity:
            ids = self.identity_layer.get_identity_state()
            lines.append(
                f"Identity: repr_norm={ids['self_repr_norm']:.3f}, "
                f"updates={ids['identity_updates']}, "
                f"deep_updates={ids['deep_updates']}, "
                f"accumulator={ids['accumulator_count']}"
            )

        if self.config.enable_consolidation:
            cs = self.consolidation.get_state()
            lines.append(
                f"Consolidation: buffer={cs['buffer_depth']}, "
                f"mean_salience={cs['buffer_mean_salience']:.3f}, "
                f"consolidations={cs['consolidation_count']}"
            )

        return "\n".join(lines)

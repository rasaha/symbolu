"""
Experiential Learning for Conscious Generation (CG) Training.

A constrained adaptive optimizer with resistance-modulated plasticity.

Post-ablation architecture (5 commits of refinement + ablation):

Core equation:
    resistance_eff = resistance * exp(-k_m * misalignment)
    openness = (1 - resistance_eff) + w_s * salience
    plasticity = sigmoid(k * openness + bias)
    g_eff = d_t * clamp(plasticity, floor, max_gain_t) * g

Load-bearing components (ablation-validated):
    - Resistance gate — primary control signal
    - Biased sigmoid — prevents dead zones
    - Damping — protects against gradient noise
    - Adaptive gain — tracks training dynamics
    - Experiential loss — multi-modal error signal

Modulation components (not primary control):
    - Salience — merged into openness (modulation, not competing signal)
    - Historical consistency — diagnostics only
    - Identity layer — slow-loop EMA consolidation with adaptive alpha

Modules:
    1. ExperientialLossSignal — Multi-modal cross-frequency loss (load-bearing)
    2. VrittiResistanceGate — Resistance-driven plasticity controller (load-bearing)
    3. OfflineConsolidationCycle — Sleep analog: stochastic replay + prune
    4. SalienceWeighter — Consequence-based weighting (modulation)
    5. IdentityLayer — EMA self-model, consolidation-only updates

Time-scale separation:
    FAST (every step): loss → merged openness → plasticity → g_eff
    MEDIUM (every N steps): stochastic replay + prune
    SLOW (every M >> N steps): identity EMA consolidation (adaptive alpha)

Reference: docs/design/EXPERIENTIAL_LEARNING_DESIGN.md
"""

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
from symbolu.training.conscious_generation.experiential.experiential_training_loop import (
    ExperientialTrainingLoop,
    ExperientialTrainingConfig,
)
from symbolu.training.conscious_generation.experiential.minimal_controller import (
    ExperientialController,
    ExperientialControllerConfig,
)

__all__ = [
    # Minimal 12-parameter controller (production path)
    "ExperientialController",
    "ExperientialControllerConfig",
    # Full framework (reference implementation)
    "ExperientialLossSignal",
    "ExperientialLossConfig",
    "VrittiResistanceGate",
    "VrittiResistanceConfig",
    "OfflineConsolidationCycle",
    "ConsolidationConfig",
    "SalienceWeighter",
    "SalienceConfig",
    "IdentityLayer",
    "IdentityLayerConfig",
    "ExperientialTrainingLoop",
    "ExperientialTrainingConfig",
]

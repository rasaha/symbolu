"""
Experiential Learning for Conscious Generation (CG) Training.

Models the five analogs of natural experience in AI training:

1. ExperientialLossSignal — Multi-modal, cross-frequency loss that propagates
   differently across modalities (semantic, temporal, somatic-analog). Maps to
   FSCS frequency-stratified coherence where error at one frequency resonates
   into others.

2. VrittiResistanceGate — Continuous plasticity scaling via vritti field.
   NO binary branching. g_eff = clamp(salience * resistance_openness, 0, max_gain) * g.
   Salience and resistance are independent signals composed multiplicatively.

3. OfflineConsolidationCycle — Simplified sleep analog: replay high-salience
   deferred samples + prune stale/low-salience entries. No overloaded
   reconciliation logic.

4. SalienceWeighter — Consequence-based error weighting that develops
   "scar tissue" in regions that have experienced cascade failures.
   Errors that propagate downstream leave deeper traces.

5. IdentityLayer — Persistent self-model updated via EMA during consolidation
   phase ONLY (slow loop). NOT updated on every step. Maps to the 12-layer
   ontological architecture where deeper layers resist surface task errors.

Time-scale separation:
    FAST (every step): loss -> salience -> resistance -> g_eff = s * r * g
    MEDIUM (every N steps): replay deferred + prune stale
    SLOW (every M >> N steps): identity EMA consolidation

Stability constraints:
    - Bounded gain with rate limiting (max_gain, max_delta_fraction)
    - EMA damping on resistance with rate-limited damping changes
    - No binary branching
    - Identity via EMA only with adaptive alpha (modulated by stability/agreement)
    - Configurable latent dominance coefficient
    - Stochastic priority sampling in replay buffer

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

__all__ = [
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
